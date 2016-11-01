# =============================================================================
#
# Copyright (c)  2016, Cisco Systems
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
from functools import partial
import re
import pexpect
import logging

from base import Protocol

from condoor.fsm import FSM
from condoor.utils import pattern_to_str
from condoor.actions import a_send, a_send_line, a_send_password, a_authentication_error, a_unable_to_connect,\
    a_save_last_pattern, a_standby_console

from condoor.exceptions import ConnectionError, ConnectionTimeoutError

from os import getpid
logger = logging.getLogger("{}-{}".format(getpid(), __name__))


# Telnet connection initiated
ESCAPE_CHAR = "Escape character is|Open"
# Connection refused i.e. line busy on TS
CONNECTION_REFUSED = re.compile("Connection refused")
PASSWORD_OK = "[Pp]assword [Oo][Kk]"
AUTH_FAILED = "Authentication failed|not authorized|Login incorrect"


class Telnet(Protocol):
    def __init__(self, device):
        super(Telnet, self).__init__(device)

    def get_command(self):
        return "telnet {} {}".format(self.hostname, self.port)

    def connect(self, driver):
        #              0            1                              2                      3
        events = [ESCAPE_CHAR, driver.press_return_re, driver.standby_re, driver.username_re,
                  #            4                   5                  6                     7
                  driver.password_re, driver.more_re, self.device.prompt_re, driver.rommon_re,
                  #       8                              9              10            11
                  driver.unable_to_connect_re, driver.timeout_re, pexpect.TIMEOUT, PASSWORD_OK]

        transitions = [
            (ESCAPE_CHAR, [0], 1, None, 20),
            (driver.press_return_re, [0, 1], 1, partial(a_send, "\r\n"), 10),
            (PASSWORD_OK, [0, 1], 1, partial(a_send, "\r\n"), 10),
            (driver.standby_re, [0, 5], -1, partial(a_standby_console), 0),
            (driver.username_re, [0, 1, 5, 6], -1, partial(a_save_last_pattern, self), 0),
            (driver.password_re, [0, 1, 5], -1, partial(a_save_last_pattern, self), 0),
            (driver.more_re, [0, 5], 7, partial(a_send, "q"), 10),
            # router sends it again to delete
            (driver.more_re, [7], 8, None, 10),
            # (prompt, [0, 1, 5], 6, partial(a_send, "\r\n"), 10),
            (self.device.prompt_re, [0, 1, 5], 0, None, 10),
            (self.device.prompt_re, [6, 8, 5], -1, partial(a_save_last_pattern, self), 0),
            (driver.rommon_re, [0, 1, 5], -1, partial(a_save_last_pattern, self), 0),
            (driver.unable_to_connect_re, [0, 1], -1, a_unable_to_connect, 0),
            (driver.timeout_re, [0, 1], -1, ConnectionTimeoutError("Connection Timeout", self.hostname), 0),
            (pexpect.TIMEOUT, [0, 1], 5, partial(a_send, "\r\n"), 10),
            (pexpect.TIMEOUT, [5], -1, ConnectionTimeoutError("Connection timeout", self.hostname), 0)
        ]
        logger.debug("EXPECTED_PROMPT={}".format(pattern_to_str(self.device.prompt_re)))
        sm = FSM("TELNET-CONNECT", self.device, events, transitions, init_pattern=self.last_pattern)
        return sm.run()

    def authenticate(self, driver):
        #                      0                      1                    2                    3
        events = [driver.username_re, driver.password_re, self.device.prompt_re, driver.rommon_re,
                  #       4             5             6              7                8
                  driver.unable_to_connect_re, AUTH_FAILED, pexpect.TIMEOUT, pexpect.EOF]

        transitions = [
            (driver.username_re, [0], 1, partial(a_send_line, self.username), 10),
            (driver.username_re, [1], 1, None, 10),
            (driver.password_re, [0, 1], 2, partial(a_send_password, self._acquire_password()), 20),
            (driver.username_re, [2], -1, a_authentication_error, 0),
            (driver.password_re, [2], -1, a_authentication_error, 0),
            (self.device.prompt_re, [0, 1, 2], -1, None, 0),
            (driver.rommon_re, [0], -1, partial(a_send, "\r\n"), 0),
            (pexpect.TIMEOUT, [0], 1, partial(a_send, "\r\n"), 10),
            (pexpect.TIMEOUT, [2], -1, None, 0),
            (AUTH_FAILED, [2], -1, a_authentication_error, 0),
            (pexpect.TIMEOUT, [3, 7], -1, ConnectionTimeoutError("Connection Timeout", self.hostname), 0),
            (driver.unable_to_connect_re, [0, 1, 2], -1, a_unable_to_connect, 0),
        ]
        logger.debug("EXPECTED_PROMPT={}".format(pattern_to_str(self.device.prompt_re)))
        sm = FSM("TELNET-AUTH", self.device, events, transitions, init_pattern=self.last_pattern)
        self.try_read_prompt(1)
        return sm.run()

    def disconnect(self):
        # self.ctrl.sendcontrol(']')
        # self.ctrl.sendline('quit')
        self.ctrl.send(chr(4))


class TelnetConsole(Telnet):
    def connect(self, driver):
        #              0            1                    2                      3
        events = [ESCAPE_CHAR, driver.press_return_re, driver.standby_re, driver.username_re,
                  #            4                   5            6                     7
                  driver.password_re, driver.more_re, self.device.prompt_re, driver.rommon_re,
                  #       8                           9              10             11
                  driver.unable_to_connect_re, driver.timeout_re, pexpect.TIMEOUT, PASSWORD_OK]

        transitions = [
            (ESCAPE_CHAR, [0], 1, partial(a_send, "\r\n"), 20),
            (driver.press_return_re, [0, 1], 1, partial(a_send, "\r\n"), 10),
            (PASSWORD_OK, [0, 1], 1, partial(a_send, "\r\n"), 10),
            (driver.standby_re, [0, 5], -1, ConnectionError("Standby console", self.hostname), 0),
            (driver.username_re, [0, 1, 5, 6], -1, partial(a_save_last_pattern, self), 0),
            (driver.password_re, [0, 1, 5], -1, partial(a_save_last_pattern, self), 0),
            (driver.more_re, [0, 5], 7, partial(a_send, "q"), 10),
            # router sends it again to delete
            (driver.more_re, [7], 8, None, 10),
            # (prompt, [0, 1, 5], 6, partial(a_send, "\r\n"), 10),
            (self.device.prompt_re, [0, 1, 5], 0, None, 10),
            (self.device.prompt_re, [6, 8, 5], -1, partial(a_save_last_pattern, self), 0),
            (driver.rommon_re, [0, 1, 5], -1, partial(a_save_last_pattern, self), 0),
            (driver.unable_to_connect_re, [0, 1], -1, a_unable_to_connect, 0),
            (driver.timeout_re, [0, 1], -1, ConnectionTimeoutError("Connection Timeout", self.hostname), 0),
            (pexpect.TIMEOUT, [0, 1], 5, partial(a_send, "\r\n"), 10),
            (pexpect.TIMEOUT, [5], -1, ConnectionTimeoutError("Connection timeout", self.hostname), 0)
        ]
        logger.debug("EXPECTED_PROMPT={}".format(pattern_to_str(self.device.prompt_re)))
        sm = FSM("TELNET-CONNECT-CONSOLE", self.device, events, transitions, init_pattern=self.last_pattern)
        return sm.run()
