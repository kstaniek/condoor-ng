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

import sys
import logging
import pexpect

from condoor.exceptions import ConnectionError, CommandSyntaxError, CommandTimeoutError
from utils import parse_inventory


from os import getpid
logger = logging.getLogger("{}-{}".format(getpid(), __name__))


class Device(object):
    def __init__(self, chain, node_info, driver_name='jumphost', is_target=False):

        self.chain = chain
        self.hostname = "{}:{}".format(node_info.hostname, node_info.port)  # used by driver

        self.node_info = node_info
        self.ctrl = None

        # information whether the device is connected to the console
        self.is_console = False

        # True is last device in the chain
        self.is_target = is_target

        # prompt
        self.prompt = None
        self.prompt_re = None

        # version_text
        self.version_text = None

        # inventory_text
        self.inventory_text = None

        # hostname_text
        self.hostname_text = None

        # show users text
        self.users_text = None

        # set if device is connect
        self.connected = False

        self.mode = None

        self.protocol = None
        self.driver = self.make_driver(driver_name)

        self.os_version = None
        self.os_type = None
        self.family = None
        self.platform = None
        self.udi = None
        self.is_console = None

        self.last_command_result = None

    @property
    def device_info(self):
        return {
            'family': self.family,
            'platform': self.platform,
            'os_type': self.os_type,
            'os_verison': self.os_version,
            'udi': self.udi,
            'driver_name': self.driver.platform,
            'mode': self.mode,
            'is_console': self.is_console,
            'is_target': self.is_target,
            'prompt': self.prompt,
            'hostname': self.hostname,
        }

    def __repr__(self):
        return str(self.node_info)

    def connect(self, ctrl):
        if self.prompt_re is None:
            self.prompt_re = self.driver.prompt_re

        self.ctrl = ctrl
        # self.protocol.last_pattern = None
        if self.protocol.connect(self.driver):
            if self.protocol.authenticate(self.driver):
                if not self.prompt:
                    self.prompt = self.protocol.detect_prompt()
                    self.prompt_re = self.driver.make_dynamic_prompt(self.prompt)
                self.connected = True

                if self.is_target is False:
                    if self.version_text is None:
                        self.get_version_text()
                    if self.os_version is None:
                        self.update_os_version()
                    if self.hostname_text is None:
                        self.get_hostname_text()
                        self.update_hostname(self.prompt)
                else:
                    self._connected_to_target()
                return True

        else:
            return False

    def _connected_to_target(self):
        self.update_driver(self.prompt)
        self.after_connect()

        try:
            self.prepare_terminal_session()
        except CommandSyntaxError:
            pass

        if self.version_text is None:
            self.get_version_text()

        if self.os_type is None:
            self.update_os_type()

        self.driver_name = self.os_type

        if self.os_version is None:
            self.update_os_version()

        # delegate to device
        self.prompt_re = self.driver.make_dynamic_prompt(self.prompt)

        self.prepare_terminal_session()

        if self.inventory_text is None:
            self.get_inventory_text()

        if self.udi is None:
            self.update_udi()

        if self.family is None:
            self.update_family()

        if self.platform is None:
            self.update_platform()

        if self.is_console is None:
            self.get_users_text()
            self.update_console()

    def disconnect(self):
        self.protocol = None
        pass

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
                output = self.last_command_result.replace('\r', '')
            else:
                output = self.ctrl.before.replace('\r', '')

            second_line_index = output.find('\n') + 1
            output = output[second_line_index:]
            return output

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

        logger.debug("Driver: {}".format(driver_class.platform))
        return driver_class(self)

    def get_previous_prompts(self):
        return self.chain.get_previous_prompts(self)

    def get_version_text(self):
        logger.debug("Getting version text")
        self.version_text = self.driver.get_version_text()
        if self.version_text:
            logger.debug("Version text collected")
        else:
            logger.warn("Version text not collected")

    def get_hostname_text(self):
        logger.debug("Getting hostname text")
        self.hostname_text = self.driver.get_hostname_text()
        if self.hostname_text:
            logger.debug("Hostname text collected")
        else:
            logger.warn("Hostname text not collected")

    def get_inventory_text(self):
        logger.debug("Getting inventory text")
        self.inventory_text = self.driver.get_inventory_text()
        if self.inventory_text:
            logger.debug("Inventory text collected")
        else:
            logger.warn("Inventory text not collected")

    def get_users_text(self):
        logger.debug("Getting connected users text")
        self.users_text = self.driver.get_users_text()
        if self.users_text:
            logger.debug("Users text collected")
        else:
            logger.warn("Users text not collected")

    def get_protocol_name(self):
        protocol_name = self.node_info.protocol
        if self.is_console:
            protocol_name += '_console'
        return protocol_name

    def make_dynamic_prompt(self, prompt):
        if prompt:
            self.prompt_re = self.driver.make_dynamic_prompt(prompt)

    def update_udi(self):
        logger.debug("Parsing inventory")
        # TODO: Maybe validate if udi is complete
        self.udi = parse_inventory(self.inventory_text)

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
            logger.debug("SW Type: {}".format(os_type))
            self.os_type = os_type

    def update_os_version(self):
        os_version = self.driver.get_os_version(self.version_text)
        if os_version:
            logger.debug("SW Version: {}".format(os_version))
            self.os_version = os_version

    def update_family(self):
        family = self.driver.get_hw_family(self.version_text)
        if family:
            logger.debug("HW Family: {}".format(family))
            self.family = family

    def update_platform(self):
        platform = self.driver.get_hw_platform(self.udi)
        if platform:
            logger.debug("HW Platform: {}".format(platform))
            self.platform = platform

    def update_console(self):
        is_console = self.driver.is_console(self.users_text)
        if is_console is not None:
            self.is_console = is_console

        # print(self.driver.platform)
        # if self.version_text is None:
        #     return
        #
        # match = re.search("^(  )?cisco (.*?) ", self.version_text, re.MULTILINE)  # NX-OS
        # if match:
        #     logger.debug("Platform string: {}".format(match.group()))
        #     self.family = self.platform = match.group(2)
        #
        #     for key, value in self.driver.families.items():
        #         if self.family.startswith(key):
        #             self.family = value
        #             break
        # else:
        #     logger.debug("Platform string not present. Refer to CSCux08958")
        #
        # logger.debug("Family: {}".format(self.family))
        # logger.debug("Platform: {}".format(self.platform))

    def after_connect(self):
        return self.driver.after_connect()
