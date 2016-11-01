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

from fsm import action
from condoor.exceptions import ConnectionAuthenticationError, ConnectionError


@action
def a_send_line(text, ctx):
    ctx.ctrl.sendline(text)
    return True


@action
def a_send(text, ctx):
    ctx.ctrl.send(text)
    return True


@action
def a_send_password(password, ctx):
    if password:
        ctx.ctrl.setecho(False)
        ctx.ctrl.sendline(password)
        ctx.ctrl.setecho(True)
        return True
    else:
        ctx.ctrl.disconnect()
        raise ConnectionAuthenticationError("Password not provided", ctx.ctrl.hostname)


@action
def a_authentication_error(ctx):
    ctx.ctrl.disconnect()
    raise ConnectionAuthenticationError("Authentication failed", ctx.ctrl.hostname)


@action
def a_unable_to_connect(ctx):
    ctx.msg = "{}{}".format(ctx.ctrl.before, ctx.ctrl.after)
    return False


@action
def a_standby_console(ctx):
    ctx.device.is_console = True
    raise ConnectionError("Standby console", ctx.ctrl.hostname)


@action
def a_disconnect(ctx):
    ctx.msg = "Device is reloading"
    ctx.ctrl.platform.disconnect()
    return True


@action
def a_reload_na(ctx):
    ctx.msg = "Reload to the ROM monitor disallowed from a telnet line. " \
              "Set the configuration register boot bits to be non-zero."
    ctx.failed = True
    return False


@action
def a_connection_closed(ctx):
    ctx.msg = "Device disconnected"
    ctx.device.connected = False
    # do not stop FSM to detect the jumphost prompt
    return True


@action
def a_stays_connected(ctx):
    ctx.ctrl.connected = True
    ctx.device.connected = False
    return True


@action
def a_unexpected_prompt(ctx):
    prompt = ctx.ctrl.after
    ctx.msg = "Received the jump host prompt: '{}'".format(prompt)
    # ctx.ctrl.last_hop = ctx.detected_prompts.index(prompt)
    ctx.device.connected = False
    return False


@action
def a_expected_prompt(ctx):
    prompt = ctx.ctrl.after
    ctx.device.update_driver(prompt)
    ctx.device.update_config_mode(prompt)
    ctx.device.update_hostname(prompt)
    ctx.finished = True
    return True


@action
def a_expected_string_received(ctx):
    ctx.finished = True
    return True


@action
def a_save_last_pattern(obj, ctx):
    obj.last_pattern = ctx.pattern
    return True


@action
def a_send_boot(rommon_boot_command, ctx):
    ctx.ctrl.sendline(rommon_boot_command)
    return True


@action
def a_reconnect(ctx):
    ctx.ctrl.connect(ctx.device)
    return True


@action
def a_return_and_reconnect(ctx):
    ctx.ctrl.send("\r")
    ctx.ctrl.connect(ctx.device)
    return True


@action
def a_store_cmd_result(ctx):
    """
    FSM action to store the command result for complex state machines where exact command output is embedded in another
     commands, i.e. admin show inventory in eXR
    """
    result = ctx.ctrl.before
    # check if multi line
    index = result.find('\n')
    if index > 0:
        # remove first line
        result = result[index + 1:]
    ctx.device.last_command_result = result.replace('\r', '')
    return True
