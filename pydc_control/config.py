"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import os
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Union

import yaml

from .exceptions import KnownException


# Static vars
CONFIG_FILE = 'config.yml'
DOCKER_COMPOSE_TEMPLATE = 'docker-compose-template.yml'
DOCKER_COMPOSE_FILE = 'docker-compose.yml'
ENV_FILE = 'docker-compose.env'

# Global vars
_BASE_DIR = os.path.dirname(__file__)


def initialize(base_dir: str) -> None:
    """
    Sets the base dir for all further operations, this should be called first
    """
    # pylint: disable=global-statement
    global _BASE_DIR
    _BASE_DIR = base_dir


def get_base_dir() -> str:
    return _BASE_DIR


# The following methods are cached so that we only retrieve/validate them once (config cannot be changed mid-run)
@lru_cache()
def get_env_file_path() -> str:
    return os.path.join(_BASE_DIR, ENV_FILE)


@lru_cache()
def get_docker_compose_path() -> str:
    return os.path.join(_BASE_DIR, DOCKER_COMPOSE_FILE)


@lru_cache()
def _get_config() -> Dict[str, Any]:
    config_path = os.path.join(_BASE_DIR, CONFIG_FILE)
    if not os.path.exists(config_path):
        raise KnownException(f'Config file {config_path} does not exist, please copy and modify example')
    with open(config_path, 'r', encoding='utf8') as config_file:
        try:
            config = yaml.safe_load(config_file)
        except Exception:
            # pylint: disable=raise-missing-from
            raise KnownException(f'Config file {config_path} is not valid YAML, please copy and modify example')
    if not config:
        raise KnownException(f'Config file {config_path} is invalid, please copy and modify example')

    # Validate configuration
    prefixes = config.get('prefixes')
    if not prefixes or not prefixes.get('service') or not prefixes.get('core'):
        raise KnownException(
            f'Config file {config_path} has an invalid "prefixes" configuration, please see example'
        )
    dc_config = config.get('docker-compose')
    if not dc_config or not dc_config.get('network') or \
            not dc_config.get('project') or not dc_config.get('registry'):
        raise KnownException(
            f'Config file {config_path} has an invalid "docker-compose" configuration, please see example'
        )
    projects = config.get('projects')
    if not projects or not isinstance(projects, dict):
        raise KnownException(
            f'Config file {config_path} has an invalid "projects" configuration, please see example'
        )
    for project_name in projects:
        project_data = projects[project_name]
        # pylint: disable=too-many-boolean-expressions
        if not project_data or not isinstance(project_data, dict) or 'directory' not in project_data or \
                'repository' not in project_data or 'services' not in project_data or \
                not isinstance(project_data.get('services'), list):
            raise KnownException(
                f'Config file {config_path} has an invalid "projects.{project_name}" '
                f'configuration, please see example'
            )
        for service_data in project_data.get('services'):
            if not isinstance(service_data, dict) or 'name' not in service_data:
                raise KnownException(
                    f'Config file {config_path} has an invalid "projects.{project_name}.services" '
                    f'entry, please see example'
                )
    return config


def get_service_prefix(service_type: str = 'service') -> str:
    """
    Gets a prefix for the given service type.
    :param service_type: The service type, defaults to "service"
    :return: The service prefix, or none if not defined
    """
    return _get_config()['prefixes'].get(service_type)


def get_target_service(target_name: str, optional: bool = False) -> Optional[str]:
    """
    Gets a target service container name from the config.
    :param target_name: The target name
    :param optional: If true, no exception will be raised if the target service is not present or configured
    :return:
    """
    config = _get_config()
    if not config.get('target-services') or target_name not in config['target-services']:
        if optional:
            return None
        raise KnownException(f'Target service {target_name} is not defined, please define "target-services"')
    return config['target-services'][target_name]


def get_project_config() -> Dict[str, dict]:
    return _get_config()['projects']


def get_dc_project() -> str:
    return _get_config()['docker-compose'].get('project')


def get_dc_network() -> str:
    return _get_config()['docker-compose'].get('network')


def get_dc_build_args() -> Optional[Union[Dict[str, str], List[str]]]:
    return _get_config()['docker-compose'].get('build-args')


def get_required_options() -> Iterable[str]:
    return _get_config().get('required-options', [])


def get_tags() -> Iterable[str]:
    return _get_config()['docker-compose'].get('tags', ['latest'])


def get_registry(tag: str) -> str:
    dc_config = _get_config()['docker-compose']
    return dc_config.get('registries-by-tag', {}).get(tag, dc_config['registry'])


def get_dc_data() -> dict:
    dc_config = _get_config()['docker-compose']
    data = {}
    for key, value in dc_config.items():
        if key in ('build-args', 'tags', 'registries-by-tag', 'registry', 'project', 'network'):
            continue
        data[key] = value
    return data
