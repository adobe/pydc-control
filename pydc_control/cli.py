"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import argparse
import os
from typing import Callable, List, Optional, Sequence

from . import commands, config, log
from .data import Project, Service
from .exceptions import KnownException


def _get_print_help_func(parser):
    # pylint: disable=unused-argument
    def print_help(args: argparse.Namespace):
        parser.print_help()
        return os.EX_OK

    return print_help


def _parse_args(configure_parsers: Optional[Callable], args: Optional[Sequence[str]]) -> argparse.Namespace:
    # pylint: disable=too-many-locals

    # Get all projects defined in the configuration
    projects = Project.find_all()

    # Parse arguments
    parser = argparse.ArgumentParser(
        description='Coordinates running projects and services through docker compose.',
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
    for service in Service.find_has_enable_flag():
        parser.add_argument(
            f"--enable-{service.name.replace('_', '-')}",
            dest=f"enable_{service.name}",
            action="store_true",
            help=f"Enables the optional {service.name} service from the {service.project_name} "
                 f"project, disabled by default",
        )
    for service in Service.find_has_disable_flag():
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
        func=commands.run_checkout,
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
        help='gets the status of the repos associated with this control script'
    )
    repo_status_parser.set_defaults(
        func=commands.get_repo_status,
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
        func=commands.run_dc_init,
    )

    # Docker compose
    dc_parser = subparsers.add_parser(
        'docker-compose',
        aliases=['dc'],
        help='Generates docker-compose templates, copies configuration, and runs any docker-compose command'
    )
    dc_parser.set_defaults(
        func=commands.run_docker_compose,
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
        func=commands.run_dc_build,
    )
    config_parser = subparsers.add_parser(
        'config',
        help='Alias for the "dc config" command'
    )
    config_parser.set_defaults(
        func=commands.run_dc_config,
    )
    down_parser = subparsers.add_parser(
        'down',
        help='Alias for the "dc down" command'
    )
    down_parser.set_defaults(
        func=commands.run_dc_down,
    )
    pull_parser = subparsers.add_parser(
        'pull',
        help='Alias for the "dc pull" command'
    )
    pull_parser.set_defaults(
        func=commands.run_dc_pull,
    )
    rm_parser = subparsers.add_parser(
        'rm',
        help='Alias for the "dc rm --force" command'
    )
    rm_parser.set_defaults(
        func=commands.run_dc_rm,
    )
    stop_parser = subparsers.add_parser(
        'stop',
        help='Alias for the "dc stop" command'
    )
    stop_parser.set_defaults(
        func=commands.run_dc_stop,
    )
    up_parser = subparsers.add_parser(
        'up',
        help='Alias for the "dc up" command'
    )
    up_parser.set_defaults(
        func=commands.run_dc_up,
    )
    up_detach_parser = subparsers.add_parser(
        'up-detach',
        help='Alias for the "dc up --detach" command'
    )
    up_detach_parser.set_defaults(
        func=commands.run_dc_up_detach,
    )
    up_recreate_parser = subparsers.add_parser(
        'up-recreate',
        help='Alias for the "dc up --force-recreate" command'
    )
    up_recreate_parser.set_defaults(
        func=commands.run_dc_up_recreate,
    )

    # Do not allow to pull configuration unless there is a project for config
    config_service_target = Service.find_config()
    if config_service_target:
        pull_config_parser = subparsers.add_parser(
            'pull-config',
            help='Alias for the "dc pull" command'
        )
        pull_config_parser.set_defaults(
            func=commands.run_dc_pull_config,
        )

    if configure_parsers:
        configure_parsers(parser, subparsers)

    # Parse arguments
    return parser.parse_args(args)


def _validate_args(args: argparse.Namespace) -> int:
    """
    Validates command line arguments for situations that are too complex for argparse.
    When this is called, all developed projects must already be added.
    :param args: the CLI arguments parsed by argparse
    :return: the exit code (or 0 on successful validation)
    """
    # Configure extra remotes
    if 'extra_remotes' in args.__dict__ and len(args.extra_remotes) > 0:
        for remote in args.extra_remotes:
            if len(remote) > 2 or len(remote) < 1:
                log.get_logger().error(
                    'extra remotes parameters must take either 1 or 2 parameters for each specification.'
                )
                log.get_logger().error('example : -e origin bob')
                log.get_logger().error(
                    '      where origin is the remote name and bob is the space the repo is forked in'
                )
                return os.EX_USAGE

    # Make sure the config service is not disabled at the same time it is being developed
    config_service_target = Service.find_config()
    # pylint: disable=too-many-boolean-expressions
    if config_service_target and config_service_target.project_name in args.dev_project_names and \
            not config_service_target.is_enabled(args):
        log.get_logger().error(
            f'To use the config service, you must not be developing on the '
            f'{config_service_target.project_name} project.'
        )
        return os.EX_USAGE
    return os.EX_OK


def _detect_current_project(dev_project_names: List[str]) -> None:
    dir_name = os.path.basename(os.getcwd())
    base_dir_name = os.path.basename(config.get_base_dir())
    if dir_name != base_dir_name:
        for project in Project.find_all():
            if project.directory == dir_name and project.name not in dev_project_names:
                log.get_logger().info(f'Assuming development for project {project.name}')
                dev_project_names.append(project.name)


def run(base_dir: str, configure_parsers: Callable = None, args: Optional[Sequence[str]] = None) -> int:
    """
    Runs the CLI control command, including parsing arguments, etc.
    :param base_dir: The base directory of the control project
    :param configure_parsers: An optional method to configure additional parameters or arguments on the parser.
                              It receives two arguments, the top-level parser and the subparser for commands.
    :param args: Optional arguments to use instead of sys.argv.
    :return: The exit code
    """
    # Initialize config based on the base dir
    config.initialize(base_dir)

    args = _parse_args(configure_parsers, args)

    # Initialize logging
    log.init_logger(args.debug)

    _detect_current_project(args.dev_project_names)
    errno = _validate_args(args)
    if errno:
        return errno

    try:
        return args.func(args)
    except KnownException as exc:
        log.get_logger().error(str(exc))
        return os.EX_SOFTWARE
    except Exception as exc:  # pylint:disable=broad-except
        log.get_logger().error(f'Encountered an unexpected failure ({exc.__class__}): {exc}')
        if args.debug:
            raise
        return os.EX_SOFTWARE
