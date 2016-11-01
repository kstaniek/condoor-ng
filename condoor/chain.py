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
from condoor.protocols import make_protocol
from condoor.exceptions import ConnectionError

from os import getpid
logger = logging.getLogger("{}-{}".format(getpid(), __name__))


class Chain(object):
    def __init__(self, connection, urls):
        self.connection = connection
        self.ctrl = Controller(connection)
        self.devices = [device for device in device_gen(self, urls)]
        self.target_device.driver_name = 'generic'
        self.target_device.is_target = True

    def __repr__(self):
        return str(self.devices)

    def connect(self):
        device = None
        for device in self.devices:
            protocol_name = device.get_protocol_name()
            device.protocol = make_protocol(protocol_name, device)

            self.ctrl.spawn_session(device)
            if device.connect(self.ctrl):
                logger.info("Connected to {}".format(device))
            else:
                logger.debug("Connection error")
                raise ConnectionError("Connection failed")

        if device is None:
            raise ConnectionError("No devices")

        return True

    def disconnect(self):
        self.ctrl.disconnect()

    @property
    def target_device(self):
        try:
            return self.devices[-1]
        except IndexError:
            return None

    @property
    def is_connected(self):
        # TODO: get info from device/controller
        return True

    @property
    def is_discovered(self):
        if self.target_device is None:
            return False

        if None in (self.target_device.version_text, self.target_device.os_type, self.target_device.os_version,
                    self.target_device.inventory_text, self.target_device.family, self.target_device.platform):
            return False
        return True

    @property
    def is_console(self):
        if self.target_device is None:
            return False

        return self.target_device.is_console

    def get_previous_prompts(self, device):
        device_index = self.devices.index(device)
        prompts = [re.compile("(?!x)x")] + [dev.prompt_re for dev in self.devices[:device_index]]
        return prompts

    def send(self, cmd, timeout, wait_for_string):
        self.target_device.send(cmd, timeout=timeout, wait_for_string=wait_for_string)

    def dump(self):
        for device in self.devices:
            print("udi: {}".format(device.udi))
            print("hostname: {}".format(device.hostname))
            print("prompt: {}".format(device.prompt))
            print("family: {}".format(device.family))
            print("platform: {}".format(device.platform))
            print("os: {}".format(device.os_type))
            print("os ver: {}".format(device.os_version))


def device_gen(chain, urls):
    it = iter(urls)
    last = next(it)
    for url in it:
        yield Device(chain, make_hop_info_from_url(last), driver_name='jumphost', is_target=False)
        last = url
    yield Device(chain, make_hop_info_from_url(last), driver_name='generic', is_target=True)
