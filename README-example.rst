.. note::
    This readme may be used in any project that utilizes pydc-control to provide setup instructions
    and to ease project setup. Just replace ``appctl`` with the name of your control script and
    remove this note.

Requirements
############

The following software needs to be configured/installed on your machine prior to using
this project.

* `Docker <https://www.docker.com/>`_ must be installed on your machine and the ``docker-compose`` command must
  be available from the command line.
* The ``git`` command must be available if using Git repositories and ``appctl`` will be used for cloning them.
* `uv <https://github.com/astral-sh/uv>`_ is highly recommended to manage virtualenvs and python versions. 
  If using ``uv``, ensure that the ``uv`` command is available from the command line.
* If ``uv`` is not used, the ``pydc-control`` module must be installed in your current Python environment.
  This may be done by running ``pip install pydc-control``.

Project setup
#############

In order to get started, clone this repository and put it in a directory where you want the rest of the projects to
be cloned. Add the ``appctl`` script (or rather, the directory containing it) to your ``PATH`` environment variable.
For example, add ``export PATH="$PATH:/my-control-project/bin`` to the startup scripts for your shell (e.g.
``.zcshrc`` or ``.bashrc``).

Copy the ``docker-compose.env.example`` file to ``docker-compose.env`` (or create your own) and follow the instructions
in the file to setup your local environment variables, including secrets. **This file should be ignored by your VCS.**
Any environment variables defined here will be added automatically to any running containers (unless they define 
``env_file: []`` in the configuration file).

Run the following command to see the sub-commands available:

.. code-block:: console

    appctl --help

Cloning projects
================

.. note::
    This section applies to Git-based projects only. You may also clone each project individually as long as they
    are setup with the correct paths in the ``config.yml`` file. Typically this means your cloned repositories
    should live in the same directory as this repository.

The following command may be used to clone all projects listed in the ``config.yml`` file:

.. code-block:: console

    appctl checkout -a

If you are using GitHub forks where the ``origin`` remote is your fork and ``upstream`` is the source repository, you
may use the following command to clone the projects and add the ``origin`` remote:

.. code-block:: console

    appctl checkout -a -e <fork-namespace> origin

The ``<fork-namespace>`` should be the namespace or user where your forks live. For example, if the repository is
located at ```https://github.com/adobe/repo1`` and your fork lives at ``https://github.com/bob/repo1``, then you would
run the following command:

.. code-block:: console

    appctl checkout -a -e bob origin

This will clone all of the projects and also add an ``origin`` remote pointing at your fork. This greatly simplifies
project setup and development no matter the number of projects involved. Note that this does not actually create the
forks for you. You will need to fork each project as you develop it. This simply adds the Git remote that points at
your fork's (future) location.

Starting up the application
===========================

The ``appctl`` script can be thought of as a wrapper around the ``docker-compose`` command. Therefore, most of the
sub-commands available in ``docker-compose`` are natively available in ``appctl``. Any other command may be used
using the ``appctl dc`` subcommand.

However, the behavior of ``appctl`` changes based on the directory you are in and what projects you are currently
working on, i.e. "developing". If you are in a project directory, ``appctl`` will automatically assume you are
"developing" on the project and that it should use the local docker compose file and code. Additional projects
may be developed by using the ``-p`` flag to any ``appctl`` commands. Any projects not being developed will use the
configuration in the ``config.yml`` file instead of the local repository.

Without developed projects
~~~~~~~~~~~~~~~~~~~~~~~~~~

First, it may be useful to start up the application locally without developing on any projects by staying in this
repository and then running ``appctl up``. This will bring all of the application's containers up and will make the
local development environment available. Ensure that everything is working before moving on to developing on projects.

With developed projects
~~~~~~~~~~~~~~~~~~~~~~~

Change your directory to the project you are currently developing. Optionally, add the ``-p`` flag to develop on
additional projects as defined in the ``config.yml`` file in this repository. Run ``appctl up``. Your local code
should then be used instead of the upstream/production/stage/latest version for the current directory (and any
additional projects that you specified).
