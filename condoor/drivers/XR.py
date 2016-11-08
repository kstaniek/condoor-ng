"""This is IOS XR Classic driver implementation."""


from condoor.drivers.generic import Driver as Generic


class Driver(Generic):
    """This is a Driver class implementation for IOS XR Classic."""

    platform = 'XR'
    inventory_cmd = 'admin show inventory chassis'
    users_cmd = 'show users'
    target_prompt_components = ['prompt_dynamic', 'prompt_default', 'rommon', 'xml']
    prepare_terminal_session = ['terminal exec prompt no-timestamp', 'terminal len 0', 'terminal width 0']
    families = {
        "ASR9K": "ASR9K",
        "ASR-9": "ASR9K",
        "CRS": "CRS",
    }

    def __init__(self, device):
        """Initialize the IOS XR Classic driver object."""
        super(Driver, self).__init__(device)
