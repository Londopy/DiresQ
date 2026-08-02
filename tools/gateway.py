"""Reads check-in packets and posts them to DiresQ.

This is the piece that would sit next to the radio. It doesn't know anything
about radios — it reads base64 packets, one per line, and forwards them. Point
it at a serial port and it's a LoRa gateway. Point it at a pipe and it's a
test harness. The server can't tell the difference, which is the point.

    # send one check-in as yourself
    python tools/gateway.py send --responder 1 --key <hex> \\
        --lat 29.7858 --lng -95.8244

    # forward whatever arrives on stdin
    python tools/gateway.py listen

    # forward whatever a radio module prints over USB
    python tools/gateway.py listen --serial COM3

Get a key with `flask --app app node-key <username>`.

The serial mode needs pyserial, which is not in requirements.txt because
nothing else needs it and we have no hardware to test it against. `listen`
over stdin works with nothing installed, and is what the tests exercise.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import transport  # noqa: E402

DEFAULT_URL = "http://127.0.0.1:5000/api/uplink"


def post(url: str, packet: bytes, timeout: float = 5.0) -> dict:
    """Hand one packet to the server and return whatever it says."""
    body = json.dumps({"packet": base64.b64encode(packet).decode()}).encode()
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as err:
        # A rejected packet is normal traffic, not a crash. Print why and let
        # the caller carry on with the next one.
        return {"error": err.read().decode(errors="replace"), "status": err.code}
    except (urllib.error.URLError, OSError) as err:
        # The server being unreachable is the situation this whole feature
        # exists for. Dying here would mean the gateway goes down exactly when
        # the network does, and takes every queued packet with it.
        return {"error": f"could not reach {url}: {err}", "unreachable": True}


def build(args) -> bytes:
    body = transport.pack_checkin(args.responder, args.lat, args.lng, args.age)
    return transport.seal(body, args.key)


def send(args) -> int:
    result = post(args.url, build(args))
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def listen(args) -> int:
    """Forward base64 packets, one per line, until the source runs out."""
    if args.serial:
        try:
            import serial  # noqa: PLC0415
        except ImportError:
            print("serial mode needs pyserial: pip install pyserial",
                  file=sys.stderr)
            return 2
        source = serial.Serial(args.serial, args.baud, timeout=1)
        lines = (source.readline().decode(errors="replace") for _ in iter(int, 1))
    else:
        lines = sys.stdin

    forwarded = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            packet = base64.b64decode(line, validate=True)
        except Exception:
            # Radio noise looks exactly like this. Say so and keep listening;
            # a gateway that exits on one bad line is a gateway that's down.
            print(f"skipped, not base64: {line[:32]}", file=sys.stderr)
            continue

        result = post(args.url, packet)
        forwarded += 1
        if result.get("ok"):
            print(f"ok   responder {result['responder_id']} "
                  f"{result['bytes']} bytes at {result['at']}")
        else:
            print(f"drop {result.get('error')}", file=sys.stderr)

    print(f"forwarded {forwarded} packet(s)")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default=DEFAULT_URL)
    sub = parser.add_subparsers(dest="command", required=True)

    one = sub.add_parser("send", help="build and send a single check-in")
    one.add_argument("--responder", type=int, required=True)
    one.add_argument("--key", required=True, help="node key, hex")
    one.add_argument("--lat", type=float, required=True)
    one.add_argument("--lng", type=float, required=True)
    one.add_argument("--age", type=int, default=0,
                     help="minutes since the check-in was made")
    one.set_defaults(func=send)

    many = sub.add_parser("listen", help="forward packets from stdin or serial")
    many.add_argument("--serial", help="e.g. COM3 or /dev/ttyUSB0")
    many.add_argument("--baud", type=int, default=115200)
    many.set_defaults(func=listen)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
