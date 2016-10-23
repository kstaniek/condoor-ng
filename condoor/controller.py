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

import logging
import pexpect

from utils import delegate
from condoor.exceptions import ConnectionError, ConnectionTimeoutError

from os import getpid
logger = logging.getLogger("{}-{}".format(getpid(), __name__))


# Delegate following methods to _session class
@delegate("_session", ("expect", "expect_exact", "sendline",
                       "isalive", "sendcontrol", "send", "read_nonblocking", "setecho"))
class Controller(object):
    def __init__(self, connection):
        # delegated pexpect session
        self._session = None
        self._connection = connection

        self._logfile_fd = connection.session_fd
        self.connected = False
        self.authenticated = False
        self.hostname = 'ctrl-hostname'
        self.last_hop = 0

    def spawn_session(self, device):

        protocol = device.protocol
        command = protocol.get_command()

        logger.debug("Executing command: '{}'".format(command))
        if self._session and self.isalive():
            try:
                self.send(command)
                self.expect_exact(command, timeout=20)
                self.sendline()

            except pexpect.EOF:
                raise ConnectionError("Connection error", self.hostname)
            except pexpect.TIMEOUT:
                raise ConnectionTimeoutError("Timeout", self.hostname)

        else:
            try:
                self._session = pexpect.spawn(
                    command,
                    maxread=50000,
                    searchwindowsize=None,
                    env={"TERM": "VT100"},  # to avoid color control charactes
                    echo=True  # KEEP YOUR DIRTY HANDS OFF FROM ECHO!
                )
                rows, cols = self._session.getwinsize()
                if cols < 160:
                    self._session.setwinsize(1024, 160)
                    nrows, ncols = self._session.getwinsize()
                    logger.debug("Terminal window size changed from "
                                "{}x{} to {}x{}".format(rows, cols, nrows, ncols))
                else:
                    logger.debug("Terminal window size: {}x{}".format(rows, cols))

            except pexpect.EOF:
                raise ConnectionError("Connection error", self.hostname)
            except pexpect.TIMEOUT:
                raise ConnectionTimeoutError("Timeout", self.hostname)

            self._session.logfile_read = self._logfile_fd

    def send_command(self, cmd):
        self.setecho(False)
        self.send(cmd)
        self.expect_exact([cmd, pexpect.TIMEOUT], timeout=15)
        self.sendline()
        self.setecho(True)

    def disconnect(self):
        logger.debug("Disconnecting the sessions")
        self.sendline('\x04')
        self.sendline('\x03')
        self.sendcontrol(']')
        self.sendline('quit')

        self._session.close()
        logger.debug("Disconnected")
        self.connected = False


    @property
    def before(self):
        """
        Property added to imitate pexpect.spawn class
        """
        return self._session.before if self._session else None

    @property
    def after(self):
        """
        Property added to imitate pexpect.spawn class
        """
        return self._session.after if self._session else None

