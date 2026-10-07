"""Synthetic work records for the offline demo and the tests.

The records are invented. The DOIs use the prefix ``10.5555``, which is a
test prefix, so they never point to a real work.
"""
from __future__ import annotations

import numpy as np

from .records import Author, WorkRecord

FAMILIES = ["Okafor", "Lindqvist", "Tanaka", "Moreau", "Haddad", "Novak", "Ibrahim", "Kowalski", "Reyes", "Chen",
            "Fischer", "Patel", "Andersen", "Silva", "Kim", "Rossi", "Nguyen", "Schmidt", "Mensah", "Varga"]
GIVENS = ["Amara", "Erik", "Yuki", "Claire", "Omar", "Petra", "Fatima", "Jan", "Lucia", "Wei", "Jonas", "Priya",
          "Mette", "Rafael", "Min-jun", "Giulia", "Linh", "Anna Maria", "Kwame", "Zsofia"]
TOPICS = ["graph neural networks", "federated learning", "protein structure prediction", "causal inference",
          "time series forecasting", "speech recognition", "reinforcement learning", "anomaly detection",
          "recommender systems", "medical image segmentation", "language model evaluation", "active learning"]
PATTERNS = ["A survey of {t}", "Robust {t} under distribution shift", "Scalable {t} with sparse attention",
            "On the limits of {t}", "Benchmarking {t}: lessons from ten datasets", "Efficient {t} for edge devices"]
SETTINGS = ["", " in clinical data", " for climate records", " on small datasets", " in low-resource languages",
            " for industrial sensors", " with noisy labels", " at web scale"]
VENUES = ["Journal of Applied Learning Systems", "Transactions on Data Methods", "Computational Science Letters",
          "Annals of Statistical Computing", "Proceedings of the Workshop on Learning Methods"]
PUBLISHERS = ["Northfield Academic Press", "Harbour Science Books", "Meridian Scholarly Press"]


def make_records(n: int, seed: int = 0) -> list[WorkRecord]:
    rng = np.random.default_rng(seed)
    out = []
    used: set[str] = set()
    for i in range(n):
        kind = rng.choice(["article-journal", "article-journal", "article-journal", "paper-conference", "book"])
        k = int(rng.integers(1, 6))
        authors = tuple(Author(family=str(rng.choice(FAMILIES)), given=str(rng.choice(GIVENS))) for _ in range(k))
        for _ in range(50):  # titles are unique, so a title identifies one record
            title = str(rng.choice(PATTERNS)).format(t=str(rng.choice(TOPICS))) + str(rng.choice(SETTINGS))
            if title.lower() not in used:
                break
        else:
            title = f"{title} (report {i})"
        title = title[0].upper() + title[1:]
        used.add(title.lower())
        start = int(rng.integers(1, 900))
        rec = dict(
            id=f"syn{i:04d}", type=str(kind), title=title, authors=authors, year=int(rng.integers(1995, 2025)),
            doi=f"10.5555/syn.{seed}.{i:04d}",
        )
        if kind == "book":
            rec.update(publisher=str(rng.choice(PUBLISHERS)))
        else:
            rec.update(container_title=str(rng.choice(VENUES)), volume=str(int(rng.integers(1, 60))),
                       issue=str(int(rng.integers(1, 12))) if kind == "article-journal" else "",
                       pages=f"{start}-{start + int(rng.integers(5, 30))}")
        out.append(WorkRecord(**rec))
    return out
