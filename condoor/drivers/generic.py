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
from os import getpid
import re
import logging

import pexpect

from condoor.actions import a_send, a_connection_closed, a_stays_connected, a_unexpected_prompt, a_expected_prompt
from condoor.fsm import FSM
from condoor.exceptions import ConnectionError, CommandError, CommandSyntaxError, CommandTimeoutError
from condoor.utils import pattern_to_str

from condoor import pattern_manager

logger = logging.getLogger("{}-{}".format(getpid(), __name__))


class Driver(object):
    platform = 'generic'
    inventory_cmd = None
    users_cmd = None
    target_prompt_components = ['prompt_dynamic']
    prepare_terminal_session = ['terminal len 0']
    families = {}

    def __init__(self, device):

        self.device = device

        # FIXME: Do something with this, it's insane
        self.prompt_re = pattern_manager.get_pattern(self.platform, 'prompt')
        self.syntax_error_re = pattern_manager.get_pattern(self.platform, 'syntax_error')
        self.connection_closed_re = pattern_manager.get_pattern(self.platform, 'connection_closed')
        self.press_return_re = pattern_manager.get_pattern(self.platform, 'press_return')
        self.more_re = pattern_manager.get_pattern(self.platform, 'more')
        self.rommon_re = pattern_manager.get_pattern(self.platform, 'rommon')
        self.buffer_overflow_re = pattern_manager.get_pattern(self.platform, 'buffer_overflow')

        self.username_re = pattern_manager.get_pattern(self.platform, 'username')
        self.password_re = pattern_manager.get_pattern(self.platform, 'password')
        self.unable_to_connect_re = pattern_manager.get_pattern(self.platform, 'unable_to_connect')
        self.timeout_re = pattern_manager.get_pattern(self.platform, 'timeout')
        self.standby_re = pattern_manager.get_pattern(self.platform, 'standby')

        self.pid2platform_re = pattern_manager.get_pattern(self.platform, 'pid2platform')
        self.platform_re = pattern_manager.get_pattern(self.platform, 'platform', compiled=False)
        self.version_re = pattern_manager.get_pattern(self.platform, 'version', compiled=False)
        self.vty_re = pattern_manager.get_pattern(self.platform, 'vty')
        self.console_re = pattern_manager.get_pattern(self.platform, 'console')

    def __repr__(self):
        return str(self.platform)

    def get_version_text(self):
        try:
            version_text = self.device.send("show version brief", timeout=120)
        except CommandError:
            # IOS Hack - need to check if show version brief is supported on IOS/IOS XE
            version_text = self.device.send("show version", timeout=120)
        return version_text

    def get_inventory_text(self):
        inventory_text = None
        if self.inventory_cmd:
            try:
                inventory_text = self.device.send(self.inventory_cmd, timeout=120)
                logger.debug('Inventory collected')
            except CommandError:
                logger.debug('Unable to collect inventory')
        else:
            logger.debug('No inventory command for {}'.format(self.platform))
        return inventory_text

    def get_hostname_text(self):
        return None

    def get_users_text(self):
        users_text = None
        if self.users_cmd:
            try:
                users_text = self.device.send(self.users_cmd, timeout=60)
            except CommandError:
                logger.debug('Unable to collect connected users information')
        else:
            logger.debug('No users command for {}'.format(self.platform))
        return users_text

    def get_os_type(self, version_text):
        # FIXME: Consider moving back to device level. This is not depended on the driver
        os_type = None
        if version_text is None:
            return os_type

        match = re.search("(XR|XE|NX-OS)", version_text)
        if match:
            os_type = match.group(1)
        else:
            os_type = 'IOS'

        if os_type == "XR":
            match = re.search("Build Information", version_text)
            if match:
                os_type = "eXR"
            match = re.search("XR Admin Software", version_text)
            if match:
                os_type = "Calvados"
        return os_type

    def get_os_version(self, version_text):
        os_version = None
        if version_text is None:
            return os_version
        print(version_text)
        match = re.search(self.version_re, version_text, re.MULTILINE)
        if match:
            os_version = match.group(1)

        return os_version

    def get_hw_family(self, version_text):
        family = None
        if version_text is None:
            return family

        match = re.search(self.platform_re, version_text, re.MULTILINE)
        if match:
            logger.debug("Platform string: {}".format(match.group()))
            family = match.group(1)
            for key, value in self.families.items():
                if family.startswith(key):
                    family = value
                    break
        else:
            logger.debug("Platform string not present. Refer to CSCux08958")
        return family

    def get_hw_platform(self, udi):
        platform = None
        try:
            pid = udi['pid']
            match = re.search(self.pid2platform_re, pid)
            if match:
                platform = match.group(1)
        except KeyError:
            pass
        return platform

    def is_console(self, users_text):
        for line in users_text.split('\n'):
            if '*' in line:
                match = re.search(self.vty_re, line)
                if match:
                    logger.debug("Detected connection to vty")
                    return False
                else:
                    match = re.search(self.console_re, line)
                    if match:
                        logger.debug("Detected connection to console")
                        return True

        logger.debug("Connection port unknown")
        return None

    def update_driver(self, prompt):
        logger.debug(prompt)
        platform = pattern_manager.get_platform_based_on_prompt(prompt)
        if platform:
            logger.debug('{} -> {}'.format(self.platform, platform))
            return platform
        else:
            logger.debug('No update: {}'.format(self.platform))
            return self.platform

    def wait_for_string(self, expected_string, timeout=60):

        #                    0                         1                        2                        3
        events = [self.syntax_error_re, self.connection_closed_re, expected_string, self.press_return_re,
                  #        4           5                 6                7
                  self.more_re, pexpect.TIMEOUT, pexpect.EOF, self.buffer_overflow_re]

        # add detected prompts chain
        events += self.device.get_previous_prompts()  # without target prompt

        logger.debug("Expected: {}".format(pattern_to_str(expected_string)))

        transitions = [
            (self.syntax_error_re, [0], -1, CommandSyntaxError("Command unknown", self.device.hostname), 0),
            (self.connection_closed_re, [0], 1, a_connection_closed, 10),
            (pexpect.TIMEOUT, [0], -1, CommandTimeoutError("Timeout waiting for prompt", self.device.hostname), 0),
            (pexpect.EOF, [0, 1], -1, ConnectionError("Unexpected device disconnect", self.device.hostname), 0),
            (self.more_re, [0], 0, partial(a_send, " "), 10),
            (expected_string, [0, 1], -1, a_expected_prompt, 0),
            (self.press_return_re, [0], -1, a_stays_connected, 0),
            # TODO: Customize in XR driver
            (self.buffer_overflow_re, [0], -1, CommandSyntaxError("Command too long", self.device.hostname), 0)
        ]

        for prompt in self.device.get_previous_prompts():
            transitions.append((prompt, [0, 1], 0, a_unexpected_prompt, 0))

        sm = FSM("WAIT-4-STRING", self.device, events, transitions, timeout=timeout)
        return sm.run()

    # def send_xml(self, command, timeout=60):
    #     """
    #     Handle error i.e.
    #     ERROR: 0x24319600 'XML-TTY' detected the 'informational' condition
    #     'The XML TTY Agent has not yet been started.
    #     Check that the configuration 'xml agent tty' has been committed.'
    #     """
    #     self._debug("Starting XML TTY Agent")
    #     result = self.send("xml")
    #     self._info("XML TTY Agent started")
    #
    #     result = self.send(command, timeout=timeout)
    #     self.ctrl.sendcontrol('c')
    #     return result

    # def netconf(self, command):
    #     """
    #     Handle error i.e.
    #     ERROR: 0x24319600 'XML-TTY' detected the 'informational' condition
    #     'The XML TTY Agent has not yet been started.
    #     Check that the configuration 'xml agent tty' has been committed.'
    #     """
    #     self._debug("Starting XML TTY Agent")
    #     result = self.send("netconf", wait_for_string=']]>]]>')
    #     self._info("XML TTY Agent started")
    #
    #     self.ctrl.send(command)
    #     self.ctrl.send("\r\n")
    #     self.ctrl.expect("]]>]]>")
    #     result = self.ctrl.before
    #     self.ctrl.sendcontrol('c')
    #     self.send()
    #     return result

    def enable(self, enable_password):
        """This method changes the device mode to privileged. If device does not support privileged mode the
        the informational message to the log will be posted.

        Args:
            enable_password (str): The privileged mode password. This is optional parameter. If password is not
                provided but required the password from url will be used. Refer to :class:`condoor.Connection`
        """
        logger.info("Privileged mode not supported on {} platform".format(self.platform))

    def reload(self, rommon_boot_command="boot", reload_timeout=300, save_config=True):
        """This method reloads the device and waits for device to boot up. It post the informational message to the
        log if not implemented by device driver."""

        logger.info("Reload not implemented on {} platform".format(self.platform))

    def after_connect(self):
        pass

    def make_dynamic_prompt(self, prompt):
        patterns = [pattern_manager.get_pattern(
            self.platform, pattern_name, compiled=False) for pattern_name in self.target_prompt_components]

        patterns_re = "|".join(patterns).format(prompt=re.escape(prompt[:-1]))

        try:
            prompt_re = re.compile(patterns_re)
        except re.error as e:
            raise RuntimeError("Pattern compile error: {} ({}:{})".format(e.message, self.platform, patterns_re))

        logger.debug("Dynamic prompt: '{}'".format(prompt_re.pattern))
        return prompt_re

    def update_config_mode(self, prompt):
        if 'config' in prompt:
            mode = 'config'
        elif 'admin' in prompt:
            mode = 'admin'
        else:
            mode = 'global'

        logger.debug("Mode: {}".format(mode))
        return mode

    def update_hostname(self, prompt):
        result = re.search(self.prompt_re, prompt)
        if result:
            hostname = result.group('hostname')
            logger.debug("Hostname detected: {}".format(hostname))
        else:
            hostname = self.device.hostname
            logger.debug("Hostname not set: {}".format(prompt))
        return hostname
