"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""
# pylint: disable=protected-access

import pytest

from pydc_control import data, cli, exceptions
from . import fixture_cleanup_caches, fixture_temp_dir, write_config


_ = fixture_cleanup_caches, fixture_temp_dir


def test_no_projects(temp_dir):
    write_config(temp_dir, {
        'projects': {},
    })
    with pytest.raises(exceptions.KnownException):
        data.Project.find_all()


def test_project_no_services(temp_dir):
    write_config(temp_dir, {
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
    write_config(temp_dir, {
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


@pytest.mark.parametrize('service_name, argv, result', [
    ('no-flags', [], True),
    ('enabled', [], False),
    ('enabled', ['--enable-enabled'], True),
    ('disabled', [], True),
    ('disabled', ['--disable-disabled'], False),
    ('enabled-proxy', [], False),
    ('enabled-proxy', ['--enable-enabled'], True),
    ('disabled-proxy', [], True),
    ('disabled-proxy', ['--disable-disabled'], False),
])
def test_is_enabled(service_name, argv, result, temp_dir):
    write_config(temp_dir, {
        'projects': {
            'project1': {
                'directory': None,
                'repository': None,
                'services': [
                    {
                        'name': 'no-flags',
                    },
                    {
                        'name': 'enabled',
                        'enable': 1,
                    },
                    {
                        'name': 'disabled',
                        'disable': True,
                    },
                ],
            },
            'project2': {
                'directory': None,
                'repository': None,
                'services': [
                    {
                        'name': 'enabled-proxy',
                        'enable': 'enabled',
                    },
                    {
                        'name': 'disabled-proxy',
                        'disable': 'disabled',
                    },
                ],
            }
        }
    })
    args = cli._parse_args(None, argv)
    service = data.Service.find_one(service_name)
    assert service.is_enabled(args) is result
