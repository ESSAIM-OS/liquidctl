import tempfile
import unittest
from pathlib import Path

from liquidctl.essaim_bridge import clamp_pump_speed, normalize_status_rows
from liquidctl.linux_fast import (
    DEFAULT_ESSAIM_EXCLUDES,
    DRIVER_USB_INDEX,
    is_excluded,
    parse_exclude_spec,
    scan_sysfs_usb_ids,
    select_driver_modules,
)


class TestLinuxFastOptimizations(unittest.TestCase):
    def test_sysfs_usb_scanner_and_driver_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # NZXT Kraken X53 (1e71:2007) -> kraken3
            d1 = root / "1-3"
            d1.mkdir()
            (d1 / "idVendor").write_text("1e71\n", encoding="ascii")
            (d1 / "idProduct").write_text("2007\n", encoding="ascii")

            # Gigabyte IT5711 (048d:5711) & IT5702 (048d:5702) -> excluded for Essaim OS
            d2 = root / "1-7"
            d2.mkdir()
            (d2 / "idVendor").write_text("048d\n", encoding="ascii")
            (d2 / "idProduct").write_text("5702\n", encoding="ascii")

            # ASUS Ryujin III (0b05:1988) -> MUST NOT be excluded even though ASUS Aura MB HIDs are excluded!
            d3 = root / "1-8"
            d3.mkdir()
            (d3 / "idVendor").write_text("0b05\n", encoding="ascii")
            (d3 / "idProduct").write_text("1988\n", encoding="ascii")

            # ASUS Aura MB HID (0b05:19af) -> excluded for Essaim OS
            d4 = root / "1-9"
            d4.mkdir()
            (d4 / "idVendor").write_text("0b05\n", encoding="ascii")
            (d4 / "idProduct").write_text("19af\n", encoding="ascii")

            present = scan_sysfs_usb_ids(root)
            self.assertEqual(
                present,
                {(0x1E71, 0x2007), (0x048D, 0x5702), (0x0B05, 0x1988), (0x0B05, 0x19AF)},
            )
            mods = select_driver_modules(present, excludes=DEFAULT_ESSAIM_EXCLUDES)
            self.assertEqual(mods, {"kraken3", "asus_ryujin"})

    def test_empty_usb_loads_zero_drivers(self):
        self.assertEqual(select_driver_modules(set(), excludes=DEFAULT_ESSAIM_EXCLUDES), set())
        self.assertEqual(select_driver_modules({(0x048D, 0x5711), (0x125F, 0x7601)}, excludes=DEFAULT_ESSAIM_EXCLUDES), set())

    def test_parse_exclude_spec(self):
        rules = parse_exclude_spec("048d:*, 0b05:19af, 2516:0051")
        self.assertTrue(is_excluded(0x048D, 0x5711, rules))
        self.assertTrue(is_excluded(0x048D, 0x8297, rules))
        self.assertTrue(is_excluded(0x0B05, 0x19AF, rules))
        self.assertFalse(is_excluded(0x0B05, 0x1988, rules))

    def test_all_driver_usb_index_entries_valid(self):
        self.assertGreaterEqual(len(DRIVER_USB_INDEX), 20)
        for mod, pairs in DRIVER_USB_INDEX.items():
            self.assertTrue(pairs, f"{mod} should list at least one VID:PID")
            for vid, pid in pairs:
                self.assertTrue(0 <= vid <= 0xFFFF and 0 <= pid <= 0xFFFF)

    def test_essaim_bridge_normalization_and_pump_clamp(self):
        self.assertEqual(clamp_pump_speed(0), 40)
        self.assertEqual(clamp_pump_speed(25), 40)
        self.assertEqual(clamp_pump_speed(75), 75)
        self.assertEqual(clamp_pump_speed(150), 100)

        norm = normalize_status_rows(
            description="NZXT Kraken X (X53, X63 or X73)",
            vendor_id=0x1E71,
            product_id=0x2007,
            bus="hid",
            address="/dev/hidraw2",
            rows=[
                ("Liquid temperature", 34.6, "°C"),
                ("Pump speed", 2310, "rpm"),
                ("Pump duty", 72, "%"),
                ("Fan 1 speed", 1180, "rpm"),
                ("Fan 1 duty", 48, "%"),
            ],
        )
        self.assertEqual(norm["liquid_temp_c"], 34.6)
        self.assertEqual(norm["pump_rpm"], 2310)
        self.assertEqual(norm["pump_duty"], 72)
        self.assertEqual(norm["fans"], [{"label": "Fan 1", "rpm": 1180, "duty": 48}])
        self.assertTrue(norm["capabilities"]["pump"])
        self.assertTrue(norm["capabilities"]["rgb"])

        psu = normalize_status_rows(
            description="Corsair HX1000i",
            vendor_id=0x1B1C,
            product_id=0x1C07,
            bus="hid",
            address="/dev/hidraw4",
            rows=[
                ("Total power output", 342.5, "W"),
                ("Estimated input power", 371.2, "W"),
                ("Estimated efficiency", 92.3, "%"),
                ("VRM temperature", 46.0, "°C"),
            ],
        )
        self.assertEqual(psu["psu"]["output_power_w"], 342.5)
        self.assertEqual(psu["psu"]["input_power_w"], 371.2)
        self.assertTrue(psu["capabilities"]["psu"])


if __name__ == "__main__":
    unittest.main()
