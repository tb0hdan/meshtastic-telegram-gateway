# -*- coding: utf-8 -*-
# pylint: skip-file
import pytest
from mtg.geo.degrees import deg_to_cardinal
def test_deg_to_cardinal_north_360():
    """Test conversion for 360 degrees (North)"""
    result = deg_to_cardinal(360.0)
    assert result == "N"

def test_deg_to_cardinal_north_0():
    """Test conversion for 0 degrees (North)"""
    result = deg_to_cardinal(0.0)
    assert result == "N"

def test_deg_to_cardinal_north_boundary_high():
    """Test conversion for North boundary at high end"""
    result = deg_to_cardinal(348.76)  # Just above 348.75
    assert result == "N"

def test_deg_to_cardinal_north_boundary_low():
    """Test conversion for North boundary at low end"""
    result = deg_to_cardinal(11.25)
    assert result == "N"

def test_deg_to_cardinal_nne():
    """Test conversion for NNE (North-Northeast)"""
    result = deg_to_cardinal(22.5)  # Middle of NNE range
    assert result == "NNE"

def test_deg_to_cardinal_nne_boundary_low():
    """Test conversion for NNE boundary at low end"""
    result = deg_to_cardinal(11.26)  # Just above 11.25
    assert result == "NNE"

def test_deg_to_cardinal_nne_boundary_high():
    """Test conversion for NNE boundary at high end"""
    result = deg_to_cardinal(33.75)
    assert result == "NNE"

def test_deg_to_cardinal_ne():
    """Test conversion for NE (Northeast)"""
    result = deg_to_cardinal(45.0)
    assert result == "NE"

def test_deg_to_cardinal_ene():
    """Test conversion for ENE (East-Northeast)"""
    result = deg_to_cardinal(67.5)
    assert result == "ENE"

def test_deg_to_cardinal_east():
    """Test conversion for E (East)"""
    result = deg_to_cardinal(90.0)
    assert result == "E"

def test_deg_to_cardinal_ese():
    """Test conversion for ESE (East-Southeast)"""
    result = deg_to_cardinal(112.5)
    assert result == "ESE"

def test_deg_to_cardinal_se():
    """Test conversion for SE (Southeast)"""
    result = deg_to_cardinal(135.0)
    assert result == "SE"

def test_deg_to_cardinal_sse():
    """Test conversion for SSE (South-Southeast)"""
    result = deg_to_cardinal(157.5)
    assert result == "SSE"

def test_deg_to_cardinal_south():
    """Test conversion for S (South)"""
    result = deg_to_cardinal(180.0)
    assert result == "S"

def test_deg_to_cardinal_ssw():
    """Test conversion for SSW (South-Southwest)"""
    result = deg_to_cardinal(202.5)
    assert result == "SSW"

def test_deg_to_cardinal_sw():
    """Test conversion for SW (Southwest)"""
    result = deg_to_cardinal(225.0)
    assert result == "SW"

def test_deg_to_cardinal_wsw():
    """Test conversion for WSW (West-Southwest)"""
    result = deg_to_cardinal(247.5)
    assert result == "WSW"

def test_deg_to_cardinal_west():
    """Test conversion for W (West)"""
    result = deg_to_cardinal(270.0)
    assert result == "W"

def test_deg_to_cardinal_wnw():
    """Test conversion for WNW (West-Northwest)"""
    result = deg_to_cardinal(292.5)
    assert result == "WNW"

def test_deg_to_cardinal_nw():
    """Test conversion for NW (Northwest)"""
    result = deg_to_cardinal(315.0)
    assert result == "NW"

def test_deg_to_cardinal_nnw():
    """Test conversion for NNW (North-Northwest)"""
    result = deg_to_cardinal(337.5)
    assert result == "NNW"

def test_deg_to_cardinal_nnw_boundary_high():
    """Test conversion for NNW boundary at high end"""
    result = deg_to_cardinal(348.75)
    assert result == "NNW"

def test_deg_to_cardinal_boundary_exact_values():
    """Test exact boundary values"""
    # Test exact boundary transitions
    assert deg_to_cardinal(11.25) == "N"
    assert deg_to_cardinal(33.75) == "NNE"
    assert deg_to_cardinal(56.25) == "NE"
    assert deg_to_cardinal(78.75) == "ENE"
    assert deg_to_cardinal(101.25) == "E"
    assert deg_to_cardinal(123.75) == "ESE"
    assert deg_to_cardinal(146.25) == "SE"
    assert deg_to_cardinal(168.75) == "SSE"
    assert deg_to_cardinal(191.25) == "S"
    assert deg_to_cardinal(213.75) == "SSW"
    assert deg_to_cardinal(236.25) == "SW"
    assert deg_to_cardinal(258.75) == "WSW"
    assert deg_to_cardinal(281.25) == "W"
    assert deg_to_cardinal(303.75) == "WNW"
    assert deg_to_cardinal(326.25) == "NW"
    assert deg_to_cardinal(348.75) == "NNW"

def test_deg_to_cardinal_invalid_high():
    """Test conversion for values above 360 degrees"""
    # The function doesn't handle values > 360, so they fall through to "UNK"
    result = deg_to_cardinal(400.0)
    assert result == "UNK"

def test_deg_to_cardinal_invalid_negative():
    """Test conversion for negative degrees"""
    result = deg_to_cardinal(-45.0)
    assert result == "UNK"

def test_deg_to_cardinal_decimal_precision():
    """Test conversion with high decimal precision"""
    result = deg_to_cardinal(45.123456)
    assert result == "NE"

def test_deg_to_cardinal_zero_integer():
    """Test conversion for integer zero"""
    result = deg_to_cardinal(0)
    assert result == "N"

def test_deg_to_cardinal_float_boundaries():
    """Test float boundary conditions"""
    # Just inside NNE range
    assert deg_to_cardinal(11.26) == "NNE"
    assert deg_to_cardinal(33.74) == "NNE"

    # Just outside NNE range
    assert deg_to_cardinal(33.76) == "NE"

    # Test various boundary transitions
    assert deg_to_cardinal(78.76) == "E"
    assert deg_to_cardinal(101.26) == "ESE"
    assert deg_to_cardinal(348.76) == "N"

@pytest.mark.parametrize("degrees,expected", [
    (5.0, "N"),
    (22.5, "NNE"),
    (45.0, "NE"),
    (67.5, "ENE"),
    (90.0, "E"),
    (112.5, "ESE"),
    (135.0, "SE"),
    (157.5, "SSE"),
    (180.0, "S"),
    (202.5, "SSW"),
    (225.0, "SW"),
    (247.5, "WSW"),
    (270.0, "W"),
    (292.5, "WNW"),
    (315.0, "NW"),
    (337.5, "NNW")
])
def test_deg_to_cardinal_middle_values(degrees, expected):
    """Test middle values of each range for consistency"""
    result = deg_to_cardinal(degrees)
    assert result == expected

def test_deg_to_cardinal_unknown_gap_check():
    """Test that there are no gaps that return 'UNK' within valid range"""
    # Test a comprehensive range to ensure no gaps
    for i in range(3600):  # Test every 0.1 degree
        degrees = i / 10.0
        if degrees <= 360.0:
            result = deg_to_cardinal(degrees)
            assert result != "UNK", f"Unexpected UNK for {degrees} degrees"