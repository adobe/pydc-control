"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""
# pylint: disable=protected-access

import os
import tempfile

import pytest
import yaml

from pydc_control import data, config, exceptions


@pytest.fixture(name='temp_dir')
def fixture_temp_dir():
    with tempfile.TemporaryDirectory(prefix='pydc-control-test-') as temp_dir:
        config.set_base_dir(temp_dir)
        yield temp_dir


@pytest.fixture(autouse=True)
def fixture_cleanup():
    yield
    data._PROJECTS = None
    config.CONFIG = None


def _write_config(temp_dir: str, write_data: dict) -> None:
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
    config_data.update(write_data)
    with open(os.path.join(temp_dir, 'config.yml'), 'w', encoding='utf8') as fobj:
        yaml.safe_dump(config_data, fobj)


def test_no_projects(temp_dir):
    _write_config(temp_dir, {
        'projects': {},
    })
    with pytest.raises(exceptions.KnownException):
        data.Project.find_all()


def test_project_no_services(temp_dir):
    _write_config(temp_dir, {
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


def test_projects_with_services(temp_dir):
    _write_config(temp_dir, {
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
