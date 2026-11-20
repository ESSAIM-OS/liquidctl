import pytest
from _testutils import MockPyusbDevice

from liquidctl.driver.xpg_maestro import XpgMaestro
from liquidctl.error import NotSupportedByDevice


@pytest.fixture
def mock_xpg_maestro():
    device = MockPyusbDevice(vendor_id=0x125F, product_id=0x7601, release_number=0x0103)
    dev = XpgMaestro(device, "XPG Maestro Plus 62DA")
    dev.connect()
    return dev


def test_xpg_maestro_initialize_and_status(mock_xpg_maestro):
    assert mock_xpg_maestro.initialize() == []
    assert mock_xpg_maestro.get_status() == []
    assert mock_xpg_maestro.vendor_id == 0x125F
    assert mock_xpg_maestro.product_id == 0x7601


def test_xpg_maestro_set_screen_celsius_string(mock_xpg_maestro):
    mock_xpg_maestro.set_screen("display", "celsius", "46,25,18")

    assert len(mock_xpg_maestro.device._sent_xfers) == 1
    xfer_type, bm_req, b_req, w_val, w_idx, payload = mock_xpg_maestro.device._sent_xfers[0]
    assert xfer_type == "ctrl_transfer"
    assert bm_req == 0x21
    assert b_req == 0x09
    assert w_val == 0x0207
    assert w_idx == 0x0000
    assert len(payload) == 64
    assert payload[:14] == bytes(
        [0x07, 0xA1, 0x01, 0x00, 0x00, 0x00, 0x0A, 46, 0x0A, 25, 18, 0x07, 0x07, 0x07]
    )
    assert payload[14:] == b"\x00" * 50


def test_xpg_maestro_set_screen_fahrenheit_and_clamping(mock_xpg_maestro):
    mock_xpg_maestro.set_screen("screen", "fahrenheit", (300, -5, 150))

    _, _, _, _, _, payload = mock_xpg_maestro.device._sent_xfers[0]
    assert payload[2] == 0x00
    assert payload[7] == 255
    assert payload[9] == 0
    assert payload[10] == 100
    assert payload[11:14] == b"\x07\x07\x07"


def test_xpg_maestro_set_screen_stats_without_labels(mock_xpg_maestro):
    mock_xpg_maestro.set_screen("lcd", "stats", "45.6, 33.2, 12.8", show_labels=False)

    _, _, _, _, _, payload = mock_xpg_maestro.device._sent_xfers[0]
    assert payload[2] == 0x01
    assert payload[7] == 46
    assert payload[9] == 33
    assert payload[10] == 13
    assert payload[11:14] == b"\x06\x06\x06"


def test_xpg_maestro_set_screen_off(mock_xpg_maestro):
    mock_xpg_maestro.set_screen("display", "off", None)

    _, _, _, _, _, payload = mock_xpg_maestro.device._sent_xfers[0]
    assert payload[0] == 0x07
    assert payload[1] == 0xA1
    assert payload[11:14] == b"\x00\x00\x00"


def test_xpg_maestro_invalid_arguments(mock_xpg_maestro):
    with pytest.raises(ValueError, match="unsupported channel"):
        mock_xpg_maestro.set_screen("fan", "celsius", "40,20,10")

    with pytest.raises(ValueError, match="unsupported screen mode"):
        mock_xpg_maestro.set_screen("display", "gif", "40,20,10")

    with pytest.raises(ValueError, match="requires"):
        mock_xpg_maestro.set_screen("display", "celsius", None)

    with pytest.raises(ValueError, match="exactly three"):
        mock_xpg_maestro.set_screen("display", "celsius", "40,20")


def test_xpg_maestro_unsupported_methods(mock_xpg_maestro):
    with pytest.raises(NotSupportedByDevice):
        mock_xpg_maestro.set_color("led", "fixed", [[255, 0, 0]])

    with pytest.raises(NotSupportedByDevice):
        mock_xpg_maestro.set_speed_profile("fan", [(30, 50)])

    with pytest.raises(NotSupportedByDevice):
        mock_xpg_maestro.set_fixed_speed("fan", 50)
