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

import re
import os
import shelve
import logging
from hashlib import md5

from condoor.utils import FilteredFile, normalize_urls, make_handler
from collections import deque
from chain import Chain
from condoor.exceptions import ConnectionError
from os import getpid
import condoor

logger = logging.getLogger("{}-{}".format(getpid(), __name__))


_cache_file = "/tmp/condoor.shelve"


class Connection(object):
    def __init__(self, urls, log_dir=None, log_level=logging.DEBUG, log_session=True):

        self._discovered = False
        self._last_chain_index = 1

        self.log_session = log_session

        top_logger = logging.getLogger("{}-{}".format(getpid(), 'condoor'))
        if not len(top_logger.handlers):
            self._handler = make_handler(log_dir, log_level)
            top_logger.addHandler(self._handler)

        top_logger.setLevel(log_level)

        self.session_fd = self._make_session_fd(log_dir)
        logger.info("Condoor version {}".format(condoor.__version__))

        self.connection_chains = [Chain(self, url_list) for url_list in normalize_urls(urls)]

    def __del__(self):
        top_logger = logging.getLogger("{}-{}".format(getpid(), 'condoor'))
        top_logger.removeHandler(self._handler)

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
        """This method connects to the device.

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
        """
        Send the command to the device and return the output

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
        """
        This method disconnect the session from the device and all the jumphosts in the path.
        """
        self._chain.disconnect()

    def discovery(self, logfile=None):
        """This method detects the device details. This method discovery the several device attributes.

        Args:
            logfile (file): Optional file descriptor for session logging. The file must be open for write.
                The session is logged only if ``log_session=True`` was passed to the constructor.
                It the parameter is not passed then the default *session.log* file is created in `log_dir`.

        """
        logger.info("Device discovery process started")
        #
        self.connect(logfile=logfile)

    def enable(self, enable_password=None):
        """This method changes the device mode to privileged. If device does not support privileged mode the
        the informational message to the log will be posted.

        Args:
            enable_password (str): The privileged mode password. This is optional parameter. If password is not
                provided but required the password from url will be used. Refer to :class:`condoor.Connection`
        """
        self._chain.target_device.enable(enable_password)

    @property
    def _chain(self):
        return self.connection_chains[self._last_chain_index]

    @property
    def is_connected(self):
        return self._chain.is_connected

    @property
    def is_discovered(self):
        return self._chain.is_discovered

    @property
    def is_console(self):
        return self._chain.is_console

    @property
    def prompt(self):
        return self._chain.target_device.prompt

    @property
    def hostname(self):
        return self._chain.target_device.hostname

    @property
    def os_type(self):
        """Returns the string representing the Operating System type. For example: IOS, XR, eXR. If not detected returns
         *None*"""
        return self._chain.target_device.os_type

    @property
    def os_version(self):
        """Returns the string representing the Operating System version. For example 5.3.1.
        If not detected returns *None*"""
        return self._chain.target_device.os_version

    @property
    def family(self):
        """Returns the string representing hardware platform family. For example: ASR9K, ASR900, NCS6K, etc."""
        return self._chain.target_device.family

    @property
    def platform(self):
        """Returns the string representing hardware platform model. For example: ASR-9010, ASR922, NCS-4006, etc."""
        return self._chain.target_device.platform

    @property
    def mode(self):
        """Returns the sting representing the current device mode. For example: Calvados, Windriver, Rommon"""
        return self._chain.target_device.driver.platform

    @property
    def name(self):
        """Returns the chassis name"""
        return self._chain.target_device.udi['name']

    @property
    def description(self):
        """Returns the chassis description."""
        return self._chain.target_device.udi['description']

    @property
    def pid(self):
        """Returns the chassis PID."""
        return self._chain.target_device.udi['pid']

    @property
    def vid(self):
        """Returns the chassis VID."""
        return self._chain.target_device.udi['vid']

    @property
    def sn(self):
        """Returns the chassis SN."""
        return self._chain.target_device.udi['sn']

    @property
    def udi(self):
        """Returns the dict representing the udi hardware record::
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
        """Returns the dict representing the target device info record::
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
        return {
            'connections': [{'device_info': [device.device_info for device in chain.devices]}
                            for chain in self.connection_chains],
            'last_chain': self._last_chain_index,
        }
