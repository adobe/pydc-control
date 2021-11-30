# Python Docker Compose Control

This library can be used to control multiple docker compose-based projects in
a coordinated way, allowing you to start, stop, and developing on separate projects
as necessary.

This project was built from requirements at Adobe that arose when splitting a
monolith project into microservices. It simplifies this transition and makes it easy
to run multiple projects at the same time whether pulling from built/deployed
upstream docker images or developing using local code.


## Features

* Coordinates the execution of multiple docker compose projects in a 
  single network/namespace
* Start or stop an entire application, no matter the number of projects or
  docker-compose files, with a single command
* Extremely configurable, add your own commands and projects
* Integrates directly with docker compose, as long as you can use docker compose files,
  this project can control them
* Allows easy development of a single project or multiple projects at the same time
* Generate dynamic docker-compose files using Jinja templates for any number of projects


## Setup

### Application filesystem layout

This project assumes a flat directory layout for projects, with the control project
located in the same directory as all other projects. For example:


```
# Arbitrary directory containing all projects for an application,
# may also contain other directories/applications as well
my-app/
  # Control project, uses pydc_control
  app-control/
    # This is arbitrary, but recommended to be able to add to the path
    bin/
      # Control script - executable python script that uses pydc_control
      appctl
    # Configuration file used to build base docker-compose template
    config.yml
    # Environment variable configuration, symlinked to all projects automatically
    docker-compose.env
  # Arbitrary projects
  project1/
    # The only required file for a project is a docker-compose file
    docker-compose.yml
  project2/
    # A jinja-templated file may be used instead (see advanced features below)
    docker-compose-template.yml
  ...
```

### Determine configuration variables

Determine these variables up front:

* Docker network name (`mynetwork` in the examples below)
* Docker compose service and container prefix (`mynamespace_` in the examples below)
* Core service prefix (`core_` in the examples below)
* Docker compose project name (`myproject` in the examples below)
* Docker registry and tags that will be used for deployed containers

### Create a control project

Create a new project for your control project. It can be configured however you'd like,
but it should either have a script available on the path for easy execution or install
it into a local environment for easy execution.

#### Control script

Add a single python script to the project. Using naming such as `<app>ctl` is
recommended to make it easy to execute.

```python
#!/usr/bin/env python3

import os
import sys
import pydc_control


if __name__ == '__main__':
    # The base path is the location of your control project
    base_path = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
    # Run pydc_control, returns an exit code
    sys.exit(pydc_control.run(base_path))
```

#### Configuration file

Copy the `config.yml.example` file (or create your own) and add it to the control
project. **Every project** in your application should have an entry in the `projects`
list in this file, with one or more services (containers) attached to it. The syntax
is similar to a docker-compose file, but has a layer of abstraction to handle projects
with multiple services. This file will be used to generate the base docker compose
file during control script runs.

For services that have *no associated project*, for example, a MySQL or message bus
container, you can create an arbitrarily named project that has null values for the
`directory` and `repository` properties.

For projects that have *no associated services*, for example a project containing
static configuration, you can create a project with the `services` property set to
an empty list (`[]`).

Note that several settings near the top of the file are required.

#### Environment variables file

Copy the `docker-compose.env.example` file (or create your own) and add it to the
control project. *This file should be ignored by your VCS.*

Any environment variables defined here will be added automatically to any running
container (unless they define `env_file: []` in the configuration file).

### Setup projects

Each project that pydc control can own should contain **at least** a `docker-compose.yml`
file. The docker compose should be quite standard, but typically must contain at least
one service that is prefixed with the service/container prefix determined above and the
network as determined above. The service should also be attached to that network.

For example:

```
version: '3'

services:
  # This prefix MUST match the service prefix determined above
  mynamespace_ping:
    image: containous/whoami:latest
    ports:
    - "80"
    networks:
    - mynetwork

networks:
  mynetwork:
    external: true
```

#### Setup template projects

Projects with docker compose templates can add some variables that are pulled automatically from the config file:

```
version: '3'

services:
  {{ service_prefix }}_ping:
    image: containous/whoami:latest
    ports:
    - "80"
    networks:
    - {{ network }}

networks:
  {{ network }}:
    external: true
```


## Usage

**NOTE: All examples using `appctl` as the command is just an example. This script
may be named whatever you would like.**

To use your control script, simply add it to the PATH and call it from any directory.
The behavior changes based on the directory you are in:

* If called from a project directory (listed in `config.yml`), that project is assumed
  to be currently developed, meaning it is automatically added to the `-p` parameters
  in the control script. This will use the development docker-compose file from the
  project and all other containers from the generated base docker-compose in the control
  project (built from `config.yml`).
* If called from any other project directory (included the control project), it will
  only include the generated docker compose from the control project (built from
  `config.yml`). 

### Develop projects

To add more development projects besides the current project directory, simply use the
`-p` flag:

```
appctl -p project2 config
``` 
  
### Run docker compose commands

Most common docker compose commands have shortcuts added to the control script, with an
additional command that may be used to pass arbitrary commands to docker compose.

```
appctl config
appctl up
appctl up-detach
appctl down
appctl stop
appctl build
appctl pull
appctl docker-compose -- <additional docker compose args>
# Alias for docker-compose command
appctl dc -- <additional docker compose args>
# see appctl --help for all commands available
```

