"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import os
from typing import List, Optional

import docker
from docker.models.containers import Container
import pytest


import pydc_control


# Use a relative path to this script since sometimes IDEs mangle the working directory
BASE_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '../../sample_project'))
PROJECT_DEV_DIR = os.path.join(BASE_DIR, 'project-dev')
PROJECT_MULTIPLE_SERVICES_DIR = os.path.join(BASE_DIR, 'project-dc-template')
SAMPLE_CONTROL_BASE_DIR = os.path.join(BASE_DIR, 'sample-control')
# This should match what is stored as the key in the config.yml file
PROJECT_DC_TEMPLATE_NAME = 'project-dc-template'


def _run_control_commands(args: List[str], working_dir: Optional[str] = None) -> int:
    original_working_dir = os.getcwd()
    if working_dir:
        os.chdir(working_dir)
    exit_code = pydc_control.run(SAMPLE_CONTROL_BASE_DIR, args=args)
    if exit_code:
        raise Exception(f'Could not startup sample project due to exit code: {exit_code}')
    if working_dir:
        os.chdir(original_working_dir)
    return exit_code


def _get_pydc_containers(docker_client: docker.DockerClient) -> List[Container]:
    running_containers = docker_client.containers.list()
    return list(
        container for container in running_containers
        if container.name.startswith('pydc_') or container.name.startswith('pydcdev_')
    )


@pytest.fixture(name='docker_client')
def fixture_docker_client():
    return docker.from_env()


@pytest.fixture(autouse=True)
def fixture_cleanup():
    yield
    print('Cleaning up containers')
    _run_control_commands(['down'])


def test_up(docker_client):
    _run_control_commands(['up-detach'])
    containers = _get_pydc_containers(docker_client)
    assert len(containers) == 5
    assert {container.name for container in containers} == \
           {'pydc_core_core1', 'pydc_service1', 'pydc_service2', 'pydc_service3', 'pydc_service4'}
    assert all(container.status == 'running' for container in containers)


def test_dev(docker_client):
    _run_control_commands(['-p', PROJECT_DC_TEMPLATE_NAME, 'up-detach'], working_dir=PROJECT_DEV_DIR)
    containers = _get_pydc_containers(docker_client)
    assert len(containers) == 5
    assert {container.name for container in containers} == \
           {'pydc_core_core1', 'pydc_service1', 'pydc_service2', 'pydcdev_service3', 'pydcdev_service4'}
    assert all(container.status == 'running' for container in containers)


def test_enabled(docker_client):
    _run_control_commands(['--enable-core2', 'up-detach'])
    containers = _get_pydc_containers(docker_client)
    assert len(containers) == 6
    assert any(container.name == 'pydc_core_core2' for container in containers)
