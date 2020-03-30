
import os
from typing import Any, Dict, List, Optional

from .config import get_base_dir, get_project_config, get_service_prefix
from .exceptions import KnownException


_PROJECTS = None


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
    def enable(self) -> bool:
        return not not self.data.get('enable', False)

    @property
    def disable(self) -> bool:
        return not not self.data.get('disable', False)

    @property
    def core(self) -> bool:
        return not not self.data.get('core', False)

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
    def find_enabled(cls) -> List['Service']:
        services = []
        for project in Project.find_all():
            services.extend(service for service in project.services if service.enable)
        return services

    @classmethod
    def find_disabled(cls) -> List['Service']:
        services = []
        for project in Project.find_all():
            services.extend(service for service in project.services if service.disable)
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
    def find_all(cls) -> List['Project']:
        global _PROJECTS
        if not _PROJECTS:
            project_config = get_project_config()
            _PROJECTS = list(Project(name, data) for name, data in project_config.items())
        return _PROJECTS

    @classmethod
    def find_one(cls, name: str) -> Optional['Project']:
        for project in cls.find_all():
            if project.name == name:
                return project
        return None

