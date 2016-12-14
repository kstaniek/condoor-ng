"""This is IOS XRv driver implementation."""

from functools import partial
import re
import logging
from condoor.drivers.XR import Driver as XR
from condoor import TIMEOUT, EOF, ConnectionAuthenticationError, ConnectionError
from condoor.fsm import FSM
from condoor.actions import a_reload_na, a_send, a_send_boot

logger = logging.getLogger(__name__)


class Driver(XR):
    """This is a Driver class implementation for IOS XRv"""

    platform = 'XRv'
    inventory_cmd = 'admin show inventory chassis'
    users_cmd = 'show users'
    target_prompt_components = ['prompt_dynamic', 'prompt_default', 'rommon', 'xml']
    prepare_terminal_session = ['terminal exec prompt no-timestamp', 'terminal len 0', 'terminal width 0']
    reload_cmd = 'admin reload location all'
    families = {
        "XRv": "IOS-XRv",
    }

    def reload(self, reload_timeout, save_config):
        """Reload the device."""

        PROCEED = re.compile(re.escape("Proceed with reload? [confirm]"))
        DONE = re.compile(re.escape("[Done]"))
        CONFIGURATION_COMPLETED = re.compile("SYSTEM CONFIGURATION COMPLETED")
        CONFIGURATION_IN_PROCESS = re.compile("SYSTEM CONFIGURATION IN PROCESS")
        CONSOLE = re.compile("ios con[0|1]/RS?P[0-1]/CPU0 is now available")
        RECONFIGURE_USERNAME_PROMPT = "[Nn][Oo] root-system username is configured"

        RELOAD_NA = re.compile("Reload to the ROM monitor disallowed from a telnet line")
        #           0          1      2                3                   4                  5
        events = [RELOAD_NA, DONE, PROCEED, CONFIGURATION_IN_PROCESS, self.rommon_re, self.press_return_re,
                  #   6               7                       8                     9      10
                  CONSOLE, CONFIGURATION_COMPLETED, RECONFIGURE_USERNAME_PROMPT, TIMEOUT, EOF]

        transitions = [
            (RELOAD_NA, [0], -1, a_reload_na, 0),
            (DONE, [0], 1, None, 120),
            (PROCEED, [1], 3, partial(a_send, "\r"), reload_timeout),
            (self.rommon_re, [0, 3], 4, a_send_boot("boot"), 600),

            # here must be authentication
            (CONSOLE, [3, 4], 5, None, 600),
            (self.press_return_re, [5], 6, partial(a_send, "\r"), 300),
            # if asks for username/password reconfiguration, go to success state and let plugin handle the rest.
            (RECONFIGURE_USERNAME_PROMPT, [6, 7], -1, None, 0),
            (CONFIGURATION_IN_PROCESS, [6], 7, None, 180),
            (CONFIGURATION_COMPLETED, [7], -1, self._return_and_authenticate, 0),

            (TIMEOUT, [0, 1, 2], -1,
             ConnectionAuthenticationError("Unable to reload", self.hostname), 0),
            (EOF, [0, 1, 2, 3, 4, 5], -1,
             ConnectionError("Device disconnected", self.hostname), 0),
            (TIMEOUT, [6], 7, self._send_line, 180),
            (TIMEOUT, [7], -1,
             ConnectionAuthenticationError("Unable to reconnect after reloading", self.hostname), 0),
        ]

        fsm = FSM("RELOAD", self.device, events, transitions, timeout=300)
        return fsm.run()
