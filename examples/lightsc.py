#!/usr/bin/env python3
# Copyright (c) 2015, Louis Opter <kalessin@kalessin.fr>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import argparse
import contextlib
import json
import socket
import sys
import uuid


class LightsClient:

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self._socket = socket.create_connection((host, port))
        self._pipeline = []
        self._batch = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()

    @classmethod
    def _make_payload(cls, method, params):
        return {
            "method": method,
            "params": params,
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
        }

    def _execute_payload(self, payload):
        self._socket.send(json.dumps(payload).encode("utf-8"))
        # FIXME: proper read loop
        response = self._socket.recv(8192).decode("utf-8")
        try:
            response = json.loads(response)
        except Exception:
            print("received invalid json: {}".format(response))

        return response

    def _jsonrpc_call(self, method, params):
        payload = self._make_payload(method, params)
        if self._batch:
            self._pipeline.append(payload)
            return
        return self._execute_payload(payload)

    def close(self):
        self._socket.close()

    @contextlib.contextmanager
    def batch(self):
        self._batch = True
        response = []
        yield response
        self._batch = False
        result = self._execute_payload(self._pipeline)
        if isinstance(result, list):
            response.extend(result)
        else:
            response.append(result)
        self._pipeline = []

    def set_light_from_hsbk(self, target, h, s, b, k, t):
        return self._jsonrpc_call("set_light_from_hsbk", [
            target, h, s, b, k, t
        ])

    def set_waveform(self, target, waveform,
                     h, s, b, k,
                     period, cycles, skew_ratio, transient):
        return self._jsonrpc_call("set_waveform", [
            target, waveform, h, s, b, k, period, cycles, skew_ratio, transient
        ])

    def saw(self, target, h, s, b, k, period, cycles, transient=True):
        return self.set_waveform(
            target, "SAW", h, s, b, k,
            cycles=cycles,
            period=period,
            skew_ratio=0.5,
            transient=transient
        )

    def sine(self, target, h, s, b, k,
             period, cycles, peak=0.5, transient=True):
        return self.set_waveform(
            target, "SINE", h, s, b, k,
            cycles=cycles,
            period=period,
            skew_ratio=peak,
            transient=transient
        )

    def half_sine(self, target, h, s, b, k, period, cycles, transient=True):
        return self.set_waveform(
            target, "HALF_SINE", h, s, b, k,
            cycles=cycles,
            period=period,
            skew_ratio=0.5,
            transient=transient
        )

    def triangle(self, target, h, s, b, k,
                 period, cycles, peak=0.5, transient=True):
        return self.set_waveform(
            target, "TRIANGLE", h, s, b, k,
            cycles=cycles,
            period=period,
            skew_ratio=peak,
            transient=transient
        )

    def square(self, target, h, s, b, k, period, cycles,
               duty_cycle=0.5, transient=True):
        return self.set_waveform(
            target, "SQUARE", h, s, b, k,
            cycles=cycles,
            period=period,
            skew_ratio=duty_cycle,
            transient=transient
        )

    def power_on(self, target):
        return self._jsonrpc_call("power_on", {"target": target})

    def power_off(self, target):
        return self._jsonrpc_call("power_off", {"target": target})

    def power_toggle(self, target):
        return self._jsonrpc_call("power_toggle", {"target": target})

    def get_light_state(self, target):
        return self._jsonrpc_call("get_light_state", [target])

    def tag(self, target, tag):
        return self._jsonrpc_call("tag", [target, tag])

    def untag(self, target, tag):
        return self._jsonrpc_call("untag", [target, tag])

    def set_label(self, target, label):
        return self._jsonrpc_call("set_label", [target, label])

    def adjust_brightness(self, target, adjustment):
        bulbs = self.get_light_state(target)["result"]
        for bulb in bulbs:
            h, s, b, k = bulb["hsbk"]
            b = max(min(b + adjustment, 1.0), 0.0)
            self.set_light_from_hsbk(bulb["label"], h, s, b, k, 500)


def _drop_to_shell(lightsc):
    c = lightsc  # noqa
    nb = "d073d501a0d5"  # noqa
    fugu = "d073d500603b"  # noqa
    neko = "d073d5018fb6"  # noqa
    middle = "d073d502e530"  # noqa

    banner = (
        "Connected to {}:{}, use the variable c to interact with your "
        "bulbs:\n\n>>> r = c.get_light_state(\"*\")".format(c.host, c.port)
    )

    try:
        from IPython import embed

        embed(header=banner + "\n>>> r")
        return
    except ImportError:
        pass

    import code

    banner += "\n>>> from pprint import pprint\n>>> pprint(r)\n"
    code.interact(banner=banner, local=locals())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="lightsc.py is an interactive lightsd Python client"
    )
    parser.add_argument(
        "host", type=str, help="The hostname or ip where lightsd is running"
    )
    parser.add_argument(
        "port", type=int, help="The port on which lightsd is listening on"
    )
    args = parser.parse_args()
    try:
        _drop_to_shell(LightsClient(args.host, args.port))
    except socket.error as ex:
        print(
            "Couldn't connect to lightsd@{}:{}, is it running? "
            "({})".format(args.host, args.port, ex.strerror),
            file=sys.stderr
        )
        sys.exit(1)
