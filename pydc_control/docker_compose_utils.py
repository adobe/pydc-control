"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import argparse
import os
from typing import List

import jinja2
import yaml

from . import config, docker_utils, log
from .data import Project, Service
from .exceptions import KnownException


def _check_required_options():
    log.get_logger().info(f'Validating config file ({config.ENV_FILE})')
    if not os.path.exists(config.get_env_file_path()):
        raise KnownException(f'Please create {config.get_env_file_path()} containing env vars for project config, '
                             f'this will be used to configure each project. The {config.ENV_FILE}.example '
                             'file may be used as a template')
    with open(config.get_env_file_path(), 'r', encoding='utf8') as fobj:
        contents = fobj.read()
    required_options = config.get_required_options()
    for option in required_options:
        if option not in contents:
            raise KnownException(f'The {config.get_env_file_path()} file must include the {option} option')


def _check_project_directories(projects: List[Project]) -> None:
    if len(projects) == 0:
        log.get_logger().debug('No projects specified, not validating directories')
        return
    log.get_logger().info(f'Validating directories are present for {len(projects)} projects(s)')
    for project in projects:
        if not os.path.exists(project.path) or not os.path.isdir(project.path):
            raise KnownException(f'No directory found for the "{project.name}" project at {project.path}, '
                                 'please check the repository')


def _set_dynamic_options(args: argparse.Namespace) -> None:
    # pylint: disable=too-many-branches

    with open(config.get_env_file_path(), 'r', encoding='utf8') as fobj:
        env_file_contents = fobj.read()
    new_contents = []
    lines_changed = False

    enabled_status_by_service = {}
    services_by_dynamic_option = {}
    for service in Service.find_all():
        enabled_status_by_service[service.name] = service.is_enabled(args)
        for option in service.dynamic_options.keys():
            services_by_dynamic_option[option] = service
    dynamic_options_seen = {}
    for option in services_by_dynamic_option:
        dynamic_options_seen[option] = False

    for line in env_file_contents.splitlines():
        option_considered = False
        for option, service in services_by_dynamic_option.items():
            if not line.startswith(f'{option}='):
                continue
            option_considered = True
            dynamic_options_seen[option] = True
            if enabled_status_by_service.get(service.name, True):
                value = service.dynamic_options[option].get('enabled')
            else:
                value = service.dynamic_options[option].get('disabled')

            if value:
                new_line = f'{option}={value}'
                if line != new_line:
                    log.get_logger().info(f'Replacing dynamic option for {option} in {config.ENV_FILE} with {value}')
                    lines_changed = True
                else:
                    log.get_logger().info(f'Keeping existing dynamic option for {option} in {config.ENV_FILE}')
                new_contents.append(new_line)
            else:
                log.get_logger().info(f'Removing dynamic option for {option} in {config.ENV_FILE}')
                lines_changed = True

        # If no dynamic options are in the line, append it
        if not option_considered:
            new_contents.append(line)

    for option, service in services_by_dynamic_option.items():
        if not dynamic_options_seen[option]:
            if enabled_status_by_service.get(service.name, True):
                value = service.dynamic_options[option].get('enabled')
            else:
                value = service.dynamic_options[option].get('disabled')
            if value:
                log.get_logger().info(f'Adding dynamic option for {option} in {config.ENV_FILE} with value {value}')
                new_contents.append(f'{option}={value}')
                lines_changed = True

    if lines_changed:
        with open(config.get_env_file_path(), 'w', encoding='utf8') as fobj:
            fobj.write('\n'.join(new_contents))


def _link_config(projects: List[Project]):
    if len(projects) == 0:
        log.get_logger().debug(f'No projects specified, not linking {config.ENV_FILE}')
        return
    log.get_logger().info(f'Linking base {config.ENV_FILE} to {len(projects)} projects(s)')
    for project in projects:
        env_project_path = os.path.join(project.path, config.ENV_FILE)
        if not os.path.exists(env_project_path):
            os.symlink(config.get_env_file_path(), env_project_path)
        elif os.path.islink(env_project_path):
            # nothing to do if it already exists
            pass
        else:
            os.remove(env_project_path)
            os.symlink(config.get_env_file_path(), env_project_path)
        log.get_logger().debug(f'Linked in {project.path}')


def _render_docker_compose_file(project_dir, template_config):
    if not os.path.exists(os.path.join(project_dir, config.DOCKER_COMPOSE_TEMPLATE)):
        log.get_logger().debug(
            f'No {config.DOCKER_COMPOSE_TEMPLATE} detected in the {project_dir} directory, skipping generation'
        )
        return
    try:
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(project_dir))
        template = env.get_template(config.DOCKER_COMPOSE_TEMPLATE)
        output = template.render(**template_config)
        with open(os.path.join(project_dir, config.DOCKER_COMPOSE_FILE), 'w', encoding='utf8') as fobj:
            fobj.write(output)
    except jinja2.exceptions.TemplateSyntaxError as exc:
        # pylint: disable=raise-missing-from
        raise KnownException(
            f'Could not render {project_dir}/{config.DOCKER_COMPOSE_TEMPLATE}: {exc.message} on line {exc.lineno}'
        )


def _generate_docker_compose(args: argparse.Namespace, dev_projects: List[Project], tag: str):
    registry = config.get_registry(tag)
    log.get_logger().info(f'Generating docker-compose.yml with {len(dev_projects)} project(s) and tag "{tag}"')

    services = {}
    dev_project_names = list(project.name for project in dev_projects)
    projects = Project.find_all()

    enabled_services = {}
    for project in projects:
        for service in project.services:
            enabled_services[service.name] = service.is_enabled(args)

    for project in projects:
        if project.name in dev_project_names:
            continue
        for service in project.services:
            if not enabled_services.get(service.name):
                continue
            data = service.get_dc_data(registry, tag)
            # Add env file and network dynamically
            if 'env_file' not in data:
                data['env_file'] = [f'./{config.ENV_FILE}']
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
    with open(config.get_docker_compose_path(), 'w', encoding='utf8') as fobj:
        yaml.safe_dump(docker_compose_data, fobj)

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


def init_docker_compose(args: argparse.Namespace, dev_projects: List[Project], no_network: bool = False) -> None:
    if not no_network:
        docker_utils.check_docker_network()
    _check_project_directories(dev_projects)
    _check_required_options()
    _set_dynamic_options(args)
    _link_config(dev_projects)
    _generate_docker_compose(args, dev_projects, args.tag)
