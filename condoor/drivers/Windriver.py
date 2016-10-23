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
import logging
from generic import Driver as Generic
from condoor import pattern_manager

from os import getpid
logger = logging.getLogger("{}-{}".format(getpid(), __name__))


class Driver(Generic):
    platform = 'Windriver'
    inventory_cmd = None
    target_prompt_components = ['prompt_dynamic', 'prompt_default', 'calvados', 'lc']
    prepare_terminal_session = []
    families = {
        "ASR9K": "ASR9K",
        "ASR-9": "ASR9K",
        "ASR9": "ASR9K",
        "NCS-6": "NCS6K",
        "NCS-4": "NCS4K",
        "NCS-50": "NCS5K",
        "NCS-55": "NCS5500",
        "NCS1": "NCS1K",
        "NCS-1": "NCS1K",
    }

    def __init__(self, device):
        super(Driver, self).__init__(device)

    def get_version_text(self):
        version_text = self.device.send('cat /etc/issue', timeout=10)
        return version_text

    def get_os_type(self, version_text):
        return 'Windriver'

    def get_os_version(self, version_text):
        match = re.search("Wind River Linux (\d+\.\d+\.\d+\.\d+)", version_text, re.MULTILINE)
        if match:
            return match.group(1)
        return None

    # def update_driver(self, prompt):
    #     logger.debug(prompt)
    #     platform = pattern_manager.get_platform_based_on_prompt(prompt)
    #     if platform:
    #         logger.debug('{} -> {}'.format(self.platform, platform))
    #         return platform
    #     else:
    #         return self.platform


    # def after_connect(self):
    #     show_users = self.device.send("show users", timeout=120)
    #     result = re.search(pattern_manager.get_pattern(self.platform, 'connected_locally'), show_users)
    #     if result:
    #         self._debug('Exit from Calvados')
    #         self.device.send('exit')
    #         return True
    #     return False