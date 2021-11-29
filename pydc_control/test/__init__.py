"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""
# pylint: disable=protected-access

import pytest

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