#### Container startup order

Services are started up using the following method:

* All services (containers) marked with `core: true` are started detached
* All open ports defined on the core services are checked to make sure they are open
* Any `wait-for-ports` (see below) are waited for via requests
* All services belonging to projects that are *not* being developed are started detached

  * Note: If no projects are being developed (see above), all services are started and
    are not detached.
     
* All developed project services are started and logs are displayed for *only* these
  services

The reason for the detached behavior for many of the containers is that they can run in the
background and are often not changed. Additionally, this prevents logs from showing up for them
in the console, which could cause extra noise when developing on only one or two projects.

If the control script process is interrupted (via Ctrl+C for example), the developed
project services are attempted to be stopped (and only these) so that they may be restarted
again. All of these operations and choices are to ensure the smoothest experience with
docker compose logs and interactions so that you can focus only on your developed projects.

### Perform VCS checkout, pull, status (git only) 

To checkout and/or update all projects listed in the `config.yml` automatically,
use the following command:

```
appctl checkout
# Alias
appctl co
```

To check the repository status for every project:

```
appctl repo-status
# Alias
appctl rs
``` 


## Advanced features

### Dynamically generating image references

While many image references can be hardcoded, it may be desirable to generate image
references based on specific tags or with specific registries based on those tags.
This can be done by using the `image_path` key in the service definition in
`config.yml` instead of `image`. The full image reference is generated from 3 pieces
of information:

* The image **path** defined in the `image_path` property for the the service
  in `config.yml`
* The tag defined on the command line of your control script (`-t`)

  * The full list of tags is defined in the `docker-compose.tags` property of the
    `config.yml` file.

* The `docker-compose.registry` property defined in `config.yml`

  * The `docker-compose.registries-by-tag` property may be used to override the registry
    based on the tag value.
    
The full image reference is of the form `<registry><path>:<tag>`.

### Templating docker-compose.yml

In order to use a template instead of a direct `docker-compose.yml` file in a project,
simply create a file named `docker-compose-template.yml` and then make sure that
`docker-compose.yml` file is ignored by your VCS since it will be regenerated on each
run of the control script. The template file is processed via Jinja and has several
variables available to it such as:

* `dev_project_names` - The names of the project currently under development
* `enabled_services` - The services that are marked as enabled and are currently enabled
* `tag` - The docker tag selected
* `registry` - The docker registry from the config file
* `network` - The docker network from the config file
* `core_prefix` - The prefix to use for core containers
* `service_prefix` - The prefix to use for service containers

### Making services enabled/disabled

Sometimes it is desirable to not start all services when starting up the application
with the control script, but be able to start these services when needed. For example,
a service that takes a lot of resources to run and is rarely used may not need to
be started every time, but when testing functionality involving the service, it
may be enabled explicitly.  Similarly, it may be desirable to be able to disable
specific services.

Simply add the `enable: true` or `disable: true` flags to your service definition in
`config.yml` to make the service disabled by default or enabled by default respectively.
Flags are added to the control script automatically based on the service name to
enable/disable the service.

For example, if a service needs to be disabled by default, in your `config.yml`:

```
projects:
  project1:
    ...
    service:
    - name: service1
      enable: true
      ...
```

This adds the `--enable-service1` flag to the control script automatically and prevents
the service from being included in docker compose otherwise.

If you would like to use the same behavior in development projects, use the `enabled_services`
dictionary in your `docker-compose-template.yml` file to tell if a service should be included
or not:

```
services:
  {%- if enabled_services.get('service1') %}
  mynamespace_service1:
    ...
  {%- endif %}
```

### Create your own control script commands

It is easy to create additional commands using pydc_control.

```python
#!/usr/bin/env python3

import argparse
import os
import sys

import pydc_control


def run_db_connect(args: argparse.Namespace):
    """
    Connects to the mongo my_db database running on "my_mongo_container"
    """
    pydc_control.call_commands(
        ['docker', 'exec', '-it', 'my_mongo_container', 'mongo', 'my_db']
    )
    return os.EX_OK


def configure_parsers(parser: argparse.ArgumentParser, commands_parser: argparse._SubParsersAction):
    # DB
    db_parser = commands_parser.add_parser(
        'db',
        help='Connects to the mongo database in an interactive shell',
    )
    db_parser.set_defaults(
        func=run_db_connect,
    )


if __name__ == '__main__':
    base_path = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
    sys.exit(pydc_control.run(base_path, configure_parsers))
```


## Frequently Asked Questions

### Why do we duplicate docker compose configuration between projects and the control config?

While it may seem like duplicated code/configuration, the docker compose files in each
project and the configuration file in the control project serve different purposes and
often look different:

* The configuration file in the control project should use a deployed (production or stage-like)
  docker image and configuration for the project. The code for each project is not dynamically
  modified and is usually promoted/deployed to environments outside of pydc-control.
* The docker compose file in the individual (developed) project should use a development
  build of the docker image with, ideally, application files and configuration mounted
  dynamically into the container so that development is seamless and immediate.
  Live-reloading should be used when available to speed development of a project.
