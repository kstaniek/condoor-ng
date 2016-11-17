"""This is IOS XR Classic driver implementation."""

import re
import logging
from condoor.drivers.generic import Driver as Generic
from condoor import pattern_manager

logger = logging.getLogger(__name__)


class Driver(Generic):
    """This is a Driver class implementation for IOS XR Classic."""

    platform = 'XR'
    inventory_cmd = 'admin show inventory chassis'
    users_cmd = 'show users'
    target_prompt_components = ['prompt_dynamic', 'prompt_default', 'rommon', 'xml']
    prepare_terminal_session = ['terminal exec prompt no-timestamp', 'terminal len 0', 'terminal width 0']
    reload_cmd = 'admin reload location all'
    families = {
        "ASR9K": "ASR9K",
        "ASR-9": "ASR9K",
        "CRS": "CRS",
    }

    def __init__(self, device):
        """Initialize the IOS XR Classic driver object."""
        super(Driver, self).__init__(device)

    def reload(self, reload_timeout, save_config):
        """Reload the device."""
        pass

        # PROCEED = re.compile(re.escape("Proceed with reload? [confirm]"))
        # DONE = re.compile(re.escape("[Done]"))
        # CONFIGURATION_COMPLETED = re.compile("SYSTEM CONFIGURATION COMPLETED")
        # CONFIGURATION_IN_PROCESS = re.compile("SYSTEM CONFIGURATION IN PROCESS")
        # CONSOLE = re.compile("ios con[0|1]/RS?P[0-1]/CPU0 is now available")
        # RECONFIGURE_USERNAME_PROMPT = "[Nn][Oo] root-system username is configured"
        #
        # RELOAD_NA = re.compile("Reload to the ROM monitor disallowed from a telnet line")
        #
        # events = [RELOAD_NA, RELOAD, DONE, PROCEED, CONFIGURATION_IN_PROCESS, self.rommon_prompt, self.press_return,
        #           CONSOLE, CONFIGURATION_COMPLETED, RECONFIGURE_USERNAME_PROMPT,
        #           pexpect.TIMEOUT, pexpect.EOF]
        #
        # transitions_shared = [
        #     # here must be authentication
        #     (CONSOLE, [3, 4], 5, None, 600),
        #     (self.press_return_re, [5], 6, self._send_lf, 300),
        #     # if asks for username/password reconfiguration, go to success state and let plugin handle the rest.
        #     (RECONFIGURE_USERNAME_PROMPT, [6, 7], -1, None, 0),
        #     (CONFIGURATION_IN_PROCESS, [6], 7, None, 180),
        #     (CONFIGURATION_COMPLETED, [7], -1, self._return_and_authenticate, 0),
        #
        #     (pexpect.TIMEOUT, [0, 1, 2], -1,
        #      ConnectionAuthenticationError("Unable to reload", self.hostname), 0),
        #     (pexpect.EOF, [0, 1, 2, 3, 4, 5], -1,
        #      ConnectionError("Device disconnected", self.hostname), 0),
        #     (pexpect.TIMEOUT, [6], 7, self._send_line, 180),
        #     (pexpect.TIMEOUT, [7], -1,
        #      ConnectionAuthenticationError("Unable to reconnect after reloading", self.hostname), 0),
        # ]
        #
        #
        # self.ctrl.sendline(RELOAD)
        # transitions = [
        #                   # Preparing system for backup. This may take a few minutes especially for large configurations.
        #                   (RELOAD, [0], 1, self._send_lf, 300),
        #                   (RELOAD_NA, [1], -1, self._reload_na, 0),
        #                   (DONE, [1], 2, None, 120),
        #                   (PROCEED, [2], 3, self._send_lf, reload_timeout),
        #                   (self.rommon_prompt, [0, 3], 4, self._send_boot, 600),
        #               ] + transitions_shared
        #
        # fsm = FSM("RELOAD", self.device, events, transitions, timeout=10)
        # return fsm.run()
