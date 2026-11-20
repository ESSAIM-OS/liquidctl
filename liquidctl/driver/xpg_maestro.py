"""liquidctl drivers for XPG Maestro Plus air coolers.

Supported devices:

- XPG Maestro Plus 62DA

Copyright Essaim OS and contributors
SPDX-License-Identifier: GPL-3.0-or-later
"""

# uses the psf/black style

import logging

from liquidctl.driver.usb import UsbDriver
from liquidctl.error import NotSupportedByDevice
from liquidctl.util import LazyHexRepr, clamp

_LOGGER = logging.getLogger(__name__)

_REPORT_ID = 0x07
_REPORT_LENGTH = 64
_CMD_DISPLAY = 0xA1
_DEFAULT_DELAY = 0x0A
_DECIMAL_NONE = 0x0A

_FLAG_ALL_ON = 0x07
_FLAG_NO_LABEL = 0x06
_FLAG_OFF = 0x00

_BM_REQUEST_TYPE_OUT = 0x21
_B_REQUEST_SET_REPORT = 0x09
_W_VALUE_OUTPUT_REPORT = 0x0207
_W_INDEX = 0x0000

_VALID_CHANNELS = ("display", "screen", "lcd")


def _parse_stats_value(value):
    """Parse `(temp, ram_pct, cpu_pct)` from a sequence or comma-separated string."""
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    else:
        raise ValueError("screen stats value must be 'temp,ram,cpu' or a 3-item sequence")

    if len(parts) != 3:
        raise ValueError("screen stats require exactly three values: temp,ram,cpu")

    return tuple(int(round(float(part))) for part in parts)


class XpgMaestro(UsbDriver):
    """XPG Maestro Plus 62DA CPU cooler 7-segment display."""

    _MATCHES = [
        (0x125F, 0x7601, "XPG Maestro Plus 62DA", {}),
    ]

    def initialize(self, **kwargs):
        """Initialize the device."""
        _LOGGER.info("no initialization required")
        return []

    def get_status(self, **kwargs):
        """Get a status report."""
        _LOGGER.info("no status available")
        return []

    def set_color(self, channel, mode, colors, **kwargs):
        """Not supported by this device."""
        raise NotSupportedByDevice()

    def set_speed_profile(self, channel, profile, **kwargs):
        """Not supported by this device."""
        raise NotSupportedByDevice()

    def set_fixed_speed(self, channel, duty, **kwargs):
        """Not supported by this device."""
        raise NotSupportedByDevice()

    def set_screen(self, channel, mode, value, show_labels=True, delay=_DEFAULT_DELAY, **kwargs):
        """Set the 7-segment display content or turn it off.

        Unstable.

        Supported channels, modes and values:

        | Channel | Mode | Value |
        | --- | --- | --- |
        | `display` | `celsius` | `temp,ram,cpu` (e.g. `45,30,18`) |
        | `display` | `fahrenheit` | `temp,ram,cpu` (e.g. `113,30,18`) |
        | `display` | `stats` | `temp,ram,cpu` (Celsius by default) |
        | `display` | `off` | — |
        """
        if channel.lower() not in _VALID_CHANNELS:
            raise ValueError(f"unsupported channel: {channel!r}")
        if mode is None:
            raise ValueError("no screen mode specified")

        mode_l = mode.lower()
        if mode_l == "off":
            packet = self._build_report(
                0,
                0,
                0,
                celsius=True,
                show_labels=False,
                enabled=False,
                delay=delay,
            )
        elif mode_l in ("celsius", "fahrenheit", "stats"):
            if value is None:
                raise ValueError(f"mode {mode_l!r} requires a 'temp,ram,cpu' value")
            temp, ram_pct, cpu_pct = _parse_stats_value(value)
            celsius = mode_l != "fahrenheit"
            packet = self._build_report(
                temp,
                ram_pct,
                cpu_pct,
                celsius=celsius,
                show_labels=show_labels,
                enabled=True,
                delay=delay,
            )
        else:
            raise ValueError(f"unsupported screen mode: {mode!r}")

        self._send_report(packet)

    @staticmethod
    def _build_report(temp, ram_pct, cpu_pct, *, celsius, show_labels, enabled, delay):
        packet = bytearray(_REPORT_LENGTH)
        packet[0] = _REPORT_ID
        packet[1] = _CMD_DISPLAY
        packet[2] = 0x01 if celsius else 0x00
        packet[6] = clamp(delay, 0, 255)
        packet[7] = clamp(temp, 0, 255)
        packet[8] = _DECIMAL_NONE
        packet[9] = clamp(ram_pct, 0, 100)
        packet[10] = clamp(cpu_pct, 0, 100)
        if not enabled:
            flag = _FLAG_OFF
        elif show_labels:
            flag = _FLAG_ALL_ON
        else:
            flag = _FLAG_NO_LABEL
        packet[11] = flag
        packet[12] = flag
        packet[13] = flag
        return bytes(packet)

    def _send_report(self, packet):
        _LOGGER.debug("sending display report: %r", LazyHexRepr(packet))
        self.device.claim()
        try:
            sent = self.device.ctrl_transfer(
                _BM_REQUEST_TYPE_OUT,
                _B_REQUEST_SET_REPORT,
                _W_VALUE_OUTPUT_REPORT,
                _W_INDEX,
                packet,
            )
        finally:
            self.device.release()

        if sent is not None and sent != len(packet):
            raise OSError(f"short USB SET_REPORT transfer: {sent}/{len(packet)} bytes")
