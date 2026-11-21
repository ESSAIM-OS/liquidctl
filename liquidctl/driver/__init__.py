"""liquidctl buses and drivers (Linux-optimized lazy loader).

On Linux, `find_liquidctl_devices()` pre-scans `/sys/bus/usb/devices` in < 0.5 ms
and imports ONLY the driver modules whose hardware is physically plugged in,
skipping SMBus probing unless `--unsafe=smbus` is requested and honoring
`LIQUIDCTL_EXCLUDE_DEVICES` to avoid conflicts with native Essaim OS drivers.

Copyright Jonas Malaco and contributors
SPDX-License-Identifier: GPL-3.0-or-later
"""

import importlib
import os
import sys

from liquidctl.driver.base import BaseBus, find_all_subclasses
from liquidctl.linux_fast import (
    DRIVER_USB_INDEX,
    env_excludes,
    is_excluded,
    scan_sysfs_usb_ids,
    select_driver_modules,
)

_ALL_USB_DRIVERS = tuple(DRIVER_USB_INDEX.keys())
_LEGACY_ALIASES = {
    "kraken_two": "kraken2",
    "nzxt_smart_device": "smart_device",
    "seasonic": "nzxt_epsu",
}
_LOADED_ALL = False


def _load_driver(name):
    mod = importlib.import_module(f"liquidctl.driver.{name}")
    globals()[name] = mod
    for alias, target in _LEGACY_ALIASES.items():
        if target == name:
            sys.modules[f"liquidctl.driver.{alias}"] = mod
    return mod


def _load_all_drivers(include_smbus=True):
    global _LOADED_ALL
    for name in _ALL_USB_DRIVERS:
        if name not in globals():
            _load_driver(name)
    if include_smbus and sys.platform == "linux":
        for name in ("ddr4", "nvidia"):
            if name not in globals():
                _load_driver(name)
    if include_smbus:
        _LOADED_ALL = True


def _use_fast_linux():
    return sys.platform == "linux" and os.environ.get("LIQUIDCTL_FAST_LINUX", "1") != "0"


def _smbus_requested(kwargs):
    unsafe = kwargs.get("unsafe")
    if not unsafe:
        return False
    if isinstance(unsafe, str):
        items = [s.strip().lower() for s in unsafe.split(",")]
    else:
        items = [str(s).strip().lower() for s in unsafe]
    return "smbus" in items


def __getattr__(name):
    if name in _LEGACY_ALIASES:
        return _load_driver(_LEGACY_ALIASES[name])
    if name in _ALL_USB_DRIVERS or name in ("ddr4", "nvidia"):
        return _load_driver(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def find_liquidctl_devices(pick=None, **kwargs):
    """Find devices and instantiate corresponding liquidctl drivers."""
    excludes = env_excludes()
    if _use_fast_linux() and not _LOADED_ALL:
        present = scan_sysfs_usb_ids()
        if present is None:
            _load_all_drivers(include_smbus=_smbus_requested(kwargs))
        else:
            needed = select_driver_modules(present, excludes=excludes)
            for mod_name in sorted(needed):
                _load_driver(mod_name)
            if _smbus_requested(kwargs):
                for name in ("ddr4", "nvidia"):
                    _load_driver(name)
    elif not _LOADED_ALL:
        _load_all_drivers(include_smbus=(sys.platform == "linux"))

    buses = sorted(
        find_all_subclasses(BaseBus),
        key=lambda x: (x.__module__, x.__name__),
    )
    num = 0
    for bus_cls in buses:
        for dev in bus_cls().find_devices(**kwargs):
            if excludes and is_excluded(
                getattr(dev, "vendor_id", None),
                getattr(dev, "product_id", None),
                excludes,
            ):
                continue
            if pick is not None:
                if num == pick:
                    yield dev
                    return
                num += 1
            else:
                yield dev


__all__ = [
    "find_liquidctl_devices",
]
