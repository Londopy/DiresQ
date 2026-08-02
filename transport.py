"""How a check-in reaches the server.

Right now there is one way in: an HTTP POST from a phone with signal. That is
the assumption the whole app rests on, and it is the assumption a disaster
breaks first.

This module is the seam. It defines the *packet* rather than the radio, so a
check-in is a fixed number of bytes regardless of what carries it. Today those
bytes arrive base64'd inside an HTTP body from `/api/uplink`. A LoRa gateway
would hand over the same bytes off a 915 MHz radio and nothing downstream
would know the difference.

We have not built the radio. We do not have the hardware and we are not going
to pretend we tested something we didn't. What we can honestly claim is that
the message fits: a check-in is 14 bytes of body plus a 4-byte signature,
which clears every LoRa data rate except the very slowest, and the encoding
round-trips to about a metre.

The signature matters more here than it would over HTTPS. There is no
transport security on a radio link — anyone with a $12 module can hear the
whole channel and transmit on it — so the packet has to carry its own proof
that it came from the node it claims. Every uplink is verified against that
responder's key before a single row is written.

Sizes worth knowing, for anyone picking this up:

    LoRaWAN US915 DR0   11 bytes   too small, would need splitting
    LoRaWAN US915 DR1   53 bytes   fits
    Meshtastic         237 bytes   fits comfortably
    Raw SX1276         255 bytes   fits

MAX_PACKET_BYTES is set to the DR1 figure, because designing against the
generous limit is how you find out at the demo that it doesn't fit.
"""

from __future__ import annotations

import hmac
import secrets
import struct
from dataclasses import dataclass
from hashlib import sha256

PROTOCOL_VERSION = 1

# The smallest payload we're willing to design for. See the table above.
MAX_PACKET_BYTES = 53

# One byte of packet type, so a report or a status change can be added later
# without a second parser.
PACKET_CHECKIN = 1

# Coordinates go over as integers. Five decimal places is about 1.1 m at the
# equator, which is far finer than a phone GPS manages in a storm, and it
# keeps a coordinate in four bytes instead of eight.
COORD_SCALE = 100_000

# version, type, responder id, lat, lng, age in minutes, counter
# B B H i i H I  ->  1+1+2+4+4+2+4 = 18 bytes
LAYOUT = struct.Struct("!BBHiiHI")

# The counter is what stops a replay. Every packet from a node carries one
# strictly greater than the last, and the server refuses anything it has
# already seen — so recording a valid packet off the air and sending it again
# gets you a 409 rather than a moved pin.
#
# Four bytes, not two. Two would wrap at 65535, and wrap handling on a replay
# defence is exactly the kind of subtlety that turns into the hole. At one
# check-in a minute, 32 bits lasts about eight thousand years; when a node
# does run out, it needs a new key, which is a rotation and not a bug.
MAX_COUNTER = 0xFFFFFFFF

# Sixteen bits of responder id, unsigned. Fine for a county, not for a state.
MAX_RESPONDER_ID = 0xFFFF

# Age is how long ago the check-in was made, in minutes. Sending the age
# rather than a timestamp saves four bytes and sidesteps the fact that a
# battery-powered node's clock is not to be trusted.
MAX_AGE_MINUTES = 0xFFFF

# Four bytes of HMAC-SHA256, truncated. Not a lot — 32 bits means a blind
# forgery lands about once in four billion tries — but a radio link has no TLS
# and a full 32-byte tag is more than twice the message it protects. The
# trade is written up in docs/offline.md rather than hidden here.
SIGNATURE_BYTES = 4

# Where the responder id sits in the body, so a gateway can find out whose key
# to check with before it has parsed anything else.
RESPONDER_ID_OFFSET = 2

KEY_BYTES = 32


class PacketError(ValueError):
    """Malformed packet. Radio links corrupt things; say so and move on."""


