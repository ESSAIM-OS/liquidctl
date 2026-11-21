"""Fast Linux sysfs USB pre-filtering & Essaim OS conflict exclusion for liquidctl.

Avoids eagerly importing all 24 driver modules and avoids touching devices
already driven natively in Rust by essaim-agent (Gigabyte ITE RGB, Wraith Prism,
ASUS Aura motherboard HIDs, NVIDIA I2C).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterable, Optional, Set, Tuple

VidPid = Tuple[int, int]
ExcludeRule = Tuple[int, Optional[int]]  # (vid, pid or None for wildcard)

# Exact USB (VID, PID) table matching every USB driver in liquidctl/driver/*.py
DRIVER_USB_INDEX: Dict[str, Tuple[VidPid, ...]] = {
    "aquacomputer": (
        (0x0C70, 0xF00E), (0x0C70, 0xF00A), (0x0C70, 0xF010),
        (0x0C70, 0xF011), (0x0C70, 0xF00D),
    ),
    "asetek": (
        (0x2433, 0xB200), (0x1B1C, 0x0C02), (0x1B1C, 0x0C03),
        (0x1B1C, 0x0C07), (0x1B1C, 0x0C08), (0x1B1C, 0x0C09), (0x1B1C, 0x0C0A),
    ),
    "asetek_pro": ((0x1B1C, 0x0C12), (0x1B1C, 0x0C13), (0x1B1C, 0x0C15)),
    "asus_ryujin": (
        (0x0B05, 0x1988), (0x0B05, 0x1BCB), (0x0B05, 0x1AA2),
        (0x0B05, 0x1ADE), (0x0B05, 0x1ADA),
    ),
    "asus_ryuo": ((0x0B05, 0x1887),),
    "aura_led": ((0x0B05, 0x19AF), (0x0B05, 0x1939), (0x0B05, 0x18F3)),
    "commander_core": ((0x1B1C, 0x0C1C), (0x1B1C, 0x0C2A), (0x1B1C, 0x0C32)),
    "commander_pro": ((0x1B1C, 0x0C10), (0x1B1C, 0x0C0B), (0x1B1C, 0x0C1A), (0x1B1C, 0x1D00)),
    "control_hub": ((0x1E71, 0x2022),),
    "coolit": ((0x1B1C, 0x0C04),),
    "corsair_hid_psu": (
        (0x1B1C, 0x1C05), (0x1B1C, 0x1C06), (0x1B1C, 0x1C07), (0x1B1C, 0x1C08),
        (0x1B1C, 0x1C23), (0x1B1C, 0x1C27), (0x1B1C, 0x1C0A), (0x1B1C, 0x1C0B),
        (0x1B1C, 0x1C0C), (0x1B1C, 0x1C0D), (0x1B1C, 0x1C1E), (0x1B1C, 0x1C1F),
    ),
    "ga2_lcd": ((0x0416, 0x7395),),
    "hydro_platinum": (
        (0x1B1C, 0x0C18), (0x1B1C, 0x0C19), (0x1B1C, 0x0C17), (0x1B1C, 0x0C29),
        (0x1B1C, 0x0C20), (0x1B1C, 0x0C21), (0x1B1C, 0x0C22), (0x1B1C, 0x0C35),
        (0x1B1C, 0x0C36), (0x1B1C, 0x0C37), (0x1B1C, 0x0C40), (0x1B1C, 0x0C41),
    ),
    "kraken2": ((0x1E71, 0x170E), (0x1E71, 0x1715)),
    "kraken3": (
        (0x1E71, 0x2007), (0x1E71, 0x2014), (0x1E71, 0x3008), (0x1E71, 0x300C),
        (0x1E71, 0x300E), (0x1E71, 0x3012), (0x1E71, 0x3014),
    ),
    "lianli_uni": (
        (0x0CF2, 0x7750), (0x0CF2, 0xA100), (0x0CF2, 0xA101), (0x0CF2, 0xA102),
        (0x0CF2, 0xA103), (0x0CF2, 0xA104), (0x0CF2, 0xA105),
    ),
    "msi": ((0x0DB0, 0xB130), (0x0DB0, 0xCA00), (0x0DB0, 0xCA02)),
    "nzxt_epsu": ((0x7793, 0x5911), (0x7793, 0x5912), (0x7793, 0x2500)),
    "rgb_fusion2": ((0x048D, 0x5702), (0x048D, 0x8297)),
    "smart_device": (
        (0x1E71, 0x1714), (0x1E71, 0x1711), (0x1E71, 0x2006), (0x1E71, 0x200D),
        (0x1E71, 0x200F), (0x1E71, 0x2001), (0x1E71, 0x2002), (0x1E71, 0x2009),
        (0x1E71, 0x200E), (0x1E71, 0x2010), (0x1E71, 0x2011), (0x1E71, 0x2019),
        (0x1E71, 0x201F), (0x1E71, 0x2020), (0x1E71, 0x2015), (0x1E71, 0x2012),
        (0x1E71, 0x2021),
    ),
}

# Devices already handled natively in Rust by essaim-agent (chassis.rs):
# - Gigabyte ITE RGB Fusion 2 motherboards (048d:*)
# - AMD Wraith Prism (2516:0051)
# - ASUS Aura motherboard HID controllers (0b05:18f3, 1939, 19af, 1872, 1867)
# Note: ASUS Ryujin / Ryuo AIOs (0b05:1988, 1bcb, 1aa2, 1ade, 1ada, 1887) remain ENABLED.
DEFAULT_ESSAIM_EXCLUDES: Set[ExcludeRule] = {
    (0x048D, None),
    (0x2516, 0x0051),
    (0x0B05, 0x18F3),
    (0x0B05, 0x1939),
    (0x0B05, 0x19AF),
    (0x0B05, 0x1872),
    (0x0B05, 0x1867),
}


def parse_exclude_spec(raw: Optional[str]) -> Set[ExcludeRule]:
    """Parse comma-separated VID:PID rules like '048d:*,0b05:19af'."""
    rules: Set[ExcludeRule] = set()
    if not raw:
        return rules
    for item in raw.split(","):
        token = item.strip().lower()
        if not token:
            continue
        if ":" in token:
            v_str, p_str = token.split(":", 1)
            try:
                vid = int(v_str, 16)
                pid = None if p_str in ("*", "") else int(p_str, 16)
                rules.add((vid, pid))
            except ValueError:
                continue
        else:
            try:
                rules.add((int(token, 16), None))
            except ValueError:
                continue
    return rules


def is_excluded(vid: Optional[int], pid: Optional[int], excludes: Iterable[ExcludeRule]) -> bool:
    if vid is None:
        return False
    for ex_vid, ex_pid in excludes:
        if ex_vid == vid and (ex_pid is None or ex_pid == pid):
            return True
    return False


def scan_sysfs_usb_ids(sysfs_root: Path = Path("/sys/bus/usb/devices")) -> Optional[Set[VidPid]]:
    """Read all present USB (VID, PID) pairs from Linux sysfs in < 0.5 ms.

    Returns an empty set on Linux environments without a USB subsystem (e.g. WSL2 / containers),
    and None only if sysfs itself is unavailable (caller falls back to eager import).
    """
    if not sysfs_root.is_dir():
        if sysfs_root == Path("/sys/bus/usb/devices") and Path("/sys").is_dir():
            return set()
        return None
    present: Set[VidPid] = set()
    try:
        entries = list(sysfs_root.iterdir())
    except OSError:
        return None
    for entry in entries:
        v_file = entry / "idVendor"
        p_file = entry / "idProduct"
        if not (v_file.is_file() and p_file.is_file()):
            continue
        try:
            vid = int(v_file.read_text(encoding="ascii").strip(), 16)
            pid = int(p_file.read_text(encoding="ascii").strip(), 16)
            present.add((vid, pid))
        except (OSError, ValueError):
            continue
    return present


def select_driver_modules(
    present_ids: Set[VidPid],
    excludes: Optional[Iterable[ExcludeRule]] = None,
) -> Set[str]:
    """Return only the liquidctl driver module names matching present non-excluded USB devices."""
    excl = list(excludes) if excludes is not None else []
    filtered = {(v, p) for (v, p) in present_ids if not is_excluded(v, p, excl)}
    if not filtered:
        return set()
    modules: Set[str] = set()
    for mod_name, pairs in DRIVER_USB_INDEX.items():
        if any(pair in filtered for pair in pairs):
            modules.add(mod_name)
    return modules


def env_excludes() -> Set[ExcludeRule]:
    raw = os.environ.get("LIQUIDCTL_EXCLUDE_DEVICES", "")
    return parse_exclude_spec(raw)
