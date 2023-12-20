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

from pydc_control import config, data


def _clear_caches():
    data.Project.find_all.cache_clear()
    config.get_env_file_path.cache_clear()
    config.get_docker_compose_path.cache_clear()
    config._get_config.cache_clear()


@pytest.fixture(autouse=True)
def fixture_cleanup_caches():
    _clear_caches()
    yield
    _clear_caches()


@pytest.fixture(name="temp_dir")
def fixture_temp_dir():
    with tempfile.TemporaryDirectory(prefix="pydc-control-test-") as temp_dir:
        config.initialize(temp_dir)
        yield temp_dir


def write_config(temp_dir: str, write_data: dict) -> None:
    config_data = {
        "prefixes": {
            "service": "mynamespace_",
            "core": "core_",
        },
        "docker-compose": {
            "project": "project1",
            "network": "project1",
            "tags": ["latest"],
            "registry": "registry1",
        },
    }
    config_data.update(write_data)
    with open(os.path.join(temp_dir, "config.yml"), "w", encoding="utf8") as fobj:
        yaml.safe_dump(config_data, fobj)