def new_node_key() -> str:
    """A key for one node, hex so it survives being pasted into a config."""
    return secrets.token_hex(KEY_BYTES)


def sign(body: bytes, key: str) -> bytes:
    """Truncated HMAC over the whole body, including the version byte.

    Signing the version too means nobody can talk us into an older format by
    flipping one bit.
    """
    digest = hmac.new(bytes.fromhex(key), body, sha256).digest()
    return digest[:SIGNATURE_BYTES]


def seal(body: bytes, key: str) -> bytes:
    """Body plus its signature. What actually goes over the air."""
    packet = body + sign(body, key)
    if len(packet) > MAX_PACKET_BYTES:
        raise PacketError(f"{len(packet)} bytes will not fit a LoRa payload")
    return packet


def responder_in(packet: bytes) -> int:
    """Read the claimed responder id without trusting anything else.

    Needed before verification, because you can't check a signature until you
    know whose key to check it against. Nothing is written on the strength of
    this — it only picks which key to try.
    """
    if len(packet) < RESPONDER_ID_OFFSET + 2:
        raise PacketError("packet too short to contain a responder id")
    return int.from_bytes(
        packet[RESPONDER_ID_OFFSET:RESPONDER_ID_OFFSET + 2], "big")


def unseal(packet: bytes, key: str) -> bytes:
    """Check the signature and hand back the body.

    Compared in constant time, so the failure doesn't leak how much of the tag
    was right.
    """
    if len(packet) != LAYOUT.size + SIGNATURE_BYTES:
        raise PacketError(
            f"expected {LAYOUT.size + SIGNATURE_BYTES} bytes, got {len(packet)}")

    body, tag = packet[:LAYOUT.size], packet[LAYOUT.size:]
    if not hmac.compare_digest(tag, sign(body, key)):
        raise PacketError("signature does not match")
    return body


@dataclass(frozen=True)
class Checkin:
    responder_id: int
    lat: float
    lng: float
    age_minutes: int
    counter: int = 0


def pack_checkin(responder_id: int, lat: float, lng: float,
                 age_minutes: int = 0, counter: int = 1) -> bytes:
    """Encode a check-in small enough to fit on a radio."""
    if not 0 <= responder_id <= MAX_RESPONDER_ID:
        raise PacketError(f"responder id {responder_id} does not fit in 16 bits")
    if not -90 <= lat <= 90 or not -180 <= lng <= 180:
        raise PacketError("coordinates out of range")
    if not 0 <= counter <= MAX_COUNTER:
        raise PacketError(f"counter {counter} does not fit in 32 bits")

    packet = LAYOUT.pack(
        PROTOCOL_VERSION,
        PACKET_CHECKIN,
        responder_id,
        round(lat * COORD_SCALE),
        round(lng * COORD_SCALE),
        max(0, min(int(age_minutes), MAX_AGE_MINUTES)),
        counter,
    )
    if len(packet) > MAX_PACKET_BYTES:
        # Can't happen with the layout above, but the layout is the kind of
        # thing someone extends without thinking about the radio.
        raise PacketError(f"{len(packet)} bytes will not fit a LoRa payload")
    return packet


def unpack_checkin(packet: bytes) -> Checkin:
    """Decode a check-in. Raises PacketError on anything it doesn't recognise."""
    if len(packet) != LAYOUT.size:
        raise PacketError(
            f"expected {LAYOUT.size} bytes, got {len(packet)}")

    version, kind, responder_id, lat, lng, age, counter = LAYOUT.unpack(packet)

    if version != PROTOCOL_VERSION:
        raise PacketError(f"protocol version {version}, we speak {PROTOCOL_VERSION}")
    if kind != PACKET_CHECKIN:
        raise PacketError(f"packet type {kind} is not a check-in")

    return Checkin(
        responder_id=responder_id,
        lat=lat / COORD_SCALE,
        lng=lng / COORD_SCALE,
        age_minutes=age,
        counter=counter,
    )
