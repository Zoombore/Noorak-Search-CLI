"""
NoorPDNA — Noor (نور) × PDNA
Three-Dimensional Identity Manifold Engine

A Python implementation of the PDNA mathematical framework:
  - Y-Axis: Identity & Expression (-1 Suppressed → +1 Fully Expressive)
  - Z-Axis: Sensory Processing    (-1 Muted    → +1 Hyperaware)
  - X-Axis: Executive Control     (-1 Chaotic  → +1 Fully Controlled)

Core formula:
  PDNA_Base(Y, Z, X) = Y * Z * X                    → continuous [-1, +1]
  PDNA_Changer = {(-Y,+Y)} × {(-Z,+Z)} × {(-X,+X)}  → 8 sign combinations
  PDNA_IR(m, n) = (Y^m * Z^m * X^m) * 10^(n-1)     → integer domain

The engine iterates over all 8 psychological states on the 3D sphere,
computes the PDNA value for each, and maps results to integer domain.

Author: Noorak Search CLI ecosystem
License: MIT
"""

import math
from itertools import product
from typing import Tuple, List, Dict

# ── Constants ────────────────────────────────────────────
AXIS_NAMES = {
    "Y": "Identity & Expression",
    "Z": "Sensory Processing",
    "X": "Executive Control"
}

SIGN_COMBINATIONS: List[Tuple[int, int, int]] = list(product([-1, 1], repeat=3))


# ── Core formula ──────────────────────────────────────────

def _clamp(v: float) -> float:
    """Clamp value to [-1.0, +1.0] range."""
    return max(-1.0, min(1.0, v))


def pdna_base(y: float, z: float, x: float) -> float:
    """PDNA_Base = Y * Z * X. Continuous range: [-1.0, +1.0]."""
    y, z, x = _clamp(y), _clamp(z), _clamp(x)
    return round(y * z * x, 6)


def pdna_changer(y: float, z: float, x: float) -> List[Dict]:
    """PDNA_changer = {(-Y,+Y)} × {(-Z,+Z)} × {(-X,+X)}. Returns 8 states."""
    results = []
    for sy, sz, sx in SIGN_COMBINATIONS:
        val = pdna_base(sy * y, sz * z, sx * x)
        results.append({
            "y": round(sy * y, 6),
            "z": round(sz * z, 6),
            "x": round(sx * x, 6),
            "pdna": val,
            "label": (f"({'+' if sy > 0 else '-'}{abs(y):.3f}, "
                      f"{'+' if sz > 0 else '-'}{abs(z):.3f}, "
                      f"{'+' if sx > 0 else '-'}{abs(x):.3f})")
        })
    return results


def _sign_pow(base: float, exp: int) -> float:
    """Sign-preserving power: copysign(|base|^exp, base)."""
    if base == 0:
        return 0.0
    return math.copysign(abs(base) ** exp, base)


def pdna_to_integer(y: float, z: float, x: float, m: int, n: int) -> int:
    """
    PDNA_IR(m, n) = (Y^m * Z^m * X^m) * 10^(n-1) → integer domain.
    Uses sign-preserving power for negative bases.
    """
    if m <= 0:
        return 0
    y, z, x = _clamp(y), _clamp(z), _clamp(x)

    ym = _sign_pow(y, m)
    zm = _sign_pow(z, m)
    xm = _sign_pow(x, m)

    result = round(ym * zm * xm * (10 ** (n - 1)))
    return result


def pdna_iterate(y: float, z: float, x: float, n: int) -> List[Dict]:
    """
    Full iteration: m starts at n, decreases by 1 until 1.
    Returns list of {"m": value, "ir": integer} dicts.
    """
    results = []
    for m in range(n, 0, -1):
        ir = pdna_to_integer(y, z, x, m, n)
        results.append({"m": m, "ir": ir, "y": y, "z": z, "x": x})
    return results


# ── Sphere surface sampling ──────────────────────────────

