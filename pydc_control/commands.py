"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import argparse
import os
import signal
import subprocess
import time
from typing import Dict, List, Optional, Union

from . import config, docker_compose_utils, docker_utils, log
from .data import Project, Service
from .exceptions import KnownException


def _wait_for_open_ports(service: Service) -> None:
    log.get_logger().info(f'Waiting for ports to be open and available on container {service.container_name}')
    open_ports = None
    while not open_ports:
        open_ports = docker_utils.get_open_ports(service.container_name)
        if not open_ports:
            log.get_logger().debug(f'Waiting for ports to be listed on container {service.container_name}')
            time.sleep(0.1)
            continue
        for container_port, host_port in open_ports.items():
            log.get_logger().debug(
                f'Waiting for port {host_port} (container port {container_port}) '
                f'to be open for container {service.container_name}'
            )
            while not docker_utils.is_port_open(host_port):
                log.get_logger().debug('Port is not open yet, sleeping...')
                time.sleep(0.1)
    for port, path in service.wait_for_ports.items():
        docker_utils.check_port(service.container_name, open_ports[port], path)


def _get_dev_projects(args: argparse.Namespace) -> List[Project]:
    # Filter the projects by the list of passed in project names
    return list(project for project in Project.find_all() if project.name in args.dev_project_names)


def _run_docker_compose_with_projects(
        args: argparse.Namespace, dev_projects: List[Project], docker_compose_args: List[str]
) -> int:
    # Always use the same project name to allow containers to be started/stopped from any repo
    commands = ['docker-compose', '-p', config.get_dc_project()]
    commands.extend(['-f', config.get_docker_compose_path()])
    for project in dev_projects:
        commands.extend(['-f', os.path.join(project.path, config.DOCKER_COMPOSE_FILE)])
    commands.extend(docker_compose_args)

    # Only do this if we are bringing up the containers and the other arguments are all options
    if 'up' in docker_compose_args and all(arg.startswith('-') or arg == 'up' for arg in docker_compose_args):
        # Start core services
        core_commands = []
        core_commands.extend(commands)
        if '--detach' not in core_commands and '-d' not in core_commands:
            core_commands.append('--detach')

        # Get core service names
        core_services = list(
            service for service in Service.find_all(core=True) if service.is_enabled(args)
        )
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
            base_services = docker_utils.read_services_from_dc(config.get_docker_compose_path())
            base_services = list(filter(lambda service: service not in core_service_names, base_services))
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
                commands.extend(
                    docker_utils.read_services_from_dc(os.path.join(project.path, config.DOCKER_COMPOSE_FILE))
                )
        else:
            # Add the rest of the services to the call (exclude core services since they are already started)
            all_services = docker_utils.read_services_from_dc(config.get_docker_compose_path())
            all_services = list(filter(lambda service: service not in core_service_names, all_services))
            commands.extend(all_services)

    log.get_logger().info(f'Calling {" ".join(commands)}')
    return call_commands(commands)


def _run_docker_compose_internal(args: argparse.Namespace, docker_compose_args: List[str], no_network: bool = False):
    dev_projects = _get_dev_projects(args)
    docker_compose_utils.init_docker_compose(args, dev_projects, no_network=no_network)
    return _run_docker_compose_with_projects(args, dev_projects, docker_compose_args)


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


def run_dc_init(args: argparse.Namespace):
    dev_projects = _get_dev_projects(args)
    docker_compose_utils.init_docker_compose(args, dev_projects)
    return os.EX_OK


def run_docker_compose(args: argparse.Namespace):
    return _run_docker_compose_internal(args, args.docker_compose_args)


def run_dc_build(args: argparse.Namespace):
    docker_compose_args = ['build']
    if args.no_cache:
        docker_compose_args.append('--no-cache')
    docker_compose_args.extend(_get_cli_build_args(config.get_dc_build_args()))
    if args.dev_project_names and not args.all_projects:
        dev_projects = _get_dev_projects(args)
        for project in dev_projects:
            # Sometimes the docker compose file might be missing during a build. If so, just generate it right now.
            # This should only run once for all dev projects
            dc_file_path = os.path.join(project.path, config.DOCKER_COMPOSE_FILE)
            if not os.path.exists(dc_file_path):
                docker_compose_utils.init_docker_compose(args, dev_projects, no_network=True)
            docker_compose_args.extend(docker_utils.read_services_from_dc(dc_file_path))
    return _run_docker_compose_internal(args, docker_compose_args)


