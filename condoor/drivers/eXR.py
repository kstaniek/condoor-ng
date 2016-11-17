"""This is IOS XR 64 bit driver implementation."""

from functools import partial
import logging
import pexpect

from condoor.exceptions import CommandSyntaxError, CommandTimeoutError, ConnectionError
from condoor.actions import a_connection_closed, a_expected_prompt, a_stays_connected, a_unexpected_prompt, a_send, \
    a_store_cmd_result
from condoor.utils import pattern_to_str
from condoor.fsm import FSM
from condoor.drivers.generic import Driver as Generic
from condoor import pattern_manager

logger = logging.getLogger(__name__)


class Driver(Generic):
    """This is a Driver class implementation for IOS XR 64 bit."""

    platform = 'eXR'
    inventory_cmd = 'admin show inventory chassis'
    users_cmd = 'show users'
    target_prompt_components = ['prompt_dynamic', 'prompt_default', 'rommon', 'xml']
    prepare_terminal_session = ['terminal exec prompt no-timestamp', 'terminal len 0', 'terminal width 0']
    families = {
        "ASR9K": "ASR9K",
        "ASR-9": "ASR9K",
        "ASR9": "ASR9K",
        "NCS-6": "NCS6K",
        "NCS-4": "NCS4K",
        "NCS-50": "NCS5K",
        "NCS-55": "NCS5500",
        "NCS1": "NCS1K",
        "NCS-1": "NCS1K",
    }

    def __init__(self, device):
        """Initialize the XR 64 bit Driver object."""
        super(Driver, self).__init__(device)
        self.calvados_re = pattern_manager.pattern(self.platform, 'calvados')
        self.calvados_connect_re = pattern_manager.pattern(self.platform, 'calvados_connect')
        self.calvados_term_length = pattern_manager.pattern(self.platform, 'calvados_term_length')

    def get_version_text(self):
        """Return version information text."""
        version_text = self.device.send("show version", timeout=120)
        return version_text

    def update_driver(self, prompt):
        """Return driver name based on prompt analysis."""
        logger.debug(prompt)
        platform = pattern_manager.platform(prompt)
        # to avoid the XR platform detection as eXR and XR prompts are the same
        if platform == 'XR':
            platform = 'eXR'

        if platform:
            logger.debug('{} -> {}'.format(self.platform, platform))
            return platform
        else:
            logger.debug('No update: {}'.format(self.platform))
            return self.platform

    def wait_for_string(self, expected_string, timeout=60):
        """Wait for string FSM for XR 64 bit."""
        # Big thanks to calvados developers for make this FSM such complex ;-)
        #                    0                         1                        2                        3
        events = [self.syntax_error_re, self.connection_closed_re, expected_string, self.press_return_re,
                  #        4           5                 6                7               8
                  self.more_re, pexpect.TIMEOUT, pexpect.EOF, self.calvados_re, self.calvados_connect_re,
                  #     9
                  self.calvados_term_length]

        # add detected prompts chain
        events += self.device.get_previous_prompts()  # without target prompt

        llogger.debug("Expecting: {}".format(pattern_to_str(expected_string)))


        transitions = [
            (self.syntax_error_re, [0], -1, CommandSyntaxError("Command unknown", self.device.hostname), 0),
            (self.connection_closed_re, [0], 1, a_connection_closed, 10),
            (pexpect.TIMEOUT, [0, 2], -1, CommandTimeoutError("Timeout waiting for prompt", self.device.hostname), 0),
            (pexpect.EOF, [0, 1], -1, ConnectionError("Unexpected device disconnect", self.device.hostname), 0),
            (self.more_re, [0], 0, partial(a_send, " "), 10),
            (expected_string, [0, 1], -1, a_expected_prompt, 0),
            (self.calvados_re, [0], -1, a_expected_prompt, 0),
            (self.press_return_re, [0], -1, a_stays_connected, 0),
            (self.calvados_connect_re, [0], 2, None, 0),
            # admin command to switch to calvados
            (self.calvados_re, [2], 3, None, 1),
            # getting the prompt only
            (pexpect.TIMEOUT, [3], 0, partial(a_send, "\r"), 0),
            # term len
            (self.calvados_term_length, [3], 4, None, 0),
            # ignore for command start
            (self.calvados_re, [4], 5, None, 0),
            # ignore for command start
            (self.calvados_re, [5], 0, a_store_cmd_result, 0),
        ]

        for prompt in self.device.get_previous_prompts():
            transitions.append((prompt, [0, 1], 0, a_unexpected_prompt, 0))

        fsm = FSM("WAIT-4-STRING", self.device, events, transitions, timeout=timeout)
        return fsm.run()
