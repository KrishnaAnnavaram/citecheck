"""Confidence intervals and paired tests. No test against a fixed value of 1.0."""
from __future__ import annotations

import math

import numpy as np
from scipy.stats import binomtest


def bootstrap_ci(values, n_boot: int = 2000, level: float = 0.95, seed: int = 0) -> dict[str, float]:
    v = np.asarray(values, dtype=float)
    if v.size == 0:
        return {"mean": math.nan, "ci_low": math.nan, "ci_high": math.nan, "n": 0}
    rng = np.random.default_rng(seed)
    boots = v[rng.integers(0, v.size, size=(n_boot, v.size))].mean(axis=1)
    lo, hi = np.quantile(boots, [(1 - level) / 2, 1 - (1 - level) / 2])
    return {"mean": float(v.mean()), "ci_low": float(lo), "ci_high": float(hi), "n": int(v.size)}


def paired_bootstrap(a, b, n_boot: int = 2000, level: float = 0.95, seed: int = 0) -> dict[str, float]:
    """Mean of (a - b) over paired works, with a percentile interval."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.shape != b.shape:
        raise ValueError("paired samples must have the same length")
    return bootstrap_ci(a - b, n_boot, level, seed)


def mcnemar(a, b) -> dict[str, float]:
    """Exact McNemar test for two paired binary outcomes (for example 'year correct' under two prompts)."""
    a, b = np.asarray(a, dtype=bool), np.asarray(b, dtype=bool)
    if a.shape != b.shape:
        raise ValueError("paired samples must have the same length")
    only_a = int((a & ~b).sum())
    only_b = int((~a & b).sum())
    n = only_a + only_b
    p = 1.0 if n == 0 else float(binomtest(only_a, n, 0.5).pvalue)
    return {"only_a": only_a, "only_b": only_b, "p_value": p}
