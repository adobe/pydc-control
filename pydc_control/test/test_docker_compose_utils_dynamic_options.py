"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""
# pylint: disable=protected-access

import argparse
import os
from typing import List
from unittest import mock

import pytest

from pydc_control import docker_compose_utils

from . import fixture_cleanup_caches, fixture_temp_dir, write_config


_ = fixture_cleanup_caches, fixture_temp_dir


def _get_docker_compose_env_path(temp_dir: str) -> str:
    return os.path.join(temp_dir, "docker-compose.env")


@pytest.mark.usefixtures("cleanup_caches")
@pytest.fixture(autouse=True)
def fixture_setup_project(temp_dir):
    # Create docker compose file
    with open(_get_docker_compose_env_path(temp_dir), "w", encoding="utf8") as fobj:
        fobj.write("ENV_VAR1=val1\n")

    # Write config file
    write_config(
        temp_dir,
        {
            "projects": {
                "project-dynamic-options": {
                    "directory": "project-dynamic-options",
                    "repository": "repo1",
                    "services": [
                        {
                            "name": "dyn1",
                            "enable": True,
                            "image": "containous/whoami:latest",
                            "dynamic-options": {
                                "DYNAMIC1_BOTH": {
                                    "enabled": "enabled",
                                    "disabled": "disabled",
                                },
                                "DYNAMIC1_ENABLED": {
                                    "enabled": "enabled",
                                    # Test empty values
                                    "disabled": "",
                                },
                                "DYNAMIC1_DISABLED": {
                                    "disabled": "disabled",
                                },
                            },
                        },
                        {
                            "name": "dyn2",
                            "enable": True,
                            "image": "containous/whoami:latest",
                            "dynamic-options": {
                                "DYNAMIC2_BOTH": {
                                    "enabled": "enabled",
                                    "disabled": "disabled",
                                },
                                "DYNAMIC2_ENABLED": {
                                    "enabled": "enabled",
                                },
                                "DYNAMIC2_DISABLED": {
                                    # Test empty values
                                    "enabled": "",
                                    "disabled": "disabled",
                                },
                            },
                        },
                        {
                            "name": "dyn3",
                            "disable": True,
                            "image": "containous/whoami:latest",
                            "dynamic-options": {
                                "DYNAMIC3_BOTH": {
                                    "enabled": "enabled",
                                    "disabled": "disabled",
                                },
                                "DYNAMIC3_ENABLED": {
                                    "enabled": "enabled",
                                },
                                "DYNAMIC3_DISABLED": {
                                    "disabled": "disabled",
                                },
                            },
                        },
                    ],
                }
            }
        },
    )


def _get_env_lines(temp_dir: str) -> List[str]:
    with open(_get_docker_compose_env_path(temp_dir), encoding="utf8") as fobj:
        return fobj.read().splitlines()


def _get_args(
    enable_dyn1: bool = False, enable_dyn2: bool = False, disable_dyn3: bool = False
) -> argparse.Namespace:
    namespace = mock.create_autospec(argparse.Namespace)
    namespace.enable_dyn1 = enable_dyn1
    namespace.enable_dyn2 = enable_dyn2
    namespace.disable_dyn3 = disable_dyn3
    return namespace


def test_defaults(temp_dir):
    docker_compose_utils._set_dynamic_options(_get_args())
    assert _get_env_lines(temp_dir) == [
        "ENV_VAR1=val1",
        "DYNAMIC1_BOTH=disabled",
        "DYNAMIC1_DISABLED=disabled",
        "DYNAMIC2_BOTH=disabled",
        "DYNAMIC2_DISABLED=disabled",
        "DYNAMIC3_BOTH=enabled",
        "DYNAMIC3_ENABLED=enabled",
    ]


def test_none_enabled(temp_dir):
    docker_compose_utils._set_dynamic_options(_get_args(disable_dyn3=True))
    assert _get_env_lines(temp_dir) == [
        "ENV_VAR1=val1",
        "DYNAMIC1_BOTH=disabled",
        "DYNAMIC1_DISABLED=disabled",
        "DYNAMIC2_BOTH=disabled",
        "DYNAMIC2_DISABLED=disabled",
        "DYNAMIC3_BOTH=disabled",
        "DYNAMIC3_DISABLED=disabled",
    ]


def test_dyn1_enabled(temp_dir):
    docker_compose_utils._set_dynamic_options(_get_args(enable_dyn1=True))
    assert _get_env_lines(temp_dir) == [
        "ENV_VAR1=val1",
        "DYNAMIC1_BOTH=enabled",
        "DYNAMIC1_ENABLED=enabled",
        "DYNAMIC2_BOTH=disabled",
        "DYNAMIC2_DISABLED=disabled",
        "DYNAMIC3_BOTH=enabled",
        "DYNAMIC3_ENABLED=enabled",
    ]


def test_dyn2_enabled_dyn3_disabled(temp_dir):
    docker_compose_utils._set_dynamic_options(
        _get_args(enable_dyn2=True, disable_dyn3=True)
    )
    assert _get_env_lines(temp_dir) == [
        "ENV_VAR1=val1",
        "DYNAMIC1_BOTH=disabled",
        "DYNAMIC1_DISABLED=disabled",
        "DYNAMIC2_BOTH=enabled",
        "DYNAMIC2_ENABLED=enabled",
        "DYNAMIC3_BOTH=disabled",
        "DYNAMIC3_DISABLED=disabled",
    ]


def test_consistent_output(temp_dir):
    # Ensures that multiple runs of setting dynamic options doesn't change anything
    docker_compose_utils._set_dynamic_options(_get_args())
    env_lines = _get_env_lines(temp_dir)
    docker_compose_utils._set_dynamic_options(_get_args())
    assert env_lines == _get_env_lines(temp_dir)