def pdna_sphere_sample(resolution: int = 5) -> List[Dict]:
    """
    Sample points on a 3D sphere representing psychological states.
    Uses spherical coordinates: Y = sin(θ)cos(φ), Z = sin(θ)sin(φ), X = cos(θ).
    """
    results = []
    for i in range(resolution + 1):
        theta = math.pi * i / resolution
        for j in range(resolution * 2):
            phi = 2 * math.pi * j / (resolution * 2)
            y = round(math.sin(theta) * math.cos(phi), 6)
            z = round(math.sin(theta) * math.sin(phi), 6)
            x = round(math.cos(theta), 6)
            results.append({
                "y": y, "z": z, "x": x,
                "pdna": pdna_base(y, z, x),
                "theta": round(theta, 4),
                "phi": round(phi, 4)
            })
    return results


# ── Summary statistics ──────────────────────────────────

def pdna_summary(states: List[Dict]) -> Dict:
    """Compute summary statistics over a set of PDNA states."""
    if not states:
        return {"error": "empty states"}

    pdna_values = [s.get("pdna", 0) for s in states]
    ir_values = [s.get("ir", 0) for s in states]
    mean_pdna = sum(pdna_values) / len(pdna_values)

    return {
        "count": len(states),
        "pdna_mean": round(mean_pdna, 6),
        "pdna_min": round(min(pdna_values), 6),
        "pdna_max": round(max(pdna_values), 6),
        "pdna_std": round(math.sqrt(sum((v - mean_pdna)**2 for v in pdna_values) / len(pdna_values)), 6),
        "ir_sum": sum(ir_values),
        "ir_mean": round(sum(ir_values) / len(ir_values), 4),
        "ir_min": min(ir_values),
        "ir_max": max(ir_values),
    }


# ── Pretty printing ──────────────────────────────────────

def pdna_table(changer_results: List[Dict]) -> str:
    """Format PDNA_changer results as a readable table."""
    header = f"{'State':>32s}  {'Y':>8s}  {'Z':>8s}  {'X':>8s}  {'PDNA':>8s}"
    sep = "─" * 72
    lines = [header, sep]
    for r in changer_results:
        lines.append(f"{r['label']:>32s}  {r['y']:>8.3f}  {r['z']:>8.3f}  "
                     f"{r['x']:>8.3f}  {r['pdna']:>8.4f}")
    return "\n".join(lines)


# ── Standalone demo ──────────────────────────────────────

def run_demo():
    """Run the NoorPDNA engine as a standalone demo."""
    print("=" * 72)
    print("  NoorPDNA — Three-Dimensional Identity Manifold Engine")
    print("  (نورک × PDNA)")
    print("=" * 72)

    y, z, x = 0.5, 0.5, 0.5
    n = 8

    print(f"\nInput state: Y={y}, Z={z}, X={x}")
    print(f"Multiplier: n={n}")

    print(f"\n{'─'*72}")
    print("PDNA_Base:")
    print(f"  PDNA({y}, {z}, {x}) = {pdna_base(y, z, x)}")

    print(f"\n{'─'*72}")
    print("PDNA_changer (all 8 sign combinations):")
    print(pdna_table(pdna_changer(y, z, x)))

    print(f"\n{'─'*72}")
    print("PDNA_IR (integer mapping, m from n to 1):")
    iterations = pdna_iterate(y, z, x, n)
    for it in iterations:
        print(f"  m={it['m']:>2d}  IR={it['ir']:>10d}")

    print(f"\n{'─'*72}")
    print(f"Summary: {pdna_summary(iterations)}")

    sphere = pdna_sphere_sample(5)
    print(f"\n{'─'*72}")
    print(f"Sphere surface sample ({len(sphere)} points):")
    print(f"  {pdna_summary(sphere)}")

    print("\n✅ NoorPDNA demo complete.")


if __name__ == "__main__":
    run_demo()
