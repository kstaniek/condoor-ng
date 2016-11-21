"""Provides the condoor configuration."""

import os
from utils import yaml_file_to_dict


class Config(object):
    """Provides the interface to the configuration file."""

    def __init__(self, config_dict):
        """Initialize config object."""
        self._dict = config_dict


class YConfig(Config):
    """Yamal configuration file interface."""

    def __init__(self):
        """Initialize the pattern manager object."""
        script_name = os.path.splitext(__file__)[0]
        path = os.path.abspath('./')
        super(YConfig, self).__init__(config_dict=yaml_file_to_dict(script_name, path))


config = YConfig()
print(config._dict)
