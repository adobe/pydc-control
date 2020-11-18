#!/usr/bin/env python3

import argparse
import jinja2
import os
import signal
import subprocess
import time
import yaml

from typing import Callable, Dict, List, Optional, Union

from . import config, docker_utils, log
from .exceptions import KnownException
from .data import Project, Service


# Constants, do not change
CONFIG_FILE = 'config.yml'
DOCKER_COMPOSE_TEMPLATE = 'docker-compose-template.yml'
DOCKER_COMPOSE_FILE = 'docker-compose.yml'
ENV_FILE = 'docker-compose.env'

# Global variables
BASE_DIR: str = None
CONFIG_PATH: str = None
DOCKER_COMPOSE_PATH: str = None
ENV_PATH: str = None


def _init_vars(base_dir):
    global BASE_DIR, CONFIG_PATH, DOCKER_COMPOSE_PATH, ENV_PATH
    BASE_DIR = base_dir
    CONFIG_PATH = os.path.join(base_dir, CONFIG_FILE)
    DOCKER_COMPOSE_PATH = os.path.join(base_dir, DOCKER_COMPOSE_FILE)
    ENV_PATH = os.path.join(base_dir, ENV_FILE)


def _detect_current_project(dev_project_names: List[str]) -> None:
    dir_name = os.path.basename(os.getcwd())
    base_dir_name = os.path.basename(BASE_DIR)
    if dir_name != base_dir_name:
        for project in Project.find_all():
            if project.directory == dir_name and project.name not in dev_project_names:
                log.get_logger().info(f'Assuming development for project {project.name}')
                dev_project_names.append(project.name)


def _check_project_directories(projects: List[Project]) -> None:
    if len(projects) == 0:
        log.get_logger().debug('No projects specified, not validating directories')
        return
    log.get_logger().info(f'Validating directories are present for {len(projects)} projects(s)')
    for project in projects:
        if not os.path.exists(project.path) or not os.path.isdir(project.path):
            raise KnownException(f'No directory found for the "{project.name}" project at {project.path}, '
                                 'please check the repository')


def _check_required_options():
    log.get_logger().info(f'Validating config file ({ENV_FILE})')
    if not os.path.exists(ENV_PATH):
        raise KnownException(f'Please create {ENV_PATH} containing env vars for project config, '
                             f'this will be used to configure each project. The {ENV_FILE}.example '
                             'file may be used as a template')
    with open(ENV_PATH, 'r') as f:
        contents = f.read()
        required_options = config.get_required_options()
        for option in required_options:
            if option not in contents:
                raise KnownException(f'The {ENV_PATH} file must include the {option} option')


def _set_dynamic_options(enabled_status_by_service: Dict[Service, bool]) -> None:
    with open(ENV_PATH, 'r') as fobj:
        env_file_contents = fobj.read()
    new_contents = []
    lines_changed = False

    services_by_dynamic_option = {}
    for service in Service.find_all():
        for option in service.dynamic_options.keys():
            services_by_dynamic_option[option] = service
    dynamic_options_seen = {}
    for option in services_by_dynamic_option:
        dynamic_options_seen[option] = False

    for line in env_file_contents.splitlines():
        option_considered = False
        for option in services_by_dynamic_option:
            if option not in line:
                continue
            option_considered = True
            dynamic_options_seen[option] = True
            service = services_by_dynamic_option[option]
            if enabled_status_by_service.get(service, True):
                value = service.dynamic_options[option].get('enabled')
            else:
                value = service.dynamic_options[option].get('disabled')

            if value:
                new_line = f'{option}={value}'
                if line != new_line:
                    log.get_logger().info(f'Replacing dynamic option for {option} in {ENV_FILE} with {value}')
                    new_contents.append(new_line)
                    lines_changed = True
            else:
                log.get_logger().info(f'Removing dynamic option for {option} in {ENV_FILE}')
                lines_changed = True

        # If no dynamic options are in the line, append it
        if not option_considered:
            new_contents.append(line)

    for option in services_by_dynamic_option:
        if not dynamic_options_seen[option]:
            service = services_by_dynamic_option[option]
            if enabled_status_by_service.get(service, True):
                value = service.dynamic_options[option].get('enabled')
            else:
                value = service.dynamic_options[option].get('disabled')
            if value:
                log.get_logger().info(f'Adding dynamic option for {option} in {ENV_FILE} with value {value}')
                new_contents.append(f'{option}={value}')
                lines_changed = True

    if lines_changed:
        with open(ENV_PATH, 'w') as fobj:
            fobj.write('\n'.join(new_contents))


