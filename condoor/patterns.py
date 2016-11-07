"""Provides the PatternManager class."""

import os
import re
import yaml


class PatternManager(object):
    """Provides API to patterns defined externally."""

    def __init__(self, pattern_dict):
        """Initialize PatternManager object."""
        self._dict = pattern_dict
        # self._dict_compiled = self._compile_patterns()

    def _compile_patterns(self):
        dict_compiled = {}
        for platform, patterns in self._dict.items():
            dict_compiled[platform] = {}
            for key, pattern in patterns.items():
                try:
                    compiled = None
                    if isinstance(pattern, str):
                        compiled = re.compile(pattern)
                    elif isinstance(pattern, dict):
                        compiled = re.compile(pattern['pattern'])
                    if compiled:
                        dict_compiled[platform][key] = compiled

                except re.error as e:
                    raise RuntimeError("Pattern compile error: {} ({}:{})".format(e.message, platform, key))

        return dict_compiled

    def _get_platform_patterns(self, platform):

        patterns = self._dict.get(platform, None)

        if patterns is None:
            raise KeyError("Unknown platform: {}".format(platform))

        generic_patterns = self._dict.get('generic', None)

        if generic_patterns is None:
            raise RuntimeError("Patterns database corrupted. Platform: {}".format(platform))

        return patterns, generic_patterns

    def _get_all_patterns(self, key, compiled=True):
        # get of unique list of platforms
        patterns = set()
        platforms = list(set([platform for platform in self._dict.keys() if platform is not None]))
        for platform in platforms:
            try:
                patterns |= set(self.get_pattern(platform, key, compiled=False).split('|'))
            except KeyError:
                continue

        if not patterns:
            raise KeyError("Pattern not found: {}".format(key))

        patterns_re = "|".join(list(patterns))

        if compiled:
            return re.compile(patterns_re)
        else:
            return patterns_re

    def get_pattern(self, platform, key, compiled=True):
        """Return the pattern defined by the key string specific to the platform.

        :param platform:
        :param key:
        :param compiled:
        :return: Pattern string or RE object.
        """
        patterns, generic_patterns = self._get_platform_patterns(platform)
        pattern = patterns.get(key, generic_patterns.get(key, None))

        if isinstance(pattern, dict):
            pattern = pattern.get('pattern', None)

        # list of references to other platforms
        if isinstance(pattern, list):
            pattern_set = set()
            for platform in pattern:
                try:
                    pattern_set |= set(self.get_pattern(platform, key, compiled=False).split('|'))
                except KeyError:
                    continue
            pattern = "|".join(pattern_set)

        if pattern is None:
            raise KeyError("Patterns database corrupted. Platform: {}, Key: {}".format(platform, key))

        if compiled:
            return re.compile(pattern)
        else:
            return pattern

    def get_pattern_description(self, platform, key):
        """Return the patter description."""
        patterns, generic_patterns = self._get_platform_patterns(platform)
        pattern = patterns.get(key, generic_patterns.get(key, None))
        if isinstance(pattern, dict):
            description = pattern.get('description', None)
        else:
            description = key

        return description

    def get_platform_based_on_prompt(self, prompt):
        """Return the platform name based on the prompt matching."""
        platforms = self._dict['generic']['prompt_detection']
        for platform in platforms:
            pattern = self.get_pattern(platform, 'prompt')
            result = re.search(pattern, prompt)
            if result:
                return platform
        return None


class YPatternManager(PatternManager):
    """Yaml version of pattern manager."""

    def __init__(self, config_file_path=None):
        """Initialize the pattern manager object."""
        if config_file_path is None:
            script_name = os.path.splitext(__file__)[0]
            # try user config path first
            config_file_path = os.path.join(os.path.expanduser("~"), ".condoor", script_name + '.yaml')
            if not os.path.exists(config_file_path):
                # try module config path (assuming it always exists)
                config_file_path = os.path.splitext(os.path.abspath(__file__))[0] + '.yaml'

                config_file_path = os.getenv(script_name.upper() + '_CFG', config_file_path)

        if not os.path.exists(config_file_path):
            raise RuntimeError("Pattern Config file does not exits: {}".format(config_file_path))

        pattern_dict = self._read_config(config_file_path)
        super(YPatternManager, self).__init__(pattern_dict=pattern_dict)

    def _read_config(self, config_file_path):
        config = {}
        with open(config_file_path, 'r') as ymlfile:
            config = yaml.load(ymlfile)

        return config

# ypm = YPatternManager()
# print(ypm.get_platform_based_on_prompt('[sysadmin-vm:0_RSP0:~]$'))
# print(ypm.get_platform_based_on_prompt('sysadmin-vm:0_RSP0#'))

# print(ypm.get_pattern("generic", "syntax_error", compiled=False))
# print(ypm.get_pattern("generic", "syntax_error").pattern)

# print(ypm._get_all_patterns('rommon').pattern)

# print(ypm._get_all_patterns('rommon', compiled=False))

# print(ypm._get_all_patterns('dupa'))

# print(ypm.get_pattern("XR", "connection_closed", compiled=False))
# print(ypm.get_pattern("XR", "standby_console", compiled=False))
