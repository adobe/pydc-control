"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import os
from typing import Callable, List

from . import cli, config, docker_utils, log
from .exceptions import KnownException
from .data import Project, Service

from .commands import call_commands


def _detect_current_project(dev_project_names: List[str]) -> None:
    dir_name = os.path.basename(os.getcwd())
    base_dir_name = os.path.basename(config.get_base_dir())
    if dir_name != base_dir_name:
        for project in Project.find_all():
            if project.directory == dir_name and project.name not in dev_project_names:
                log.get_logger().info(f'Assuming development for project {project.name}')
                dev_project_names.append(project.name)


def run(base_dir: str, configure_parsers: Callable = None) -> int:
    """
    Runs the CLI control command, including parsing arguments, etc.
    :param base_dir: The base directory of the control project
    :param configure_parsers: An optional method to configure additional parameters or arguments on the parser.
                              It receives two arguments, the top-level parser and the subparser for commands.
    :return: The exit code
    """
    # Initialize config based on the base dir
    config.initialize(base_dir)

    args = cli.parse_args(configure_parsers)

    # Initialize logging
    log.init_logger(args.debug)

    _detect_current_project(args.dev_project_names)
    errno = cli.validate_args(args)
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
