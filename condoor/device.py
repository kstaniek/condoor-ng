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
import sys
import logging
import pexpect

from condoor.protocols import make_protocol
from condoor.exceptions import CommandError, ConnectionError, CommandSyntaxError, CommandTimeoutError
from utils import parse_inventory


from os import getpid
logger = logging.getLogger("{}-{}".format(getpid(), __name__))


class Device(object):
    def __init__(self, chain, node_info):

        self.chain = chain
        self.hostname = "hostname-device"  # used by driver

        self.node_info = node_info
        self.ctrl = None

        # information whether the device is connected to the console
        self.is_console = True

        # True is last device in the chain
        self.is_target = False

        # prompt
        self.prompt = None
        self.prompt_re = None

        # version_text
        self.version_text = None

        # inventory_text
        self.inventory_text = None

        # set if device is connect
        self.connected = False

        self.mode = None

        protocol_name = self.node_info.protocol
        if self.is_console:
            protocol_name += '_console'

        self.protocol = make_protocol(protocol_name, self)

        self._driver_name = None
        self.driver = None

        self.driver = self.make_driver('jumphost')

        self.os_version = None
        self.os_type = None
        self.family = None
        self.platform = None
        self.udi = None

        self.last_command_result = None

    def __repr__(self):
        return str(self.node_info)

    def connect(self, ctrl):
        self.ctrl = ctrl
        if self.protocol.connect(self.driver):
            if self.protocol.authenticate(self.driver):
                if not self.prompt:
                    self.prompt = self.protocol.detect_prompt()
                    self.prompt_re = self.driver.make_dynamic_prompt(self.prompt)
                self.connected = True
                return True

        else:
            return False

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
        if self.connected:
            output = ''
            logger.debug("Sending command: '{}'".format(cmd))

            try:
                output = self.execute_command(cmd, timeout, wait_for_string)
            except ConnectionError:
                logger.error("Connection lost. Disconnecting.")
                # self.disconnect()
                raise

            logger.info("Command executed successfully: '{}'".format(cmd))
            return output

        else:
            raise ConnectionError("Device not connected", host=self.hostname)

    def execute_command(self, cmd, timeout, wait_for_string):
        try:
            self.last_command_result = None
            self.ctrl.send_command(cmd)
            if wait_for_string is None:
                wait_for_string = self.prompt_re

            if not self.driver.wait_for_string(wait_for_string, timeout):
                logger.error("Unexpected session disconnect during '{}' "
                             "command execution".format(cmd))
                raise ConnectionError("Unexpected session disconnect", host=self.hostname)

            if self.last_command_result:
                return self.last_command_result.replace('\r', '')
            else:
                return self.ctrl.before.replace('\r', '')

        except CommandSyntaxError as e:
            logger.error("{}: '{}'".format(e.message, cmd))
            e.command = cmd
            raise

        except (CommandTimeoutError, pexpect.TIMEOUT) as e:
            logger.error("Command timeout: '{}'".format(cmd))
            raise CommandTimeoutError(message="Command timeout", host=self.hostname, command=cmd)

        except ConnectionError as e:
            logger.error("{}: '{}'".format(e.message, cmd))
            raise

        except pexpect.EOF:
            logger.error("Unexpected session disconnect")
            raise ConnectionError("Unexpected session disconnect", host=self.hostname)

        except Exception as e:
            logger.critical("Exception", exc_info=True)
            raise ConnectionError(message="Unexpected error", host=self.hostname)

    @property
    def driver_name(self):
        return None if self.driver is None else self.driver.platform

    @driver_name.setter
    def driver_name(self, driver_name):
        if self.driver is None or driver_name != self.driver.platform:
            self.driver = self.make_driver(driver_name)
            logger.debug("{}".format(self.driver.platform))
            self.make_dynamic_prompt(self.prompt)

    def make_driver(self, driver_name='generic'):

        module_str = 'condoor.drivers.%s' % driver_name
        try:
            __import__(module_str)
            module = sys.modules[module_str]
            driver_class = getattr(module, 'Driver')
        except ImportError as e:
            logger.critical("Import error", exc_info=e)
            return self.make_driver()
            # raise GeneralError("Platform {} not supported".format(driver_name))

        return driver_class(self)

    def get_previous_prompts(self):
        return self.chain.get_previous_prompts(self)

    def get_version_text(self):
        self.version_text = self.driver.get_version_text()

    def make_dynamic_prompt(self, prompt):
        if prompt:
            self.prompt_re = self.driver.make_dynamic_prompt(prompt)

    def get_inventory_text(self):
        logger.debug('Getting inventory')
        self.inventory_text = self.driver.get_inventory_text()

    def update_udi(self):
        self.udi = parse_inventory(self.inventory_text)
        logger.debug("UDI Updated")

        # if family not known update platform and family based on udi
        if self.family is None:
            pid = self.udi['pid']
            for key, value in self.driver.families.items():
                if pid.startswith(key):
                    self.family = value
                    self.platform = pid[:-3] if '-AC' in pid or '-DC' in pid else pid
                    logger.debug("Family: {}".format(self.family))
                    logger.debug("Platform: {}".format(self.platform))
                    break

    def update_config_mode(self, prompt):
        self.mode = self.driver.update_config_mode(prompt)

    def update_hostname(self, prompt):
        self.hostname = self.driver.update_hostname(prompt)

    def update_driver(self, prompt):
        logger.debug("{}: New prompt '{}'".format(self.driver.platform, prompt))
        self.prompt = prompt
        self.driver_name = self.driver.update_driver(prompt)

    def prepare_terminal_session(self):
        for cmd in self.driver.prepare_terminal_session:
            self.send(cmd)

    def update_os_type(self):
        os_type = self.driver.get_os_type(self.version_text)
        if os_type:
            logger.debug("OS Type: {}".format(os_type))
            self.os_type = os_type

    def update_os_version(self):
        os_version = self.driver.get_os_version(self.version_text)
        if os_version:
            logger.debug("OS Version: {}".format(os_version))
            self.os_version = os_version

    def update_family(self):
        if self.version_text is None:
            return

        match = re.search("^(  )?cisco (.*?) ", self.version_text, re.MULTILINE)  # NX-OS
        if match:
            logger.debug("Platform string: {}".format(match.group()))
            self.family = self.platform = match.group(2)

            for key, value in self.driver.families.items():
                if self.family.startswith(key):
                    self.family = value
                    break
        else:
            logger.debug("Platform string not present. Refer to CSCux08958")

        logger.debug("Family: {}".format(self.family))
        logger.debug("Platform: {}".format(self.platform))

    def after_connect(self):
        return self.driver.after_connect()
