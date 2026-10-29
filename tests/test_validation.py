# SPDX-License-Identifier: LicenseRef-Leo-Y-Zhang-Proprietary
"""Landmark and area verifiers must fail closed on corrupted geometry."""
import math

import pytest

import cyprus
import validate_wall


def ll(x, y):
    return math.degrees(y / 6371008.8), math.degrees(x / 6371008.8)


@pytest.fixture
def wall_check(monkeypatch):
    monkeypatch.setattr(validate_wall, "LAT0", 0.0)
    monkeypatch.setattr(validate_wall, "LON0", 0.0)
    monkeypatch.setattr(validate_wall, "WEST", {"inside": ll(1000, 1000)})
    monkeypatch.setattr(validate_wall, "EAST", {"outside": ll(30000, 1000)})

    def check(area=480, corrupt=None):
        height = area * 1e6 / 20000
        ring = [ll(0, 0), ll(20000, 0), ll(20000, height), ll(0, height), ll(0, 0)]
        if corrupt:
            ring = corrupt(ring)
        monkeypatch.setattr(validate_wall, "build_ring", lambda: ring)
        with pytest.raises(SystemExit) as exc:
            validate_wall.main()
        return exc.value.code

    return check


@pytest.mark.parametrize("area", [400, 480, 560])
def test_wall_accepts_valid_ring_and_inclusive_area_limits(wall_check, area):
    assert wall_check(area) == 0


@pytest.mark.parametrize("area", [400, 560])
def test_wall_accepts_exact_area_limits(wall_check, monkeypatch, area):
    # Exercise exact decision endpoints independently of projection rounding.
    monkeypatch.setattr(validate_wall, "ring_area_km2", lambda ring: area)
    assert wall_check() == 0


@pytest.mark.parametrize("area", [399.99, 560.01])
def test_wall_rejects_wrong_area(wall_check, area):
    assert wall_check(area) == 1


@pytest.mark.parametrize("group", ["WEST", "EAST"])
def test_wall_rejects_one_landmark_on_wrong_side(wall_check, monkeypatch, group):
    point = ll(30000, 1000) if group == "WEST" else ll(1000, 1000)
    monkeypatch.setattr(validate_wall, group, {"changed": point})
    assert wall_check() == 1


@pytest.mark.parametrize("corrupt", [
    lambda ring: [ll(5000, 0), *ring[1:-1], ll(5000, 0)],
    lambda ring: ring[:3],
    lambda ring: [],
])
def test_wall_rejects_changed_vertex_removed_corner_and_truncation(wall_check, corrupt):
    assert wall_check(corrupt=corrupt) == 1


@pytest.fixture
def divide_check(monkeypatch):
    # Two landmarks per side: checking only the first must not suffice.
    monkeypatch.setattr(cyprus, "LANDMARKS_NORTH", {"n1": (1, 0.5), "n2": (1, 1.5)})
    monkeypatch.setattr(cyprus, "LANDMARKS_SOUTH", {"s1": (-1, 0.5), "s2": (-1, 1.5)})
    return cyprus.close_ring([(0, 0), (0, 2)], north_lat=2, pad_lon=0.5)


def test_divide_accepts_valid_ring(divide_check):
    assert cyprus.validate(divide_check, 0, 0) is True


@pytest.mark.parametrize("group,key,point", [
    ("LANDMARKS_NORTH", "n1", (-1, 0.5)),
    ("LANDMARKS_NORTH", "n2", (-1, 1.5)),
    ("LANDMARKS_SOUTH", "s1", (1, 0.5)),
    ("LANDMARKS_SOUTH", "s2", (1, 1.5)),
])
def test_divide_rejects_each_changed_landmark(divide_check, monkeypatch, group, key, point):
    changed = dict(getattr(cyprus, group))
    changed[key] = point
    monkeypatch.setattr(cyprus, group, changed)
    assert cyprus.validate(divide_check, 0, 0) is False


@pytest.mark.parametrize("corrupt", [lambda r: r[:3], lambda r: [],
                                          lambda r: [(la - 2, lo) for la, lo in r]])
def test_divide_rejects_truncated_or_displaced_ring(divide_check, corrupt):
    assert cyprus.validate(corrupt(divide_check), 0, 0) is False
