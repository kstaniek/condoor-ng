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

from condoor.drivers.generic import Driver as Generic
from condoor import pattern_manager, CommandError

from os import getpid
logger = logging.getLogger("{}-{}".format(getpid(), __name__))


class Driver(Generic):
    platform = 'jumphost'
    inventory_cmd = None
    target_prompt_components = ['prompt_dynamic']
    prepare_terminal_session = []

    def __init__(self, device):
        super(Driver, self).__init__(device)

    def get_version_text(self):
        version_text = self.device.send('uname -sr', timeout=10)
        return version_text

    def update_hostname(self, prompt):
        return self.device.hostname

    def get_hostname_text(self):
        # FIXME: fix it, too complex logic
        try:
            hostname_text = self.device.send('hostname', timeout=10)
            if hostname_text:
                self.device.hostname = hostname_text.split('\n')[0]
                return hostname_text
        except CommandError:
            return None

    def make_dynamic_prompt(self, prompt):
        patterns = [pattern_manager.get_pattern(
            self.platform, pattern_name, compiled=False) for pattern_name in self.target_prompt_components]

        patterns_re = "|".join(patterns).format(prompt=re.escape(prompt))

        try:
            prompt_re = re.compile(patterns_re)
        except re.error as e:
            raise RuntimeError("Pattern compile error: {} ({}:{})".format(e.message, self.platform, patterns_re))

        logger.debug("Dynamic prompt: '{}'".format(prompt_re.pattern))
        return prompt_re