def _link_config(projects: List[Project]):
    if len(projects) == 0:
        log.get_logger().debug(f'No projects specified, not linking {ENV_FILE}')
        return
    log.get_logger().info(f'Linking base {ENV_FILE} to {len(projects)} projects(s)')
    for project in projects:
        env_project_path = os.path.join(project.path, ENV_FILE)
        if not os.path.exists(env_project_path):
            os.symlink(ENV_PATH, env_project_path)
        elif os.path.islink(env_project_path):
            # nothing to do if it already exists
            pass
        else:
            os.remove(env_project_path)
            os.symlink(ENV_PATH, env_project_path)
        log.get_logger().debug(f'Linked in {project.path}')


def _render_docker_compose_file(base_dir, template_config):
    if not os.path.exists(os.path.join(base_dir, DOCKER_COMPOSE_TEMPLATE)):
        log.get_logger().debug(f'No {DOCKER_COMPOSE_TEMPLATE} detected in the {base_dir} directory, skipping generation')
        return
    try:
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(base_dir))
        template = env.get_template(DOCKER_COMPOSE_TEMPLATE)
        output = template.render(**template_config)
        with open(os.path.join(base_dir, DOCKER_COMPOSE_FILE), 'w') as f:
            f.write(output)
    except jinja2.exceptions.TemplateSyntaxError as e:
        raise KnownException(f'Could not render {base_dir}/{DOCKER_COMPOSE_TEMPLATE}: {e.message} on line {e.lineno}')


def _generate_docker_compose(dev_projects: List[Project], tag: str, enabled_status_by_service: Dict[Service, bool]):
    registry = config.get_registry(tag)
    log.get_logger().info(f'Generating docker-compose.yml with {len(dev_projects)} project(s) and tag "{tag}"')

    services = {}
    dev_project_names = list(project.name for project in dev_projects)
    for project in Project.find_all():
        if project.name in dev_project_names:
            continue
        for service in project.services:
            if (service.enable or service.disable) and not enabled_status_by_service.get(service, True):
                continue
            data = service.get_dc_data(registry, tag)
            # Add env file and network dynamically
            if 'env_file' not in data:
                data['env_file'] = [f'./{ENV_FILE}']
            if 'networks' not in data:
                data['networks'] = [config.get_dc_network()]
            services[service.dc_name] = data

    # Write out base docker compose
    docker_compose_data = {
        'version': '3',
        'networks': {
            config.get_dc_network(): {
                'external': True,
            },
        },
        'services': services,
    }
    docker_compose_data.update(config.get_dc_data())
    with open(os.path.join(BASE_DIR, DOCKER_COMPOSE_FILE), 'w') as f:
        yaml.safe_dump(docker_compose_data, f)

    enabled_services = {}
    for service, status in enabled_status_by_service.items():
        enabled_services[service.name] = status
    template_config = {
        'dev_project_names': dev_project_names,
        'enabled_services': enabled_services,
        'tag': tag,
        'registry': registry,
        'network': config.get_dc_network(),
        'core_prefix': config.get_service_prefix('core'),
        'service_prefix': config.get_service_prefix(),
    }
    for project in dev_projects:
        _render_docker_compose_file(project.path, template_config)


def _wait_for_open_ports(service: Service) -> None:
    log.get_logger().info(f'Waiting for ports to be open and available on container {service.container_name}')
    open_ports = None
    while not open_ports:
        open_ports = docker_utils.get_open_ports(service.container_name)
        if not open_ports:
            log.get_logger().debug(f'Waiting for ports to be listed on container {service.container_name}')
            time.sleep(0.1)
            continue
        for port in open_ports:
            log.get_logger().debug(f'Waiting for port {port} to be open on container {service.container_name}')
            while not docker_utils.is_port_open(port):
                log.get_logger().debug(f'Port is not open yet, sleeping...')
                time.sleep(0.1)
    for port, path in service.wait_for_ports.items():
        docker_utils.check_port(service.container_name, port, path)