def run_dc_config(args: argparse.Namespace):
    return _run_docker_compose_internal(args, ['config'], no_network=True)


def run_dc_down(args: argparse.Namespace):
    # Always add remove orphans flag since we can create orphans through enable/disable flags
    return _run_docker_compose_internal(args, ['down', '--remove-orphans'])


def run_dc_pull(args: argparse.Namespace):
    return _run_docker_compose_internal(args, ['pull'])


def run_dc_pull_config(args: argparse.Namespace):
    config_service = Service.find_config()
    if not config_service:
        raise KnownException('A config target service is not defined, please define one to pull configuration')
    if not config_service.is_enabled(args):
        raise KnownException('Cannot pull configuration when using the real config service')
    return _run_docker_compose_internal(args, ['pull', config_service.dc_name])


def run_dc_rm(args: argparse.Namespace):
    return _run_docker_compose_internal(args, ['rm', '--force'])


def run_dc_stop(args: argparse.Namespace):
    return _run_docker_compose_internal(args, ['stop'])


def run_dc_up(args: argparse.Namespace):
    return _run_docker_compose_internal(args, ['up'])


def run_dc_up_detach(args: argparse.Namespace):
    return _run_docker_compose_internal(args, ['up', '--detach'])


def run_dc_up_recreate(args: argparse.Namespace):
    return _run_docker_compose_internal(args, ['up', '--force-recreate'])


def get_repo_status(args: argparse.Namespace):
    if args.all_projects or not args.dev_project_names:
        projects = Project.find_all()
    else:
        projects = _get_dev_projects(args)
    if len(projects) == 0:
        raise KnownException('There are no projects available, please set projects')

    log.get_logger().info(f'Getting the git status for {len(projects)} projects')

    for project in projects:
        log.get_logger().info(f'########### {project.name} ###########')
        if not project.repository:
            log.get_logger().info('No configured repository')
            continue

        subprocess.call(['git', 'status', '--short', '--branch', '--untracked-files=no'], cwd=project.path)


def run_checkout(args: argparse.Namespace):
    # pylint: disable=too-many-branches
    if args.all_projects or not args.dev_project_names:
        projects = Project.find_all()
    else:
        projects = _get_dev_projects(args)
    if len(projects) == 0:
        raise KnownException('There are no projects available, please set projects')

    parent_dir = os.path.realpath(os.path.join(config.get_base_dir(), '..'))
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
            for remote in args.extra_remotes:
                org = name = remote[0]
                if len(remote) == 2:
                    # an optional name to be specified for the remote
                    name = remote[1]

                # check if remote exists
                command = ['git', 'ls-remote', '-q', '--exit-code', name]
                # ignore stdout as the check can be misleading if this is the first time we are adding a repo
                with open(os.devnull, 'wb') as fnull:
                    exit_code = subprocess.call(command, cwd=project.path, stdout=fnull, stderr=subprocess.STDOUT)
                if exit_code == 0:
                    log.get_logger().debug(f'Remote {name} already exists in project {project.name}')
                    continue
                log.get_logger().info(f'Trying to add remote {name} at '
                                      f'{base_git_path}:{org}/{project.directory}.git in project {project.name}')
                command = ['git', 'remote', 'add', name, f'{base_git_path}:{org}/{project.directory}.git']
                exit_code = subprocess.call(command, cwd=project.path)

                if exit_code:
                    log.get_logger().warning(f'There was a problem adding remote {remote} in project {project.name}')

    return result


def call_commands(commands: List[str]) -> int:
    """
    Calls the commands given, waits for the result, and returns the exit code. Stdout and stderr are not redirected
    and are printed directly to the console. This also handles keyboard interrupts correctly.
    :param commands: The commands to run as arguments to subprocess.Popen
    :return: The exit code of the commands
    """
    with subprocess.Popen(commands) as process:
        try:
            exit_code = process.wait()
        except KeyboardInterrupt:
            # When a keyboard interrupt is sent, pass it onto the child and then still wait
            # If this occurs twice, the second will abort this process
            process.send_signal(signal.SIGINT)
            exit_code = process.wait()
    return exit_code
