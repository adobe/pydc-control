import os
import yaml
from typing import Any, Dict, Iterable, List, Optional, Union

from .exceptions import KnownException


# Static vars
CONFIG_FILE = 'config.yml'

# Global vars
BASE_DIR = None
CONFIG_PATH = None
CONFIG: Dict[str, Any] = None


def set_base_dir(base_dir: str) -> None:
    """
    Sets the base dir for all further operations, this should be called first
    """
    global BASE_DIR, CONFIG_PATH
    BASE_DIR = base_dir
    CONFIG_PATH = os.path.join(BASE_DIR, CONFIG_FILE)


def get_base_dir() -> Optional[str]:
    return BASE_DIR


def _get_config() -> Dict[str, Any]:
    global CONFIG
    if not CONFIG:
        if not os.path.exists(CONFIG_PATH):
            raise KnownException(f'Config file {CONFIG_PATH} does not exist, please copy and modify example')
        with open(CONFIG_PATH, 'r') as config_file:
            try:
                CONFIG = yaml.safe_load(config_file)
            except Exception as e:
                raise KnownException(f'Config file {CONFIG_PATH} is not valid YAML, please copy and modify example')
        if not CONFIG:
            raise KnownException(f'Config file {CONFIG_PATH} is invalid, please copy and modify example')

        # Validate configuration
        prefixes = CONFIG.get('prefixes')
        if not prefixes or not prefixes.get('service') or not prefixes.get('core'):
            raise KnownException(
                f'Config file {CONFIG_PATH} has an invalid "prefixes" configuration, please see example'
            )
        dc = CONFIG.get('docker-compose')
        if not dc or not dc.get('network') or not dc.get('project') or not dc.get('registry'):
            raise KnownException(
                f'Config file {CONFIG_PATH} has an invalid "docker-compose" configuration, please see example'
            )
        projects = CONFIG.get('projects')
        if not projects or not isinstance(projects, dict):
            raise KnownException(
                f'Config file {CONFIG_PATH} has an invalid "projects" configuration, please see example'
            )
        for project_name in projects:
            project_data = projects[project_name]
            if not project_data or not isinstance(project_data, dict) or 'directory' not in project_data or \
                    'repository' not in project_data or 'services' not in project_data or \
                    not isinstance(project_data.get('services'), list):
                raise KnownException(
                    f'Config file {CONFIG_PATH} has an invalid "projects.{project_name}" '
                    f'configuration, please see example'
                )
            for service_data in project_data.get('services'):
                if not isinstance(service_data, dict) or 'name' not in service_data:
                    raise KnownException(
                        f'Config file {CONFIG_PATH} has an invalid "projects.{project_name}.services" '
                        f'entry, please see example'
                    )
    return CONFIG


def get_service_prefix(service_type: str = 'service') -> str:
    """
    Gets a prefix for the given service type.
    :param service_type: The service type, defaults to "service"
    :return: The service prefix, or none if not defined
    """
    return _get_config()['prefixes'].get(service_type)


def get_target_service(target_name: str) -> str:
    """
    Gets a target service container name from the config.
    :param target_name: The target name
    :return:
    """
    config = _get_config()
    if not config['target-services'] or target_name not in config['target-services']:
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
