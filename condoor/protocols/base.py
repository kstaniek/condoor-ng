"""This procides the base Protocol class implementation."""

import re
from os import getpid
import time
import logging
import pexpect


from condoor.exceptions import ConnectionError
from condoor.utils import levenshtein_distance

logger = logging.getLogger("{}-{}".format(getpid(), __name__))


class Protocol(object):
    """Base Protocol class implementation."""

    def __init__(self, device):
        """Initialize the protocol object."""
        self.device = device
        self.hostname = self.device.node_info.hostname
        self.port = self.device.node_info.port
        self.password = self.device.node_info.password
        self.username = self.device.node_info.username

        self.last_pattern = None

    def connect(self, device):
        """Connect using specific protocol."""
        raise NotImplementedError("Connection method not implemented")

    def authenticate(self, device):
        """Authenticate using specific protocol."""
        raise NotImplementedError("Authentication method not implemented")

    def disconnect(self):
        """Disconnect using specific protocol."""
        raise NotImplementedError("Disconnect method not implemented")

    def try_read_prompt(self, timeout_multiplier):
        """Read the prompt.

        Based on try_read_prompt from pxssh.py
        https://github.com/pexpect/pexpect/blob/master/pexpect/pxssh.py
        """
        # maximum time allowed to read the first response
        first_char_timeout = timeout_multiplier * 2

        # maximum time allowed between subsequent characters
        inter_char_timeout = timeout_multiplier * 0.4

        # maximum time for reading the entire prompt
        total_timeout = timeout_multiplier * 4

        prompt = ""
        begin = time.time()
        expired = 0.0
        timeout = first_char_timeout

        while expired < total_timeout:
            try:
                p = self.device.ctrl.read_nonblocking(size=1, timeout=timeout)
                # \r=0x0d CR \n=0x0a LF
                if p not in ['\n', '\r']:  # omit the cr/lf sent to get the prompt
                    timeout = inter_char_timeout
                expired = time.time() - begin
                prompt += p
            except pexpect.TIMEOUT:
                break
            except pexpect.EOF:
                raise ConnectionError('Session disconnected')

        prompt = prompt.strip()
        return prompt

    def detect_prompt(self, sync_multiplier=4):
        """Detect the prompt.

        This attempts to find the prompt. Basically, press enter and record
        the response; press enter again and record the response; if the two
        responses are similar then assume we are at the original prompt.
        This can be a slow function. Worst case with the default sync_multiplier
        can take 16 seconds. Low latency connections are more likely to fail
        with a low sync_multiplier. Best case sync time gets worse with a
        high sync multiplier (500 ms with default).

        """
        self.device.ctrl.sendline()
        self.try_read_prompt(sync_multiplier)

        attempt = 0
        max_attempts = 10
        while attempt < max_attempts:
            attempt += 1
            logger.debug("Detecting prompt. Attempt ({}/{})".format(attempt, max_attempts))

            self.device.ctrl.sendline()
            a = self.try_read_prompt(sync_multiplier)

            self.device.ctrl.sendline()
            b = self.try_read_prompt(sync_multiplier)

            ld = levenshtein_distance(a, b)
            len_a = len(a)
            logger.debug("LD={},MP={}".format(ld, sync_multiplier))
            sync_multiplier *= 1.2
            if len_a == 0:
                continue

            if float(ld) / len_a < 0.3:
                prompt = b.splitlines(True)[-1]
                logger.debug("Detected prompt: '{}'".format(prompt))
                compiled_prompt = re.compile("(\r\n|\n\r){}".format(re.escape(prompt)))
                self.device.ctrl.sendline()
                self.device.ctrl.expect(compiled_prompt)  # match from new line
                return prompt

        return None

    def _acquire_password(self):
        # TODO: Remove
        password = self.password
        # if not password:
        #     if self.account_manager:
        #         self._dbg(20,
        #                   "{}: {}: Acquiring password for {} from system KeyRing".format(
        #                       self.protocol, self.hostname, self.username))
        #         password = self.account_manager.get_password(self.hostname, self.username, interact=True)
        #         if not password:
        #             self._dbg(30, "{}: {}: Password for {} does not exists in KeyRing".format(
        #                 self.protocol, self.hostname, self.username))
        return password
