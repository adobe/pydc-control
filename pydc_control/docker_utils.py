"""
Copyright 2021 Adobe
All Rights Reserved.

NOTICE: Adobe permits you to use, modify, and distribute this file in accordance
with the terms of the Adobe license agreement accompanying it.
"""

import contextlib
import re
import socket
import subprocess
import time

import requests
import yaml

from . import config, log


def check_docker_network():
    log.get_logger().debug(f'Checking for docker network {config.get_dc_network()}')
    exit_code = subprocess.call(
        ['docker', 'network', 'inspect', config.get_dc_network()],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if exit_code:
        log.get_logger().info(f'Creating docker network {config.get_dc_network()}')
        subprocess.check_call(
            ['docker', 'network', 'create', config.get_dc_network()],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )


def get_open_ports(container_name):
    """
    Retrieves the open ports on a container.
    :param container_name:
    :return: The open ports as a dictionary of container ports to host ports
    """
    try:
        lines = subprocess.check_output(['docker', 'port', container_name]).splitlines()
        ports = {}
        for line in lines:
            match = re.match(r'^(\d+)/tcp -> 0.0.0.0:(\d+)$', line.strip().decode('utf-8'))
            if not match:
                continue
            ports[int(match.group(1))] = int(match.group(2))
        return ports
    except subprocess.CalledProcessError:
        log.get_logger().warning(
            f'Could not find open ports for {container_name}, please ensure it is configured correctly'
        )
        return []


def is_port_open(port):
    """
    Checks if the port is open on localhost by creating a socket connection to it.
    :param port: The port as a number
    :return: True if open, false otherwise
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(('127.0.0.1', port)) == 0


def _is_path_responding(port: int, path: str) -> bool:
    with contextlib.suppress(Exception):
        return requests.get(f'http://localhost:{port}{path}').status_code == 200


def check_port(container_name: str, port: int, path: str) -> None:
    total_time = 0.1
    while not _is_path_responding(port, path):
        message = f'Container {container_name} is not yet up, sleeping...'
        if (total_time % 3) == 0:
            log.get_logger().info(message)
        else:
            log.get_logger().debug(message)
        total_time += 0.1
        time.sleep(0.1)


def read_services_from_dc(docker_compose_path: str):
    with open(docker_compose_path, encoding='utf8') as fobj:
        data = yaml.safe_load(fobj)
        services = data.get('services', {})
        return services.keys()