def _run_checkout(args: argparse.Namespace):
    if args.all_projects or not args.dev_project_names:
        projects = Project.find_all()
    else:
        projects = _get_dev_projects(args)
    if len(projects) == 0:
        raise KnownException(f'There are no projects available, please set projects')

    parent_dir = os.path.realpath(os.path.join(BASE_DIR, '..'))
    log.get_logger().info(f'Checking out {len(projects)} projects to {parent_dir}')
    result = os.EX_OK
    for project in projects:
        # Skip projects without a repository
        if not project.repository:
            log.get_logger().debug(f'Skipping project {project.name} since it does not have a configured repository')
            continue

        if os.path.exists(project.path):
            log.get_logger().info(f'########### {project.name} (pulling changes) ###########')
            commands = ['git', 'pull', 'upstream', 'master']
            cwd = project.path
        else:
            log.get_logger().info(f'########### {project.name} (cloning) ###########')
            commands = ['git', 'clone', '--origin', 'upstream', project.repository]
            cwd = parent_dir
        exit_code = subprocess.call(commands, cwd=cwd)

        if exit_code:
            log.get_logger().warning(f'Could not clone or update {project.name} ({project.path}), see errors above')
            result = exit_code

        if not result and len(args.extra_remotes) > 0:
            log.get_logger().debug('Adding any remotes specified if not already added')
            base_git_path = project.repository.split(':')[0]
            for r in args.extra_remotes:
                org = name = r[0]
                if len(r) == 2:
                    name = r[1] # an optional name to be specified for the remote

                # check if remote exists
                command = ['git', 'ls-remote', '-q', '--exit-code', name]
                # ignore stdout as the check can be misleading if this is the first time we are adding a repo
                with open(os.devnull, 'w') as fnull:
                    exit_code = subprocess.call(command, cwd=project.path, stdout=fnull, stderr=subprocess.STDOUT)
                if exit_code == 0:
                    log.get_logger().debug(f'Remote {name} already exists in project {project.name}')
                    continue
                log.get_logger().info(f'Trying to add remote {name} at '
                                      f'{base_git_path}:{org}/{project.directory}.git in project {project.name}')
                command = [ 'git', 'remote', 'add', name, f'{base_git_path}:{org}/{project.directory}.git' ]
                exit_code = subprocess.call(command, cwd=project.path)

                if exit_code:
                    log.get_logger().warning(f'There was a problem adding remote {r} in project {project.name}')

    return result


def _get_repo_status(args: argparse.Namespace):
    if args.all_projects or not args.dev_project_names:
        projects = Project.find_all()
    else:
        projects = _get_dev_projects(args)
    if len(projects) == 0:
        raise KnownException(f'There are no projects available, please set projects')

    log.get_logger().info(f'Getting the git status for {len(projects)} projects')

    for project in projects:
        log.get_logger().info(f'########### {project.name} ###########')
        if not project.repository:
            log.get_logger().info('No configured repository')
            continue

        subprocess.call(['git', 'status', '--short', '--branch', '--untracked-files=no'], cwd=project.path)


def _init_docker_compose(args: argparse.Namespace, dev_projects: List[Project]) -> None:
    docker_utils.check_docker_network()
    _check_project_directories(dev_projects)
    _check_required_options()
    enabled_status_by_service = {}
    for service in Service.find_enabled():
        enabled_status_by_service[service] = getattr(args, f'enable_{service.name}')
    for service in Service.find_disabled():
        enabled_status_by_service[service] = not getattr(args, f'disable_{service.name}')
    _set_dynamic_options(enabled_status_by_service)
    _link_config(dev_projects)
    _generate_docker_compose(dev_projects, args.tag, enabled_status_by_service)


def _run_dc_init(args: argparse.Namespace):
    dev_projects = _get_dev_projects(args)
    _init_docker_compose(args, dev_projects)
    return os.EX_OK


