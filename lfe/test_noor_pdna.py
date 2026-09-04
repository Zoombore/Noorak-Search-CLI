#!/usr/bin/env python3
"""
Noorak Search CLI — PDNA Test Suite

Run with: python3 test_noor_pdna.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import noor_pdna as N

def test_pdna_base():
    assert N.pdna_base(0.5, 0.5, 0.5) == 0.125
    assert N.pdna_base(1.0, 1.0, 1.0) == 1.0
    assert N.pdna_base(-1.0, -1.0, -1.0) == -1.0
    assert N.pdna_base(0.0, 0.0, 0.0) == 0.0
    assert N.pdna_base(2.0, -3.0, 1.5) == -1.0  # clamped
    assert N.pdna_base(0.7, -0.3, 0.9) == -0.189
    print("  ✅ test_pdna_base")

def test_pdna_changer():
    results = N.pdna_changer(0.5, 0.5, 0.5)
    assert len(results) == 8
    assert all("label" in r for r in results)
    assert all("pdna" in r for r in results)
    assert all(abs(abs(r["pdna"]) - 0.125) < 0.0001 for r in results)
    print("  ✅ test_pdna_changer")

def test_pdna_to_integer():
    # m=1,n=5: 0.5^1 * 0.5^1 * 0.5^1 * 10^4 = 0.125 * 10000 = 1250
    assert N.pdna_to_integer(0.5, 0.5, 0.5, 1, 5) == 1250
    # m=1,n=5 with max values: 1^1 * 1^1 * 1^1 * 10^4 = 10000
    assert N.pdna_to_integer(1.0, 1.0, 1.0, 1, 5) == 10000
    assert N.pdna_to_integer(-1.0, -1.0, -1.0, 1, 5) == -10000
    assert N.pdna_to_integer(0.0, 0.0, 0.0, 5, 5) == 0
    # Sign preservation
    assert N.pdna_to_integer(0.7, -0.3, 0.9, 3, 3) == -1
    # Higher m = much larger numbers (sphere collapse effect)
    r = N.pdna_to_integer(0.8, 0.8, 0.8, 5, 5)
    assert r > 100 and r < 100000
    print("  ✅ test_pdna_to_integer")

def test_pdna_iterate():
    results = N.pdna_iterate(0.8, 0.8, 0.8, 5)
    assert len(results) == 5
    assert all("m" in r and "ir" in r for r in results)
    assert results[0]["m"] == 5
    assert results[-1]["m"] == 1
    print("  ✅ test_pdna_iterate")

def test_pdna_sphere():
    sphere = N.pdna_sphere_sample(3)
    assert len(sphere) > 0
    assert all("y" in s and "z" in s and "x" in s for s in sphere)
    summary = N.pdna_summary(sphere)
    assert summary["count"] > 0
    print("  ✅ test_pdna_sphere")

def test_pdna_table():
    table = N.pdna_table(N.pdna_changer(0.5, 0.5, 0.5))
    assert "State" in table
    assert "PDNA" in table
    print("  ✅ test_pdna_table")

if __name__ == "__main__":
    print("=" * 60)
    print("  Noorak Search CLI — PDNA Test Suite")
    print("=" * 60)
    print()
    print("PDNA Unit Tests:")
    test_pdna_base()
    test_pdna_changer()
    test_pdna_to_integer()
    test_pdna_iterate()
    test_pdna_sphere()
    test_pdna_table()
    print()
    print("=" * 60)
    print("  ✅ All tests passed!")
    print("=" * 60)
