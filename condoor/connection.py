"""Provides the main Connection class."""
import re
import os
import shelve
import logging
from hashlib import md5

from collections import deque
from condoor.chain import Chain
from condoor.exceptions import ConnectionError
from condoor.utils import FilteredFile, normalize_urls, make_handler
import condoor

logger = logging.getLogger("{}-{}".format(os.getpid(), __name__))


_cache_file = "/tmp/condoor.shelve"


class Connection(object):
    """Connection class providing the condoor API."""

    def __init__(self, urls, log_dir=None, log_level=logging.DEBUG, log_session=True):
        """Initialize the Connection object."""
        self._discovered = False
        self._last_chain_index = 1

        self.log_session = log_session

        top_logger = logging.getLogger("{}-{}".format(os.getpid(), 'condoor'))
        if not len(top_logger.handlers):
            self._handler = make_handler(log_dir, log_level)
            top_logger.addHandler(self._handler)

        top_logger.setLevel(log_level)

        self.session_fd = self._make_session_fd(log_dir)
        logger.info("Condoor version {}".format(condoor.__version__))

        self.connection_chains = [Chain(self, url_list) for url_list in normalize_urls(urls)]

    def _make_session_fd(self, log_dir):
        session_fd = None
        if log_dir is not None:
            try:
                # FIXME: take pattern from pattern manager
                session_fd = FilteredFile(os.path.join(log_dir, 'session.log'),
                                          mode="w", pattern=re.compile("s?ftp://.*:(.*)@"))
            except IOError:
                logger.error("Unable to create session log file")

        else:
            if self.log_session:
                import sys
                session_fd = sys.stderr

        return session_fd

    def _get_key(self):
        m = md5()
        m.update(str(self.connection_chains))
        return m.hexdigest()

    def _write_cache(self):
        try:
            cache = shelve.open(_cache_file, 'c')
        except Exception:
            logger.error("Unable to open a cache file for write")
            return

        key = self._get_key()
        cache[key] = self.device_description_record
        logger.info("Device description record cached: {}".format(key))
        cache.close()

    def connect(self, logfile=None):
        """Connect to the device.

        Args:
            logfile (file): Optional file descriptor for session logging. The file must be open for write.
                The session is logged only if ``log_session=True`` was passed to the constructor.
                It the parameter is not passed then the default *session.log* file is created in `log_dir`.

        Raises:
            ConnectionError: If the discovery method was not called first or there was a problem with getting
             the connection.
            ConnectionAuthenticationError: If the authentication failed.
            ConnectionTimeoutError: If the connection timeout happened.

        """
        if logfile:
            self.session_fd = logfile

        chain_indices = deque(range(len(self.connection_chains)))
        chain_indices.rotate(self._last_chain_index)
        excpt = ConnectionError("Unable to connect to the device")
        for index in chain_indices:
            chain = self.connection_chains[index]
            self._last_chain_index = index
            try:
                if chain.connect():
                    break
            except ConnectionError as e:
                excpt = e
        else:
            # invalidate cache
            raise excpt

        self._write_cache()

    def send(self, cmd="", timeout=60, wait_for_string=None):
        """Send the command to the device and return the output.

        Args:
            cmd (str): Command string for execution. Defaults to empty string.
            timeout (int): Timeout in seconds. Defaults to 60s
            wait_for_string (str): This is optional string that driver
                waits for after command execution. If none the detected
                prompt will be used.

        Returns:
            A string containing the command output.

        Raises:
            ConnectionError: General connection error during command execution
            CommandSyntaxError: Command syntax error or unknown command.
            CommandTimeoutError: Timeout during command execution
        """
        return self._chain.send(cmd, timeout, wait_for_string)

    def disconnect(self):
        """Disconnect the session from the device and all the jumphosts in the path."""
        self._chain.disconnect()

    def discovery(self, logfile=None):
        """Discover the device details.

        This method discover several device attributes.

        Args:
            logfile (file): Optional file descriptor for session logging. The file must be open for write.
                The session is logged only if ``log_session=True`` was passed to the constructor.
                It the parameter is not passed then the default *session.log* file is created in `log_dir`.

        """
        logger.info("Device discovery process started")
        # TODO: invalidate cache
        self.connect(logfile=logfile)

    def enable(self, enable_password=None):
        """Change the device mode to privileged.

        If device does not support privileged mode the the informational message to the log will be posted.

        Args:
            enable_password (str): The privileged mode password. This is optional parameter. If password is not
                provided but required the password from url will be used. Refer to :class:`condoor.Connection`
        """
        self._chain.target_device.enable(enable_password)

    def run_fsm(self, name, command, events, transitions, timeout, max_transitions=20):
        """Instantiate and run the Finite State Machine for the current device connection.

        Here is the example of usage::

            test_dir = "rw_test"
            dir = "disk0:" + test_dir
            REMOVE_DIR = re.compile(re.escape("Remove directory filename [{}]?".format(test_dir)))
            DELETE_CONFIRM = re.compile(re.escape("Delete {}/{}[confirm]".format(filesystem, test_dir)))
            REMOVE_ERROR = re.compile(re.escape("%Error Removing dir {} (Directory doesnot exist)".format(test_dir)))

            command = "rmdir {}".format(dir)
            events = [device.prompt, REMOVE_DIR, DELETE_CONFIRM, REMOVE_ERROR, pexpect.TIMEOUT]
            transitions = [
                (REMOVE_DIR, [0], 1, send_newline, 5),
                (DELETE_CONFIRM, [1], 2, send_newline, 5),
                # if dir does not exist initially it's ok
                (REMOVE_ERROR, [0], 2, None, 0),
                (device.prompt, [2], -1, None, 0),
                (pexpect.TIMEOUT, [0, 1, 2], -1, error, 0)

            ]
            manager.log("Removing test directory from {} if exists".format(dir))
            if not device.run_fsm("DELETE_DIR", command, events, transitions, timeout=5):
                return False

        This FSM tries to remove directory from disk0:

        Args:
            name (str): Name of the state machine used for logging purposes. Can't be *None*
            command (str): The command sent to the device before FSM starts
            events (list): List of expected strings or pexpect.TIMEOUT exception expected from the device.
            transitions (list): List of tuples in defining the state machine transitions.
            timeout (int): Default timeout between states in seconds.
            max_transitions (int): Default maximum number of transitions allowed for FSM.

        The transition tuple format is as follows::

            (event, [list_of_states], next_state, action, timeout)

        - event (str): string from the `events` list which is expected to be received from device.
        - list_of_states (list): List of FSM states that triggers the action in case of event occurrence.
        - next_state (int): Next state for FSM transition.
        - action (func): function to be executed if the current FSM state belongs to `list_of_states` and the `event`
          occurred. The action can be also *None* then FSM transits to the next state without any action. Action
          can be also the exception, which is raised and FSM stops.

        The example action::

            def send_newline(ctx):
                ctx.ctrl.sendline()
                return True

            def error(ctx):
                ctx.message = "Filesystem error"
                return False

            def readonly(ctx):
                ctx.message = "Filesystem is readonly"
                return False

        The ctx object description refer to :class:`condoor.fsm.FSM`.

        If the action returns True then the FSM continues processing. If the action returns False then FSM stops
        and the error message passed back to the ctx object is posted to the log.


        The FSM state is the integer number. The FSM starts with initial ``state=0`` and finishes if the ``next_state``
        is set to -1.

        If action returns False then FSM returns False. FSM returns True if reaches the -1 state.

        """
        return self._chain.target_device.run_fsm(name, command, events, transitions, timeout, max_transitions)

    @property
    def _chain(self):
        return self.connection_chains[self._last_chain_index]

    @property
    def is_connected(self):
        """Return if target device is connected."""
        return self._chain.is_connected

    @property
    def is_discovered(self):
        """Return if target device is discovered."""
        return self._chain.is_discovered

    @property
    def is_console(self):
        """Return if target device is connected via console."""
        return self._chain.is_console

    @property
    def prompt(self):
        """Return target device prompt."""
        return self._chain.target_device.prompt

    @property
    def hostname(self):
        """Return target device hostname."""
        return self._chain.target_device.hostname

    @property
    def os_type(self):
        """Return the string representing the target device OS type.

        For example: IOS, XR, eXR. If not detected returns *None*
        """
        return self._chain.target_device.os_type

    @property
    def os_version(self):
        """Return the string representing the target device OS version.

        For example 5.3.1. If not detected returns *None*
        """
        return self._chain.target_device.os_version

    @property
    def family(self):
        """Return the string representing hardware platform family.

        For example: ASR9K, ASR900, NCS6K, etc.
        """
        return self._chain.target_device.family

    @property
    def platform(self):
        """Return the string representing hardware platform model.

        For example: ASR-9010, ASR922, NCS-4006, etc.
        """
        return self._chain.target_device.platform

    @property
    def mode(self):
        """Return the sting representing the current device mode.

        For example: Calvados, Windriver, Rommon.
        """
        return self._chain.target_device.driver.platform

    @property
    def name(self):
        """Return the chassis name."""
        return self._chain.target_device.udi['name']

    @property
    def description(self):
        """Return the chassis description."""
        return self._chain.target_device.udi['description']

    @property
    def pid(self):
        """Return the chassis PID."""
        return self._chain.target_device.udi['pid']

    @property
    def vid(self):
        """Return the chassis VID."""
        return self._chain.target_device.udi['vid']

    @property
    def sn(self):
        """Return the chassis SN."""
        return self._chain.target_device.udi['sn']

    @property
    def udi(self):
        """Return the dict representing the udi hardware record.

        Example::
            {
            'description': 'ASR-9904 AC Chassis',
            'name': 'Rack 0',
            'pid': 'ASR-9904-AC',
            'sn': 'FOX1830GT5W ',
            'vid': 'V01'
            }

        """
        return self._chain.target_device.udi

    @property
    def device_info(self):
        """Return the dict representing the target device info record.

        Example::
            {
            'family': 'ASR9K',
            'os_type': 'eXR',
            'os_version': '6.1.0.06I',
            'platform': 'ASR-9904'
            }

        """
        return self._chain.target_device.device_info

    @property
    def device_description_record(self):
        """Return dict describing Connection object."""
        return {
            'connections': [{'device_info': [device.device_info for device in chain.devices]}
                            for chain in self.connection_chains],
            'last_chain': self._last_chain_index,
        }