def _run_docker_compose_with_projects(dev_projects: List[Project], docker_compose_args: List[str]) -> int:
    # Always use the same project name to allow containers to be started/stopped from any repo
    commands = ['docker-compose', '-p', config.get_dc_project()]
    commands.extend(['-f', DOCKER_COMPOSE_PATH])
    for project in dev_projects:
        commands.extend(['-f', os.path.join(project.path, DOCKER_COMPOSE_FILE)])
    commands.extend(docker_compose_args)

    # Only do this if we are bringing up the containers and the other arguments are all options
    if 'up' in docker_compose_args and all(arg.startswith('-') or arg == 'up' for arg in docker_compose_args):
        # Start core services
        core_commands = []
        core_commands.extend(commands)
        if '--detach' not in core_commands and '-d' not in core_commands:
            core_commands.append('--detach')

        # Get core service names
        core_services = Service.find_all(core=True)
        core_service_names = list(service.dc_name for service in core_services)
        core_commands.extend(core_service_names)

        log.get_logger().info(
            f'Starting {len(core_service_names)} core service(s) (detached) by calling {" ".join(core_commands)}'
        )
        exit_code = call_commands(core_commands)
        if exit_code:
            return exit_code

        # Wait for ports to be opened for each core service
        for service in core_services:
            _wait_for_open_ports(service)

        # Start base services first if we are developing a service
        if dev_projects:
            # Bring up base containers first (detached to not fill up your screen with logs) only if have services
            base_commands = []
            base_commands.extend(commands)
            if '--detach' not in base_commands and '-d' not in base_commands:
                base_commands.append('--detach')

            # Only include services in this repo's docker compose file and are not core services
            base_services = docker_utils.read_services_from_dc(DOCKER_COMPOSE_PATH)
            print(f'base services 1: {base_services}')
            base_services = list(filter(lambda service: service not in core_service_names, base_services))
            print(f'base services 2: {base_services}')
            base_commands.extend(base_services)

            log.get_logger().info(
                f'Starting {len(base_services)} base service(s) (detached) by calling {" ".join(base_commands)}'
            )
            exit_code = subprocess.call(base_commands)
            if exit_code:
                return exit_code
            # else pass through to the up call for all other services

            # Bring up the service containers only since the base ones are already started
            for project in dev_projects:
                commands.extend(docker_utils.read_services_from_dc(os.path.join(project.path, DOCKER_COMPOSE_FILE)))
        else:
            # Add the rest of the services to the call (exclude core services since they are already started)
            all_services = docker_utils.read_services_from_dc(DOCKER_COMPOSE_PATH)
            all_services = list(filter(lambda service: service not in core_service_names, all_services))
            commands.extend(all_services)

    log.get_logger().info(f'Calling {" ".join(commands)}')
    return call_commands(commands)


def _run_docker_compose_internal(args: argparse.Namespace, docker_compose_args: List[str]):
    dev_projects = _get_dev_projects(args)
    _init_docker_compose(args, dev_projects)
    return _run_docker_compose_with_projects(dev_projects, docker_compose_args)


def _run_docker_compose(args: argparse.Namespace):
    return _run_docker_compose_internal(args, args.docker_compose_args)


def _get_cli_build_args(build_args: Optional[Union[Dict[str, str], List[str]]]) -> List[str]:
    if not build_args:
        return []
    if isinstance(build_args, dict):
        values = list(f'{key}={value}' for key, value in build_args.items())
    else:
        values = build_args

    result = []
    for value in values:
        result.extend(['--build-arg', value])
    return result


def _run_dc_build(args: argparse.Namespace):
    docker_compose_args = ['build']
    if args.no_cache:
        docker_compose_args.append('--no-cache')
    docker_compose_args.extend(_get_cli_build_args(config.get_dc_build_args()))
    if args.dev_project_names and not args.all_projects:
        dev_projects = _get_dev_projects(args)
        for project in dev_projects:
            docker_compose_args.extend(
                docker_utils.read_services_from_dc(os.path.join(project.path, DOCKER_COMPOSE_FILE))
            )
    return _run_docker_compose_internal(args, docker_compose_args)


def _run_dc_config(args: argparse.Namespace):
    return _run_docker_compose_internal(args, ['config'])


def _run_dc_down(args: argparse.Namespace):
    return _run_docker_compose_internal(args, ['down'])


def _run_dc_pull(args: argparse.Namespace):
    return _run_docker_compose_internal(args, ['pull'])


def _run_dc_pull_config(args: argparse.Namespace):
    config_service = Service.find_one(config.get_target_service('config'))
    if not config_service:
        raise KnownException(f'A config target service is not defined, please define one to pull configuration')
    if (config_service.disable and args.disable_config) or (config_service.enable and not args.enable_config):
        raise KnownException('Cannot pull configuration when using the real config service')
    return _run_docker_compose_internal(args, ['pull', config_service.dc_name])


def _run_dc_stop(args: argparse.Namespace):
    return _run_docker_compose_internal(args, ['stop'])


def _run_dc_up(args: argparse.Namespace):
    return _run_docker_compose_internal(args, ['up'])


def _run_dc_up_detach(args: argparse.Namespace):
    return _run_docker_compose_internal(args, ['up', '--detach'])


def _run_dc_up_recreate(args: argparse.Namespace):
    return _run_docker_compose_internal(args, ['up', '--force-recreate'])


def _get_dev_projects(args: argparse.Namespace) -> List[Project]:
    # Filter the projects by the list of passed in project names
    return list(project for project in Project.find_all() if project.name in args.dev_project_names)


