"""Provides the Chain class keeping the information about intermediate devices (jumphosts) on the paths to target."""
import re
import logging
from os import getpid

from condoor.device import Device
from condoor.hopinfo import make_hop_info_from_url
from condoor.controller import Controller
from condoor.protocols import make_protocol
from condoor.exceptions import ConnectionError

logger = logging.getLogger("{}-{}".format(getpid(), __name__))


def device_gen(chain, urls):
    """Device object generator."""
    itr = iter(urls)
    last = next(itr)
    for url in itr:
        yield Device(chain, make_hop_info_from_url(last), driver_name='jumphost', is_target=False)
        last = url
    yield Device(chain, make_hop_info_from_url(last), driver_name='generic', is_target=True)


class Chain(object):
    """Chain class keeping information about the intermediate jumphosts and target device."""

    def __init__(self, connection, urls):
        """Initialize the new Chain object."""
        self.connection = connection
        self.ctrl = Controller(connection)
        self.devices = [device for device in device_gen(self, urls)]
        self.target_device.driver_name = 'generic'
        self.target_device.is_target = True

    def __repr__(self):
        """Return the string representation of devices in the chain."""
        return str(self.devices)

    def connect(self):
        """Connect to the target device using the intermediate jumphosts."""
        device = None
        for device in self.devices:
            protocol_name = device.get_protocol_name()
            device.protocol = make_protocol(protocol_name, device)

            self.ctrl.spawn_session(device.protocol.get_command())
            if device.connect(self.ctrl):
                logger.info("Connected to {}".format(device))
            else:
                logger.debug("Connection error")
                raise ConnectionError("Connection failed")

        if device is None:
            raise ConnectionError("No devices")

        return True

    def disconnect(self):
        """Disconnect from the device."""
        self.ctrl.disconnect()

    @property
    def target_device(self):
        """Return the target device object (last) in the chain."""
        try:
            return self.devices[-1]
        except IndexError:
            return None

    @property
    def is_connected(self):
        """Return if target device is connected."""
        # TODO: get info from device/controller
        return True

    @property
    def is_discovered(self):
        """Return if target device is discovered."""
        if self.target_device is None:
            return False

        if None in (self.target_device.version_text, self.target_device.os_type, self.target_device.os_version,
                    self.target_device.inventory_text, self.target_device.family, self.target_device.platform):
            return False
        return True

    @property
    def is_console(self):
        """Return is target device is connected over console."""
        if self.target_device is None:
            return False

        return self.target_device.is_console

    def get_previous_prompts(self, device):
        """Return the list of intermediate prompts. All except target."""
        device_index = self.devices.index(device)
        prompts = [re.compile("(?!x)x")] + [dev.prompt_re for dev in self.devices[:device_index]]
        return prompts

    def send(self, cmd, timeout, wait_for_string):
        """Send command to the target device."""
        self.target_device.send(cmd, timeout=timeout, wait_for_string=wait_for_string)
