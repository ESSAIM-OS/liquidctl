#!/usr/bin/env python3
"""Fast Linux single-shot JSON bridge for Essaim OS (`liquidctl-essaim`).

Combines per-boot cached initialization, status normalization, and batched
pump/fan/RGB control into a single Python process with zero conflict against
native Essaim OS RGB controllers (`048d:*`, `2516:0051`, ASUS Aura MB HIDs).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from liquidctl.linux_fast import DEFAULT_ESSAIM_EXCLUDES, is_excluded, parse_exclude_spec

INIT_CACHE_PATH = Path("/run/essaim/liquidctl-init.json")
PUMP_MIN_PCT = 40


def _boot_id() -> str:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    except OSError:
        return "unknown"


def _load_init_cache(path: Path = INIT_CACHE_PATH) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("boot_id") == _boot_id():
            return data
    except (OSError, ValueError):
        pass
    return {"boot_id": _boot_id(), "initialized": []}


def _save_init_cache(cache: Dict[str, Any], path: Path = INIT_CACHE_PATH) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def normalize_status_rows(
    description: str,
    vendor_id: Optional[int],
    product_id: Optional[int],
    bus: Optional[str],
    address: Optional[str],
    rows: Sequence[Tuple[str, Any, str]],
) -> Dict[str, Any]:
    """Normalize raw liquidctl status tuples `(key, value, unit)` into a clean Essaim JSON object."""
    liquid_temp_c: Optional[float] = None
    pump_rpm: Optional[int] = None
    pump_duty: Optional[int] = None
    fans: List[Dict[str, Any]] = []
    fan_by_label: Dict[str, Dict[str, Any]] = {}
    psu: Dict[str, Any] = {}
    raw_status: List[Dict[str, Any]] = []

    for key, val, unit in rows:
        k = str(key).strip()
        kl = k.lower()
        u = str(unit or "").strip()
        raw_status.append({"key": k, "value": val, "unit": u})
        num = float(val) if isinstance(val, (int, float)) and not isinstance(val, bool) else None

        if num is None:
            continue

        if "liquid temperature" in kl or "coolant" in kl:
            liquid_temp_c = round(num, 1)
        elif "pump" in kl:
            if u.lower() == "rpm" or "speed" in kl:
                pump_rpm = int(round(num))
            elif u == "%" or "duty" in kl:
                pump_duty = int(round(num))
        elif "fan" in kl:
            base = k.replace(" speed", "").replace(" duty", "").replace(" Speed", "").replace(" Duty", "").strip()
            entry = fan_by_label.setdefault(base, {"label": base, "rpm": None, "duty": None})
            if u.lower() == "rpm" or "speed" in kl:
                entry["rpm"] = int(round(num))
            elif u == "%" or "duty" in kl:
                entry["duty"] = int(round(num))
        elif any(tok in kl for tok in ("total power", "input power", "output power", "estimated input power")):
            if "input" in kl:
                psu["input_power_w"] = round(num, 1)
            else:
                psu["output_power_w"] = round(num, 1)
        elif "efficiency" in kl and u == "%":
            psu["efficiency_pct"] = round(num, 1)
        elif "temperature" in kl and ("vrm" in kl or "case" in kl or "psu" in kl):
            psu["temp_c"] = round(num, 1)

    fans = list(fan_by_label.values())
    dl = description.lower()
    is_psu = bool(psu) or any(tok in dl for tok in ("psu", "hx", "rmi", "axi", "e500", "e650", "e850"))
    has_pump = pump_rpm is not None or pump_duty is not None or any(
        tok in dl for tok in ("kraken", "hydro", "h100", "h115", "h150", "h170", "ryujin", "ryuo", "coreliquid", "galahad", "d5", "asetek")
    )
    has_fans = bool(fans) or any(
        tok in dl for tok in ("commander", "smart device", "quadro", "octo", "control hub", "uni fan", "kraken", "hydro", "coreliquid")
    )
    has_rgb = not is_psu and any(
        tok in dl for tok in ("kraken", "hydro", "commander", "smart device", "hue", "coreliquid", "ryujin", "ryuo", "uni fan", "galahad")
    )

    dev_id = f"{bus or 'usb'}:{address or '0'}"
    return {
        "id": dev_id,
        "description": description,
        "vendor_id": f"{vendor_id:04x}" if vendor_id is not None else None,
        "product_id": f"{product_id:04x}" if product_id is not None else None,
        "liquid_temp_c": liquid_temp_c,
        "pump_rpm": pump_rpm,
        "pump_duty": pump_duty,
        "fans": fans,
        "psu": psu if psu else None,
        "capabilities": {
            "pump": has_pump,
            "fans": has_fans,
            "rgb": has_rgb,
            "psu": is_psu,
        },
        "raw_status": raw_status,
    }


def _configure_essaim_excludes() -> None:
    if not os.environ.get("LIQUIDCTL_EXCLUDE_DEVICES"):
        spec = ",".join(
            f"{v:04x}:*" if p is None else f"{v:04x}:{p:04x}"
            for (v, p) in sorted(DEFAULT_ESSAIM_EXCLUDES, key=lambda x: (x[0], -1 if x[1] is None else x[1]))
        )
        os.environ["LIQUIDCTL_EXCLUDE_DEVICES"] = spec


def _try_set_speed(dev: Any, channels: Sequence[str], pct: int) -> bool:
    for ch in channels:
        try:
            dev.set_fixed_speed(ch, pct)
            return True
        except Exception:
            continue
    return False


def _try_set_color(dev: Any, mode: str, rgb: Tuple[int, int, int]) -> bool:
    colors = [] if mode == "off" else [[rgb[0], rgb[1], rgb[2]]]
    for ch in ("sync", "ring", "logo", "led", "led1", "external"):
        try:
            dev.set_color(ch, mode, colors)
            return True
        except Exception:
            continue
    return False


def cmd_snapshot() -> Dict[str, Any]:
    _configure_essaim_excludes()
    from liquidctl.driver import find_liquidctl_devices
    from liquidctl.version import __version__

    excludes = parse_exclude_spec(os.environ.get("LIQUIDCTL_EXCLUDE_DEVICES", ""))
    init_cache = _load_init_cache()
    inited = set(init_cache.get("initialized", []))
    cache_dirty = False
    devices_out: List[Dict[str, Any]] = []

    for dev in find_liquidctl_devices():
        if is_excluded(getattr(dev, "vendor_id", None), getattr(dev, "product_id", None), excludes):
            continue
        key = f"{getattr(dev, 'bus', 'usb')}:{getattr(dev, 'address', '0')}:{getattr(dev, 'vendor_id', 0):04x}:{getattr(dev, 'product_id', 0):04x}"
        try:
            with dev.connect():
                if key not in inited:
                    try:
                        dev.initialize()
                    except Exception:
                        pass
                    inited.add(key)
                    cache_dirty = True
                rows = dev.get_status() or []
                devices_out.append(
                    normalize_status_rows(
                        description=dev.description,
                        vendor_id=getattr(dev, "vendor_id", None),
                        product_id=getattr(dev, "product_id", None),
                        bus=getattr(dev, "bus", None),
                        address=getattr(dev, "address", None),
                        rows=rows,
                    )
                )
        except Exception as exc:
            devices_out.append({
                "id": f"{getattr(dev, 'bus', 'usb')}:{getattr(dev, 'address', '0')}",
                "description": dev.description,
                "vendor_id": f"{dev.vendor_id:04x}" if getattr(dev, "vendor_id", None) is not None else None,
                "product_id": f"{dev.product_id:04x}" if getattr(dev, "product_id", None) is not None else None,
                "error": str(exc),
                "fans": [],
                "capabilities": {"pump": False, "fans": False, "rgb": False, "psu": False},
            })

    if cache_dirty:
        init_cache["initialized"] = sorted(inited)
        _save_init_cache(init_cache)

    return {"available": True, "version": __version__, "devices": devices_out}


def clamp_pump_speed(speed: int) -> int:
    """Enforce hard hardware safety floor on AIO pumps (never allow < 40%)."""
    return max(PUMP_MIN_PCT, min(100, int(speed)))


def cmd_apply(payload: Dict[str, Any]) -> Dict[str, Any]:
    _configure_essaim_excludes()
    from liquidctl.driver import find_liquidctl_devices

    excludes = parse_exclude_spec(os.environ.get("LIQUIDCTL_EXCLUDE_DEVICES", ""))
    pump_speed = payload.get("pump_speed")
    fan_speed = payload.get("fan_speed")
    rgb = payload.get("rgb")

    applied = 0
    errors: List[str] = []

    for dev in find_liquidctl_devices():
        if is_excluded(getattr(dev, "vendor_id", None), getattr(dev, "product_id", None), excludes):
            continue
        try:
            with dev.connect():
                changed = False
                if pump_speed is not None:
                    safe_pump = clamp_pump_speed(int(pump_speed))
                    if _try_set_speed(dev, ("pump",), safe_pump):
                        changed = True
                if fan_speed is not None:
                    safe_fan = max(20, min(100, int(fan_speed)))
                    if _try_set_speed(dev, ("fan", "fans", "fan1", "sync"), safe_fan):
                        changed = True
                if isinstance(rgb, dict):
                    mode = str(rgb.get("mode", "fixed")).lower()
                    hex_c = str(rgb.get("color", "#f5a623")).lstrip("#")
                    if len(hex_c) == 6:
                        c = (int(hex_c[0:2], 16), int(hex_c[2:4], 16), int(hex_c[4:6], 16))
                    else:
                        c = (245, 166, 35)
                    if mode == "off" or c == (0, 0, 0):
                        if _try_set_color(dev, "off", (0, 0, 0)) or _try_set_color(dev, "fixed", (0, 0, 0)):
                            changed = True
                    else:
                        if _try_set_color(dev, "fixed", c):
                            changed = True
                if changed:
                    applied += 1
        except Exception as exc:
            errors.append(f"{dev.description}: {exc}")

    return {"ok": len(errors) == 0, "applied": applied, "errors": errors}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="liquidctl-essaim", description="Fast Linux JSON bridge for Essaim OS.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("snapshot", help="Initialize (cached per boot) and output normalized JSON status.")
    ap = sub.add_parser("apply", help="Apply batched pump/fan/RGB JSON settings.")
    ap.add_argument("--json", dest="json_payload", required=True, help="JSON settings object.")
    args = parser.parse_args(argv)

    if args.cmd == "snapshot":
        print(json.dumps(cmd_snapshot()))
        return 0
    if args.cmd == "apply":
        data = json.loads(args.json_payload)
        res = cmd_apply(data if isinstance(data, dict) else {})
        print(json.dumps(res))
        return 0 if res.get("ok") else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
