# =============================================================================
# fsm
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

from functools import wraps
import logging
from time import time
from pexpect import EOF
from condoor.exceptions import ConnectionError
from condoor.utils import pattern_to_str
from inspect import isclass

from os import getpid
logger = logging.getLogger("{}-{}".format(getpid(), __name__))


def action(func):
    @wraps(func)
    def with_logging(*args, **kwargs):
        logger.debug("A={}".format(func.__name__))
        return func(*args, **kwargs)
    return with_logging


class FSM(object):
    """This class represents Finite State Machine for the current device connection. Here is the
        example of usage::

            to be done


        The example action::

            def send_newline(ctx):
                ctx.ctrl.sendline()
                return True

            def error(ctx):
                ctx.message = "Filesystem error"
                return False

            def readonly(ctx):
                ctx.message = "Filesystem is readonly"
                return False

        The ctx object description refer to :class:`condoor.controllers.fsm.FSM`.

        If the action returns True then the FSM continues processing. If the action returns False then FSM stops
        and the error message passed back to the ctx object is posted to the log.


        The FSM state is the integer number. The FSM starts with initial ``state=0`` and finishes if the ``next_state``
        is set to -1.

        If action returns False then FSM returns False. FSM returns True if reaches the -1 state.

        """

    class Context(object):
        _slots__ = ['fsm_name', 'ctrl', 'event', 'state', 'finished', 'msg']
        fsm_name = "FSM"
        ctrl = None
        event = None
        state = 0
        finished = False
        msg = ""

        def __init__(self, fsm_name, device):
            """This is a class constructor.

            Args:
                fsm_name (str): Name of the FSM. This is used for logging.
                ctrl (object): The controller object.
            """
            self.device = device
            self.ctrl = device.ctrl
            self.fsm_name = fsm_name

        def __str__(self):
            """Returns the string representing the context"""
            return "FSM Context:E={},S={},FI={},M='{}'".format(
                self.event, self.state, self.finished, self.msg)

    def __init__(self, name, device, events, transitions, init_pattern=None, timeout=300, searchwindowsize=-1,
                 max_transitions=20):
        """This is a FSM class constructor.

        Args:
            name (str): Name of the state machine used for logging purposes. Can't be *None*
            ctrl (object): Controller class representing the connection to the device
            events (list): List of expected strings or pexpect.TIMEOUT exception expected from the device.
            transitions (list): List of tuples in defining the state machine transitions.
            init_pattern (str): The pattern that was expected in the previous operation.
            timeout (int): Timeout between states in seconds. Defaults to 300 seconds.
            searchwindowsize (int): The size of search window. Defaults to -1.
            max_transitions (int): Max number of transitions allowed before quiting the FSM.

        The transition tuple format is as follows::

            (event, [list_of_states], next_state, action, timeout)

        - event (str): string from the `events` list which is expected to be received from device.
        - list_of_states (list): List of FSM states that triggers the action in case of event occurrence.
        - next_state (int): Next state for FSM transition.
        - action (func): function to be executed if the current FSM state belongs to `list_of_states` and the `event`
          occurred. The action can be also *None* then FSM transits to the next state without any action. Action
          can be also the exception, which is raised and FSM stops.
        """
        self.events = events
        self.device = device
        self.ctrl = device.ctrl
        self.timeout = timeout
        self.searchwindowsize = searchwindowsize
        self.name = name
        self.init_pattern = init_pattern
        self.max_transitions = max_transitions

        self.transition_table = self._compile(transitions, events)

    def _compile(self, transitions, events):
        compiled = {}
        for transition in transitions:
            event, states, new_state, act, timeout = transition
            if not isinstance(states, list):
                states = list(states)
            try:
                event_index = events.index(event)
            except ValueError:
                logger.debug("Transition for non-existing event: {}".format(
                    event if isinstance(event, str) else event.pattern))
            else:
                for state in states:
                    key = (event_index, state)
                    compiled[key] = (new_state, act, timeout)

        return compiled

    def run(self):
        """This method starts the FSM.

            Returns:
                boolean: True if FSM reaches the last state or false if the exception or error message was raised
        """
        ctx = FSM.Context(self.name, self.device)
        transition_counter = 0
        timeout = self.timeout
        logger.debug("{} Start".format(self.name))
        while transition_counter < self.max_transitions:
            transition_counter += 1
            try:
                start_time = time()
                if self.init_pattern is None:
                    ctx.event = self.ctrl.expect(self.events, searchwindowsize=self.searchwindowsize, timeout=timeout)
                else:
                    logger.debug("INIT_PATTERN={}".format(pattern_to_str(self.init_pattern)))
                    ctx.event = self.events.index(self.init_pattern)
                    self.init_pattern = None
                finish_time = time() - start_time
                key = (ctx.event, ctx.state)
                ctx.pattern = self.events[ctx.event]

                if key in self.transition_table:
                    transition = self.transition_table[key]
                    next_state, action_instance, next_timeout = transition
                    logger.debug("E={},S={},T={},RT={:.2f}".format(ctx.event, ctx.state, timeout, finish_time))
                    if callable(action_instance) and not isclass(action_instance):
                        if not action_instance(ctx):
                            logger.critical("Error: {}".format(ctx.msg))
                            return False
                    elif isinstance(action_instance, Exception):
                        logger.debug("A=Exception {}".format(action_instance))
                        raise action_instance
                    elif action_instance is None:
                        logger.debug("A=None")
                    else:
                        logger.error("FSM Action is not callable: {}".format(str(action_instance)))
                        raise RuntimeWarning("FSM Action is not callable")

                    if next_timeout != 0:  # no change if set to 0
                        timeout = next_timeout
                    ctx.state = next_state
                    logger.debug("NS={},NT={}".format(next_state, timeout))

                else:
                    logger.warning("Unknown transition: EVENT={},STATE={}".format(ctx.event, ctx.state))
                    continue

            except EOF:
                raise ConnectionError("Session closed unexpectedly", self.ctrl.hostname)

            if ctx.finished or next_state == -1:
                logger.debug("{} Stop at E={},S={}".format(self.name, ctx.event, ctx.state))
                return True

        # check while else if even exists
        logger.error("FSM looped. Exiting")
        return False
