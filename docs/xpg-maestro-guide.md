# XPG Maestro Plus 62DA
_Driver API and source code available in [`liquidctl.driver.xpg_maestro`](../liquidctl/driver/xpg_maestro.py)._

_New in git._

## Initialization and monitoring

The XPG Maestro Plus 62DA does not require initialization and does not report any sensor telemetry over USB (its PWM fan and 5V ARGB lighting connect directly to motherboard headers).

## Screen control

Use the `display` channel (aliases: `screen`, `lcd`) with `set display screen <mode> [<value>]`:

| Mode | Value | Description |
| --- | --- | --- |
| `celsius` | `temp,ram,cpu` | Display temperature in °C, RAM %, and CPU % |
| `fahrenheit` | `temp,ram,cpu` | Display temperature in °F, RAM %, and CPU % |
| `stats` | `temp,ram,cpu` | Alias for `celsius` |
| `off` | — | Blank all display segments and labels |

```
# liquidctl set display screen celsius 46,25,18
# liquidctl set display screen fahrenheit 115,25,18
# liquidctl set display screen off
```

Note: the stock firmware expects periodic updates (~0.5–1 Hz) to keep the display lit continuously.

## Limitations

- Fan speed and ARGB lighting are controlled via the motherboard headers, not USB.
- Because the Linux driver uses USB Control transfers (`SET_REPORT` `0x0207`) rather than `hidraw`, `liquidctl` detaches `usbhid` from interface 0 on Linux when connected and restores it on disconnect.
- On Windows, PyUSB requires replacing the stock HID driver (e.g. via Zadig/WinUSB) to send raw control transfers to `125F:7601`.
