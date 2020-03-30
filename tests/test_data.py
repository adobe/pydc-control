
import os
import pytest
import shutil
import tempfile
import yaml

from pydc_control import data, config, exceptions


class TestData:
    def setup_method(self):
        self.base_dir = tempfile.mkdtemp('-test-pydc-data')
        config.set_base_dir(self.base_dir)

    def teardown_method(self):
        shutil.rmtree(self.base_dir)
        data._PROJECTS = None
        config.CONFIG = None

    def _write_config(self, data):
        config_data = {
            'prefixes': {
                'service': 'mynamespace_',
                'core': 'core_',
            },
            'docker-compose': {
                'project': 'project1',
                'network': 'project1',
                'tags': ['latest'],
                'registry': 'registry1',
            },
        }
        config_data.update(data)
        with open(os.path.join(self.base_dir, 'config.yml'), 'w') as fobj:
            yaml.safe_dump(config_data, fobj)

    def test_no_projects(self):
        self._write_config({
            'projects': {},
        })
        with pytest.raises(exceptions.KnownException):
            data.Project.find_all()

    def test_project_no_services(self):
        self._write_config({
            'projects': {
                'project1': {
                    'directory': 'project1',
                    'repository': 'repo1',
                    'services': [],
                },
            },
        })
        projects = data.Project.find_all()
        assert len(projects) == 1
        assert projects[0].name == 'project1'
        assert len(projects[0].services) == 0

    def test_projects_with_services(self):
        self._write_config({
            'projects': {
                'project1': {
                    'directory': 'project1',
                    'repository': 'repo1',
                    'services': [
                        {
                            'name': 'service1',
                        },
                        {
                            'name': 'service2',
                        },
                    ],
                },
                'project2': {
                    'directory': 'project2',
                    'repository': 'repo2',
                    'services': [
                        {
                            'name': 'service3',
                        },
                    ],
                },
            },
        })
        projects = data.Project.find_all()
        assert len(projects) == 2
        assert projects[0].name == 'project1'
        assert len(projects[0].services) == 2
        assert projects[0].services[0].name == 'service1'
        assert projects[0].services[1].name == 'service2'
        assert projects[1].name == 'project2'
        assert len(projects[1].services) == 1
        assert projects[1].services[0].name == 'service3'
