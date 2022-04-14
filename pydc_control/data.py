"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""
import argparse
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

from .config import get_base_dir, get_project_config, get_service_prefix, get_target_service
from .exceptions import KnownException


class Service:
    def __init__(self, project_name: str, data: dict):
        self.project_name = project_name
        self.data = data

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.name == other.name and self.project_name == other.project_name

    def __hash__(self):
        return hash(f'{self.project_name}{self.name}')

    @property
    def name(self):
        return self.data.get('name')

    @property
    def container_name(self):
        """
        The actual container name.
        """
        prefix = get_service_prefix('core' if self.core else 'service')
        return f'{prefix}{self.data.get("name")}'

    @property
    def dc_name(self):
        """
        The name according to docker compose.
        """
        return self.container_name

    @property
    def enable_flag(self) -> Union[str, bool]:
        flag_value = self.data.get('enable', False)
        return flag_value if flag_value else bool(flag_value)

    @property
    def disable_flag(self) -> Union[str, bool]:
        flag_value = self.data.get('disable', False)
        return flag_value if flag_value else bool(flag_value)

    @property
    def core(self) -> bool:
        return bool(self.data.get('core', False))

    @property
    def dynamic_options(self) -> Dict[str, Dict[str, Optional[str]]]:
        return self.data.get('dynamic-options', {})

    @property
    def wait_for_ports(self) -> Dict[int, str]:
        return self.data.get('wait-for-ports', {})

    def get_dc_data(self, registry: str, tag: str) -> Dict[str, Any]:
        data = {
            # Always add container name
            'container_name': self.container_name,
        }
        for key, value in self.data.items():
            # Ignore some keys
            if key in ('name', 'core', 'enable', 'disable', 'dynamic-options', 'wait-for-ports'):
                continue
            if key == 'image_path':
                # Interpolate image path
                data['image'] = f'{registry}{value}:{tag}'
            else:
                # All other values are a pass-through to docker-compose
                data[key] = value
        return data

    def _get_flag_name(self, flag_value: Union[str, bool], prefix: str) -> str:
        if isinstance(flag_value, str):
            return f'{prefix}_{flag_value}'
        return f'{prefix}_{self.name}'

    def _get_flag_value(
        self,
        args: argparse.Namespace,
        flag_value: Union[str, bool],
        prefix: str,
        reverse: bool = False,
    ) -> bool:
        if not flag_value:
            return False
        arg_value = getattr(args, self._get_flag_name(flag_value, prefix), False)
        return (arg_value and not reverse) or (not arg_value and reverse)

    def is_enabled(self, args: argparse.Namespace) -> bool:
        """
        Retrieves if the service is enabled or not (regardless if it is an enabled or disabled service).
        :param args: the argparse parsed args, used to determine enabled/disabled status
        :return: true if the service is not flagged enable/disable or it is enabled
        """
        # Services that are not enable-able or disable-able are always considered enabled
        if not self.enable_flag and not self.disable_flag:
            return True
        is_enabled = self._get_flag_value(args, self.enable_flag, 'enable')
        is_not_disabled = self._get_flag_value(args, self.disable_flag, 'disable', reverse=True)
        return is_enabled or is_not_disabled

    @classmethod
    def find_all(cls, core=None) -> List['Service']:
        services = []
        for project in Project.find_all():
            if core is None:
                services.extend(project.services)
            else:
                services.extend(service for service in project.services if core == service.core)
        return services

    @classmethod
    def find_one(cls, name: str) -> Optional['Service']:
        for service in cls.find_all():
            if service.name == name:
                return service
        return None

    @classmethod
    def find_config(cls) -> Optional['Service']:
        target_service = get_target_service('config', optional=True)
        if not target_service:
            return None
        return cls.find_one(target_service)

    @classmethod
    def find_has_enable_flag(cls) -> List['Service']:
        services = []
        for project in Project.find_all():
            services.extend(service for service in project.services if service.enable_flag)
        return services

    @classmethod
    def find_has_disable_flag(cls) -> List['Service']:
        services = []
        for project in Project.find_all():
            services.extend(service for service in project.services if service.disable_flag)
        return services


class Project:
    def __init__(self, name: str, data: Dict[str, Any]):
        self.name = name
        self.data = data

    @property
    def services(self) -> List[Service]:
        return list(Service(self.name, service) for service in self.data.get('services', []))

    @property
    def directory(self) -> Optional[str]:
        return self.data.get('directory')

    @property
    def repository(self) -> Optional[str]:
        return self.data.get('repository')

    @property
    def path(self) -> str:
        if not self.directory:
            raise KnownException(f'Project {self.name} does not have a directory, cannot get a path for it')
        return os.path.realpath(os.path.join(get_base_dir(), '..', self.directory))

    @classmethod
    @lru_cache()
    def find_all(cls) -> List['Project']:
        project_config = get_project_config()
        return list(Project(name, data) for name, data in project_config.items())

    @classmethod
    def find_one(cls, name: str) -> Optional['Project']:
        for project in cls.find_all():
            if project.name == name:
                return project
        return None