def _get_print_help_func(parser):
    def print_help(args: argparse.Namespace):
        parser.print_help()
        return os.EX_OK

    return print_help


def _get_config_service_target() -> Optional[Service]:
    return Service.find_one(config.get_target_service('config'))


def _parse_args(configure_parsers: Callable) -> argparse.Namespace:
    # Get all projects defined in the configuration
    projects = Project.find_all()

    # Parse arguments
    parser = argparse.ArgumentParser(
        description='Runs setup for Gauntlet services through a Jinja template and docker-compose.',
    )
    parser.add_argument(
        '-p', '--projects-dev',
        action='append',
        default=[],
        dest='dev_project_names',
        # Only projects with actual directories can be developed
        choices=list(project.name for project in projects if project.directory),
        help="The projects to develop locally, does not pull upstream images for them.",
    )
    parser.add_argument(
        "-t", "--tag",
        dest="tag",
        default='latest',
        choices=['latest', 'dev', 'stage', 'prod'],
        help="The docker tag to use for upstream images, defaults to latest (dev is equivalent to latest).",
    )
    parser.add_argument(
        "-d", "--debug",
        dest="debug",
        action="store_true",
        help="Enable debug output.",
    )
    parser.set_defaults(
        func=_get_print_help_func(parser),
    )

    # Build arguments for enabled/disabled service dynamically
    for service in Service.find_enabled():
        parser.add_argument(
            f"--enable-{service.name.replace('_', '-')}",
            dest=f"enable_{service.name}",
            action="store_true",
            help=f"Enables the optional {service.name} service from the {service.project_name} "
            f"project, disabled by default",
        )
    for service in Service.find_disabled():
        parser.add_argument(
            f"--disable-{service.name.replace('_', '-')}",
            dest=f"disable_{service.name}",
            action="store_true",
            help=f"Disables the optional {service.name} service from the {service.project_name} "
            f"project, enabled by default",
        )

    subparsers = parser.add_subparsers(title='Commands', help='commands')

    # Help shortcut
    # help_parser = subparsers.add_parser(
    #     'help',
    #     aliases=['h'],
    #     help='Prints help for commands and usages'
    # )

    # Checkout
    checkout_parser = subparsers.add_parser(
        'checkout',
        aliases=['co'],
        help='Clones and/or updates repositories for all specified projects'
    )
    checkout_parser.set_defaults(
        func=_run_checkout,
    )
    checkout_parser.add_argument(
        "-a", "--all-projects",
        dest="all_projects",
        action="store_true",
        help="Checkout/clone all projects.",
    )
    checkout_parser.add_argument(
        '-e', '--extra-remote',
        dest='extra_remotes',
        action='append',
        nargs='*',
        default=[],
        help="Add a remote when cloning/checking out. Each flag can take 1-2 params, 1 param should be the space "
             "the remote exists in github. If a 2nd param is specified it is an optional name for the remote."
    )

    # Repo Status
    repo_status_parser = subparsers.add_parser(
        'repo-status',
        aliases=['rs'],
        help='gets the status of the repos associated with gauntlet-control'
    )
    repo_status_parser.set_defaults(
        func=_get_repo_status,
    )
    repo_status_parser.add_argument(
        "-a", "--all-projects",
        dest="all_projects",
        action="store_true",
        help="Get the status of all projects.",
    )

    # Docker Status
    # Init
    init_parser = subparsers.add_parser(
        'init',
        help='Generates docker-compose templates and copies configuration, but does not run any commands'
    )
    init_parser.set_defaults(
        func=_run_dc_init,
    )

    # Docker compose
    dc_parser = subparsers.add_parser(
        'docker-compose',
        aliases=['dc'],
        help='Generates docker-compose templates, copies configuration, and runs any docker-compose command'
    )
    dc_parser.set_defaults(
        func=_run_docker_compose,
    )
    dc_parser.add_argument(
        'docker_compose_args',
        nargs='*',
        help="The arguments to pass directly to docker-compose.",
    )

    # Docker compose aliases
    build_parser = subparsers.add_parser(
        'build',
        help='Alias for the "dc build" command'
    )
    build_parser.add_argument(
        "--no-cache",
        dest="no_cache",
        action="store_true",
        help="Do not use cache when building the image.",
    )
    build_parser.add_argument(
        "-a", "--all-projects",
        dest="all_projects",
        action="store_true",
        help="Builds all projects instead of just those specified or by using the current directory,"
             "this is assumed if no projects are specified.",
    )
    build_parser.set_defaults(
        func=_run_dc_build,
    )
    config_parser = subparsers.add_parser(
        'config',
        help='Alias for the "dc config" command'
    )
    config_parser.set_defaults(
        func=_run_dc_config,
    )
    down_parser = subparsers.add_parser(
        'down',
        help='Alias for the "dc down" command'
    )
    down_parser.set_defaults(
        func=_run_dc_down,
    )
    pull_parser = subparsers.add_parser(
        'pull',
        help='Alias for the "dc pull" command'
    )
    pull_parser.set_defaults(
        func=_run_dc_pull,
    )
    stop_parser = subparsers.add_parser(
        'stop',
        help='Alias for the "dc stop" command'
    )
    stop_parser.set_defaults(
        func=_run_dc_stop,
    )
    up_parser = subparsers.add_parser(
        'up',
        help='Alias for the "dc up" command'
    )
    up_parser.set_defaults(
        func=_run_dc_up,
    )
    up_detach_parser = subparsers.add_parser(
        'up-detach',
        help='Alias for the "dc up --detach" command'
    )
    up_detach_parser.set_defaults(
        func=_run_dc_up_detach,
    )
    up_recreate_parser = subparsers.add_parser(
        'up-recreate',
        help='Alias for the "dc up --force-recreate" command'
    )
    up_recreate_parser.set_defaults(
        func=_run_dc_up_recreate,
    )

    # Do not allow to pull configuration unless there is a project for config
    config_service_target = _get_config_service_target()
    if config_service_target:
        pull_config_parser = subparsers.add_parser(
            'pull-config',
            help=f'Alias for the "dc pull" command'
        )
        pull_config_parser.set_defaults(
            func=_run_dc_pull_config,
        )

    if configure_parsers:
        configure_parsers(parser, subparsers)

    # Parse arguments
    return parser.parse_args()


