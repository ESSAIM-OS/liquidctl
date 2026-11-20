# XPG Maestro Plus 62DA (`125F:7601`)

Observed on hardware with `bcdDevice = 0103` (`HWCX XPG MAESTRO PLUS 62DA`, WCH CH552G + TM1640 7-segment driver).

## Transport

- USB Interface 0 (`bInterfaceClass = 0x03`, HID)
- Endpoints: EP0 Control, EP1 Interrupt IN (`0x81`, 64 bytes), EP3 Interrupt OUT (`0x03`, 64 bytes)
- HID Report Descriptor: Usage Page `0x01`, Usage `0x00`, Report ID `0x07`, 63 data bytes (64 bytes total Input/Output/Feature).
- The stock firmware responds to HID Output `SET_REPORT` control transfers on EP0 (`bmRequestType=0x21`, `bRequest=0x09`, `wValue=0x0207`, `wIndex=0x0000`, 64 bytes). Writing via Linux `hidraw` routes to EP3 Interrupt OUT and `HIDIOCSFEATURE` (`0x0307`) does not light the stock display.

## Display update packet (`0xA1`, 64 bytes)

| Offset | Value | Meaning |
| --- | --- | --- |
| `0` | `0x07` | HID Report ID |
| `1` | `0xA1` | Command: display update |
| `2` | `0x01` / `0x00` | Unit: `0x01` = °C, `0x00` = °F |
| `3..5` | `0x00` | Reserved |
| `6` | `0x0A` | Display hold/delay constant (~50 ms units) |
| `7` | `0..255` | Slot 1 temperature integer (`CPU TEMP` zone) |
| `8` | `0x0A` | Decimal flag (`0x0A` = no decimal) |
| `9` | `0..100` | Slot 2 percentage (`RAM USAGE` zone) |
| `10` | `0..100` | Slot 3 percentage (`CPU USAGE` zone) |
| `11` | `0x00`/`0x06`/`0x07` | Zone 1 bitmask (`0x01`=label, `0x02`=unit, `0x04`=digits) |
| `12` | `0x00`/`0x06`/`0x07` | Zone 2 bitmask |
| `13` | `0x00`/`0x06`/`0x07` | Zone 3 bitmask |
| `14..63` | `0x00` | Zero padding |
