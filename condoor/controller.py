"""Provides the Controller class which is a wrapper to the pyexpect.spawn class."""

import logging
import pexpect

from condoor.utils import delegate
from condoor.exceptions import ConnectionError, ConnectionTimeoutError

logger = logging.getLogger(__name__)


# Delegate following methods to _session class
@delegate("_session", ("expect", "expect_exact", "expect_list", "compile_pattern_list", "sendline",
                       "isalive", "sendcontrol", "send", "read_nonblocking", "setecho"))
class Controller(object):
    """Controller class which wraps the pyexpect.spawn class."""

    def __init__(self, connection):
        """Initialize the Controller object for specific connection."""
        # delegated pexpect session
        self._session = None
        self._connection = connection

        self._logfile_fd = connection.session_fd
        self.connected = False
        self.authenticated = False
        # FIXME: consider the hostname
        self.hostname = 'ctrl-hostname'
        self.last_hop = 0

    def spawn_session(self, command):
        """Spawn the session using proper command."""
        logger.debug("Executing command: '{}'".format(command))
        if self._session and self.isalive():  # pylint: disable=no-member
            try:
                self.send(command)  # pylint: disable=no-member
                self.expect_exact(command, timeout=20)  # pylint: disable=no-member
                self.sendline()  # pylint: disable=no-member

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
            self.connected = True

    def send_command(self, cmd):
        """Send command."""
        self.setecho(False)  # pylint: disable=no-member
        self.send(cmd)  # pylint: disable=no-member
        self.expect_exact([cmd, pexpect.TIMEOUT], timeout=15)  # pylint: disable=no-member
        self.sendline()  # pylint: disable=no-member
        self.setecho(True)  # pylint: disable=no-member

    def disconnect(self):
        """Disconnect the controller."""
        if self._session and self._session.isalive():
            logger.debug("Disconnecting the sessions")
            self.sendline('\x04')  # pylint: disable=no-member
            self.sendline('\x03')  # pylint: disable=no-member
            self.sendcontrol(']')  # pylint: disable=no-member
            self.sendline('quit')  # pylint: disable=no-member
            self._session.close()
        logger.debug("Disconnected")
        self.connected = False

    @property
    def is_connected(self):
        """Return connected state."""
        return self.connected

    @property
    def before(self):
        """Return text up to the expected string pattern."""
        return self._session.before if self._session else None

    @property
    def after(self):
        """Return text that was matched by the expected pattern."""
        return self._session.after if self._session else None
