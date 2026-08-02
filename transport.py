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
the message fits: a check-in is 14 bytes, which clears every LoRa data rate
except the very slowest, and the encoding round-trips to about a metre.

Sizes worth knowing, for anyone picking this up:

    LoRaWAN US915 DR0   11 bytes   too small, would need splitting
    LoRaWAN US915 DR1   53 bytes   fits
    Meshtastic         237 bytes   fits comfortably
    Raw SX1276         255 bytes   fits

MAX_PACKET_BYTES is set to the DR1 figure, because designing against the
generous limit is how you find out at the demo that it doesn't fit.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

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

# version, type, responder id, lat, lng, age in minutes
# B B H i i H  ->  1+1+2+4+4+2 = 14 bytes
LAYOUT = struct.Struct("!BBHiiH")

# Sixteen bits of responder id, unsigned. Fine for a county, not for a state.
MAX_RESPONDER_ID = 0xFFFF

# Age is how long ago the check-in was made, in minutes. Sending the age
# rather than a timestamp saves four bytes and sidesteps the fact that a
# battery-powered node's clock is not to be trusted.
MAX_AGE_MINUTES = 0xFFFF


class PacketError(ValueError):
    """Malformed packet. Radio links corrupt things; say so and move on."""


@dataclass(frozen=True)
class Checkin:
    responder_id: int
    lat: float
    lng: float
    age_minutes: int


def pack_checkin(responder_id: int, lat: float, lng: float,
                 age_minutes: int = 0) -> bytes:
    """Encode a check-in small enough to fit on a radio."""
    if not 0 <= responder_id <= MAX_RESPONDER_ID:
        raise PacketError(f"responder id {responder_id} does not fit in 16 bits")
    if not -90 <= lat <= 90 or not -180 <= lng <= 180:
        raise PacketError("coordinates out of range")

    packet = LAYOUT.pack(
        PROTOCOL_VERSION,
        PACKET_CHECKIN,
        responder_id,
        round(lat * COORD_SCALE),
        round(lng * COORD_SCALE),
        max(0, min(int(age_minutes), MAX_AGE_MINUTES)),
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

    version, kind, responder_id, lat, lng, age = LAYOUT.unpack(packet)

    if version != PROTOCOL_VERSION:
        raise PacketError(f"protocol version {version}, we speak {PROTOCOL_VERSION}")
    if kind != PACKET_CHECKIN:
        raise PacketError(f"packet type {kind} is not a check-in")

    return Checkin(
        responder_id=responder_id,
        lat=lat / COORD_SCALE,
        lng=lng / COORD_SCALE,
        age_minutes=age,
    )