def call_commands(commands):
    """
    Calls the commands given, waits for the result, and returns the exit code. Stdout and stderr are not redirected
    and are printed directly to the console. This also handles keyboard interrupts correctly.
    :param commands: The commands to run as arguments to subprocess.Popen
    :return: The exit code of the commands
    """
    p = subprocess.Popen(commands)
    try:
        exit_code = p.wait()
    except KeyboardInterrupt:
        # When a keyboard interrupt is sent, pass it onto the child and then still wait
        # If this occurs twice, the second will abort this process
        p.send_signal(signal.SIGINT)
        exit_code = p.wait()
    return exit_code


def run(base_dir, configure_parsers: Callable = None):
    """
    Runs the CLI control command, including parsing arguments, etc.
    :param base_dir: The base directory of the control project
    :param configure_parsers: An optional method to configure additional parameters or arguments on the parser.
                              It receives two arguments, the top-level parser and the subparser for commands.
    :return: The exit code
    """
    # Initialize global vars based on the base dir
    _init_vars(base_dir)
    config.set_base_dir(base_dir)

    args = _parse_args(configure_parsers)

    # Initialize logging
    log.init_logger(args.debug)

    # Configure extra remotes
    if 'extra_remotes' in args.__dict__ and len(args.extra_remotes) > 0:
        for r in args.extra_remotes:
            if len(r) > 2 or len(r) < 1:
                log.get_logger().error(
                    'extra remotes parameters must take either 1 or 2 parameters for each specification.'
                )
                log.get_logger().error('example : -e origin bob')
                log.get_logger().error(
                    '      where origin is the remote name and bob is the space the repo is forked in'
                )
                return 3

    _detect_current_project(args.dev_project_names)

    # Make sure the config service is not disabled at the same time it is being developed
    config_service_target = _get_config_service_target()
    if config_service_target and config_service_target.project_name in args.dev_project_names and (
            (config_service_target.enable and not getattr(args, f'enable_{config_service_target.name}')) or
            (config_service_target.disable and getattr(args, f'disable_{config_service_target.name}'))
    ):
        log.get_logger().error(
            f'To use the config service, you must not be developing on the '
            f'{config_service_target.project_name} project.'
        )
        return 4

    try:
        return args.func(args)
    except KnownException as e:
        log.get_logger().error(str(e))
        return 2
    except Exception as e:
        log.get_logger().error(f'Encountered an unexpected failure ({e.__class__}): {e}')
        if args.debug:
            raise
        return 1


if __name__ == '__main__':
    run(os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))
