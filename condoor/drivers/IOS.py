# =============================================================================
#
# Copyright (c) 2016, Cisco Systems
# All rights reserved.
#
# # Author: Klaudiusz Staniek
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
# Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.
# =============================================================================

from os import getpid
import re
import pexpect
import logging
from functools import partial

from condoor.drivers.generic import Driver as Generic
from condoor.actions import a_send_password, a_expected_prompt, a_send_line, a_send, a_disconnect
from condoor.exceptions import ConnectionAuthenticationError, ConnectionError
from condoor.fsm import FSM

logger = logging.getLogger("{}-{}".format(getpid(), __name__))


class Driver(Generic):
    platform = 'IOS'
    inventory_cmd = 'show inventory'
    users_cmd = 'show users'
    enable_cmd = 'enable'
    reload_cmd = 'reload'
    target_prompt_components = ['prompt_dynamic', 'prompt_default', 'rommon']
    prepare_terminal_session = ['terminal len 0', 'terminal width 0']
    families = {
        'A9': 'ASR900',
    }

    def __init__(self, device):
        super(Driver, self).__init__(device)

    def get_version_text(self):
        version_text = self.device.send("show version", timeout=120)
        return version_text

    def enable(self, enable_password):
        if self.device.prompt[-1] == '#':
            logger.debug("Device is already in privileged mode")
            return

        events = [self.password_re, self.device.prompt_re, pexpect.TIMEOUT, pexpect.EOF]
        transitions = [
            (self.password_re, [0], 1, partial(a_send_password, enable_password), 10),
            (self.password_re, [1], -1, ConnectionAuthenticationError("Incorrect enable password",
                                                                      self.device.hostname), 0),
            (self.device.prompt_re, [0, 1, 2, 3], -1, a_expected_prompt, 0),
            (pexpect.TIMEOUT, [0, 1, 2], -1, ConnectionAuthenticationError("Unable to get privileged mode",
                                                                           self.device.hostname), 0),
            (pexpect.EOF, [0, 1, 2], -1, ConnectionError("Device disconnected"), 0)
        ]
        self.device.ctrl.send_command(self.enable_cmd)
        fsm = FSM("IOS-ENABLE", self.device, events, transitions, timeout=10, max_transitions=5)
        fsm.run()
        if self.device.prompt[-1] != '#':
            raise ConnectionAuthenticationError("Privileged mode not set", self.device.hostname)

    def reload(self, reload_timeout=300, save_config=True):
        """
        CSM_DUT#reload

        System configuration has been modified. Save? [yes/no]: yes
        Building configuration...
        [OK]
        Proceed with reload? [confirm]
        """
        SAVE_CONFIG = re.compile(re.escape("System configuration has been modified. Save? [yes/no]: "))
        PROCEED = re.compile(re.escape("Proceed with reload? [confirm]"))

        response = "yes" if save_config else "no"

        events = [SAVE_CONFIG, PROCEED, pexpect.TIMEOUT, pexpect.EOF]

        transitions = [
            (SAVE_CONFIG, [0], 1, partial(a_send_line, response), 60),
            (PROCEED, [0, 1], 2, partial(a_send, "\r"), 10),
            # if timeout try to send the reload command again
            (pexpect.TIMEOUT, [0], 0, partial(a_send_line, self.reload_cmd), 10),
            (pexpect.TIMEOUT, [2], -1, a_disconnect, 0),
            (pexpect.EOF, [0, 1, 2], -1, a_disconnect, 0)
        ]
        fsm = FSM("IOS-RELOAD", self.device, events, transitions, timeout=10, max_transitions=5)
        fsm.run()
