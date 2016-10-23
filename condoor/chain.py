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
from device import Device
from hopinfo import make_hop_info_from_url

from controller import Controller
from condoor.exceptions import CommandSyntaxError
import condoor

from os import getpid
logger = logging.getLogger("{}-{}".format(getpid(), __name__))


class Chain(object):
    def __init__(self, connection, urls):
        self.connection = connection
        self.ctrl = Controller(connection)
        self.devices = [device for device in device_gen(self, urls)]
        self.target_device.driver_name = 'generic'
        self.target_device.is_target = True

    def connect(self):
        for device in self.devices:
            self.ctrl.spawn_session(device)
            if device.connect(self.ctrl):
                logger.info("Connected to {}".format(device))
                pass
            else:
                return False

        device.update_driver(device.prompt)
        device.after_connect()

        try:
            device.prepare_terminal_session()
        except CommandSyntaxError:
            pass

        device.get_version_text()
        device.update_os_type()
        device.update_os_version()

        device.driver_name = device.os_type

        device.prepare_terminal_session()

        device.get_inventory_text()
        device.update_family()
        device.update_udi()

        return True

    def disconnect(self):
        self.ctrl.disconnect()

    @property
    def target_device(self):
        return self.devices[-1]

    def get_previous_prompts(self, device):
        device_index = self.devices.index(device)
        prompts = [re.compile("(?!x)x")] + [device.prompt_re for device in self.devices[:device_index]]
        return prompts

    def send(self, cmd, timeout, wait_for_string):
        self.target_device.send(cmd, timeout=timeout, wait_for_string=wait_for_string)

    def dump(self):
        for device in self.devices:
            print(device.udi)


def device_gen(chain, urls):
    for url in urls:
        yield Device(chain, make_hop_info_from_url(url))


