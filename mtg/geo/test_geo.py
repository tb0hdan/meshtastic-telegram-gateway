# -*- coding: utf-8 -*-
# pylint: skip-file
import pytest
from unittest.mock import patch
from mtg.geo.geo import get_lat_lon_distance
def test_get_lat_lon_distance_valid_input():
    """Test distance calculation with valid coordinates"""
    # Test distance between two known points
    # Kyiv and Lviv coordinates (approximate)
    kyiv = (50.4501, 30.5234)
    lviv = (49.8397, 24.0297)

    distance = get_lat_lon_distance(kyiv, lviv)

    # Distance should be approximately 469 km (469000 meters)
    assert isinstance(distance, float)
    assert distance > 400000
    assert distance < 500000

def test_get_lat_lon_distance_same_point():
    """Test distance calculation for the same point"""
    point = (50.4501, 30.5234)
    distance = get_lat_lon_distance(point, point)
    assert distance == 0.0

def test_get_lat_lon_distance_invalid_latlon1():
    """Test error handling for invalid latlon1 parameter"""
    with pytest.raises(RuntimeError, match='Tuple expected for latlon1'):
        get_lat_lon_distance("not_a_tuple", (50.0, 30.0))

def test_get_lat_lon_distance_invalid_latlon2():
    """Test error handling for invalid latlon2 parameter"""
    with pytest.raises(RuntimeError, match='Tuple expected for latlon2'):
        get_lat_lon_distance((50.0, 30.0), "not_a_tuple")

def test_get_lat_lon_distance_list_input():
    """Test error handling for list input instead of tuple"""
    with pytest.raises(RuntimeError):
        get_lat_lon_distance([50.0, 30.0], (50.0, 30.0))

def test_get_lat_lon_distance_none_input():
    """Test error handling for None input"""
    with pytest.raises(RuntimeError):
        get_lat_lon_distance(None, (50.0, 30.0))

@patch('haversine.haversine')
def test_get_lat_lon_distance_haversine_called(mock_haversine):
    """Test that haversine function is called with correct parameters"""
    mock_haversine.return_value = 1000.0

    point1 = (50.0, 30.0)
    point2 = (51.0, 31.0)

    result = get_lat_lon_distance(point1, point2)

    mock_haversine.assert_called_once()
    assert result == 1000.0