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
import logging

from condoor.drivers.generic import Driver as Generic
from condoor import pattern_manager

logger = logging.getLogger("{}-{}".format(getpid(), __name__))


class Driver(Generic):
    platform = 'NX-OS'
    inventory_cmd = 'show inventory chassis'
    users_cmd = 'show users'
    target_prompt_components = ['prompt_dynamic', 'prompt_default', 'rommon']
    prepare_terminal_session = ['terminal len 0', 'terminal width 511']
    # N9K-C9508
    families = {
        "Nexus9": "N9K",
        "N9K-C9": "N9K",
    }

    def __init__(self, device):
        super(Driver, self).__init__(device)

    def get_version_text(self):
        version_text = self.device.send("show version", timeout=120)
        return version_text

    def update_driver(self, prompt):
        logger.debug(prompt)
        platform = pattern_manager.get_platform_based_on_prompt(prompt)
        if platform == 'IOS':
            platform = 'NX-OS'

        if platform:
            logger.debug('{} -> {}'.format(self.platform, platform))
            return platform
        else:
            logger.debug('No update: {}'.format(self.platform))
            return self.platform

    def reload(self, save_config=True):
        """
        !!!WARNING! there is unsaved configuration!!!
        This command will reboot the system. (y/n)?  [n]
        """
        if save_config:
            self.device.send("copy running-config startup-config")
        self.device("reload", wait_for_string="This command will reboot the system")
        self.device.ctrl.sendline("y")
