"""Init file for condoor."""

from condoor.connection import Connection
from condoor.config import CONF
from condoor.patterns import YPatternManager as PatternManager

from condoor.exceptions import CommandTimeoutError, ConnectionError, ConnectionTimeoutError, CommandError, \
    CommandSyntaxError, ConnectionAuthenticationError, GeneralError

from pexpect import TIMEOUT, EOF

__version__ = '2.0.0'

pattern_manager = PatternManager()

"""
This is a python module providing access to Cisco devices over Telnet and SSH.

"""

__all__ = ('Connection', 'TIMEOUT', 'EOF', 'pattern_manager', 'CONF',
           'CommandTimeoutError', 'ConnectionError', 'ConnectionTimeoutError', 'CommandError',
           'CommandSyntaxError', 'ConnectionAuthenticationError', 'GeneralError')
