import logging
import json
import sys
import subprocess

from os.path import basename, dirname, join, exists

from six import iteritems

logger = logging.getLogger('binstar.conda')

WINDOWS = sys.platform.startswith('win')
CONDA_PREFIX = sys.prefix
BIN_DIR = 'Scripts' if WINDOWS else 'bin'
CONDA_EXE = join(CONDA_PREFIX, BIN_DIR, 'conda.exe' if WINDOWS else 'conda')
CONDA_BAT = join(CONDA_PREFIX, BIN_DIR, 'conda.bat')


class CondaException(Exception):
    pass


def _import_conda_root_dir():
    import conda.exports
    return conda.exports.root_dir


def _import_anaconda_config_conda_context():
    from conda.base.context import context
    return _adapt_conda_config(context.anaconda_default_site, context.anaconda_sites)


def _get_conda_exe():
    """Returns the conda executable according to the platform if exists, None otherwise."""
    command = CONDA_EXE

    if WINDOWS:
        command = CONDA_EXE if exists(CONDA_EXE) else CONDA_BAT

    if not exists(command):
        raise CondaException('Unable to find conda executable: %s', command)

    return command


def _execute_conda_command(conda_args):
    command = _get_conda_exe()
    logger.debug('Invoking conda with args: %s', conda_args)
    output = subprocess.check_output([command] + conda_args).decode("utf-8")
    return json.loads(output)


def _conda_root_from_conda_info():
    """Tries to get the conda root prefix from the output of conda info --json

    :return: The value of 'root_prefix' of the output of conda info --json if the call is
    successful or None otherwise.
    """
    conda_args = ['info', '--json']

    try:
        conda_info = _execute_conda_command(conda_args)
        return conda_info['root_prefix']
    except (ValueError, KeyError, subprocess.CalledProcessError, CondaException):
        logger.debug("Exception calling conda with args %s", conda_args, exc_info=True)
        return None


def _adapt_conda_config(anaconda_default_site, anaconda_sites):
    return dict(
        default_site=anaconda_default_site,
        sites={name: {'url': url} for name, url in iteritems(anaconda_sites)}
    )


def _anaconda_client_config_from_conda_config():
    conda_args = ['config', '--show', '--json']

    try:
        conda_config = _execute_conda_command(conda_args)
        return _adapt_conda_config(conda_config.get('anaconda_default_site', None),
                                   conda_config.get('anaconda_sites', {}))
    except (ValueError, KeyError, subprocess.CalledProcessError, CondaException):
        logger.debug("Exception calling conda with args %s", conda_args, exc_info=True)
        return None


def get_conda_root():
    """Get the root of the conda installation. The following methods are used (in order) to
    determine the correct output:

    * Import conda.exports and return conda.exports.root_dir
    * Look for 'envs' on the current sys.prefix and return the current environment root
    * Invoke conda info --json and parse the output

    If all methods fail, None is returned.

    :return: The root of the conda installation
    """
    try:
        # We're in the root environment
        conda_root = _import_conda_root_dir()
    except ImportError:
        logger.debug("Exception importing conda.exports", exc_info=True)

        # We're not in the root environment.
        envs_dir = dirname(CONDA_PREFIX)

        if basename(envs_dir) == 'envs':
            # We're in a named environment: `conda create -n <name>`
            conda_root = dirname(envs_dir)
        else:
            # We're in an isolated environment: `conda create -p <path>`
            # The only way we can find out is by calling conda.
            conda_root = _conda_root_from_conda_info()

    return conda_root


def get_anaconda_client_config():
    """Get the anaconda client config from the conda config back-end. The following methods are
    used (in order) to determine the correct output:

    * Import conda.base.context and adapt the values of 'anaconda_default_site' and
      'anaconda_sites'.
    * Invoke conda config --json and parse the output

    If all methods fail, None is returned.

    :return: A dictionary with the anaconda client config
    """

    try:
        anaconda_client_config = _import_anaconda_config_conda_context()
    except ImportError:
        logger.debug("Exception importing conda.base.context", exc_info=True)

        anaconda_client_config = _anaconda_client_config_from_conda_config()

    return anaconda_client_config
