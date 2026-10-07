"""Models under test, behind one interface: ``complete(messages) -> str``.

* ``OpenAICompatibleLLM``: any ``/chat/completions`` server (OpenAI, Gemini's
  OpenAI-compatible endpoint, Ollama, vLLM). Temperature 0, JSON mode. The key
  comes from the environment only.
* ``SimulatedLLM``: a seeded error model for the offline demo and the tests.
  Its output is marked ``simulated`` everywhere. It is not a measurement of
  any real model, and the report never mixes it with real results.
* ``ScriptedLLM``: fixed answers for tests.
"""
from __future__ import annotations

import json
import re
import urllib.request
import zlib
from typing import Protocol

import numpy as np

from .normalize import normalize_title
from .records import Author, WorkRecord
from .render import render_all


class LLM(Protocol):
    name: str
    simulated: bool

    def complete(self, messages: list[dict[str, str]]) -> str:  # pragma: no cover - protocol
        ...


class OpenAICompatibleLLM:
    simulated = False

    def __init__(self, base_url: str, model: str, api_key: str | None, timeout_s: float = 60.0,
                 json_mode: bool = True) -> None:
        if not base_url.startswith(("https://", "http://localhost", "http://127.0.0.1")):
            raise ValueError("the base URL must use https (plain http only for localhost)")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.json_mode = json_mode
        self.name = model

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload: dict = {"model": self.model, "messages": messages, "temperature": 0}
        if self.json_mode:
            payload["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(f"{self.base_url}/chat/completions", data=json.dumps(payload).encode(),
                                     method="POST", headers={"Content-Type": "application/json"})
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310 - URL checked above
            return json.loads(resp.read().decode())["choices"][0]["message"]["content"]


# error probabilities of the simulated model, by the information in the prompt
ERROR_RATES = {
    "title_only": {"authors": 0.45, "year": 0.55, "container_title": 0.65, "volume": 0.75, "issue": 0.75,
                   "pages": 0.85, "doi": 0.80},
    "title_doi": {"authors": 0.40, "year": 0.45, "container_title": 0.55, "volume": 0.70, "issue": 0.70,
                  "pages": 0.80, "doi": 0.05},
    "full_metadata": {"authors": 0.03, "year": 0.02, "container_title": 0.03, "volume": 0.02, "issue": 0.02,
                      "pages": 0.05, "doi": 0.02},
}
OMIT_SHARE = 0.4  # share of the errors that are omissions instead of wrong values
STYLE_SLIP = 0.25  # chance of one formatting slip per reference string


class SimulatedLLM:
    simulated = True

    def __init__(self, catalogue: list[WorkRecord], seed: int = 0) -> None:
        self.by_title = {normalize_title(r.title): r for r in catalogue}
        self.catalogue = catalogue
        self.seed = seed
        self.name = f"simulated-seed{seed}"

    def _variant(self, prompt: str) -> str:
        if "\nAuthors:" in prompt:
            return "full_metadata"
        return "title_doi" if "\nDOI:" in prompt else "title_only"

    def complete(self, messages: list[dict[str, str]]) -> str:
        prompt = messages[-1]["content"]
        m = re.search(r"^Title: (.*)$", prompt, flags=re.M)
        truth = self.by_title.get(normalize_title(m.group(1))) if m else None
        if truth is None:
            return json.dumps({"title": m.group(1) if m else "", "citations": {}})
        variant = self._variant(prompt)
        rng = np.random.default_rng([self.seed, zlib.crc32(truth.id.encode()), zlib.crc32(variant.encode())])
        rates = ERROR_RATES[variant]
        rec = truth.model_dump()

        def bad(field: str) -> str | None:
            if rng.random() >= rates[field]:
                return None
            return "omit" if rng.random() < OMIT_SHARE else "wrong"

        if (e := bad("authors")):
            authors = list(truth.authors)
            if e == "omit" or not authors:
                rec["authors"] = ()
            elif len(authors) > 1 and rng.random() < 0.5:
                rec["authors"] = tuple(authors[:-1])  # drops the last author
            else:
                a = authors[0]
                rec["authors"] = (Author(family=a.family[:-1] + "e", given=a.given), *authors[1:])
        if (e := bad("year")):
            rec["year"] = None if e == "omit" else (truth.year or 2000) + int(rng.choice([-3, -2, -1, 1, 2]))
        if (e := bad("container_title")):
            other = [r.container_title for r in self.catalogue if r.container_title and r.container_title != truth.container_title]
            rec["container_title"] = "" if e == "omit" or not other else str(rng.choice(other))
        for field in ("volume", "issue"):
            if (e := bad(field)) and truth.model_dump()[field]:
                rec[field] = "" if e == "omit" else str(int(rng.integers(1, 80)))
        if (e := bad("pages")) and truth.pages:
            start = int(rng.integers(1, 900))
            rec["pages"] = "" if e == "omit" else f"{start}-{start + int(rng.integers(5, 25))}"
        if (e := bad("doi")):
            if e == "omit":
                rec["doi"] = ""
            elif rng.random() < 0.3:
                rec["doi"] = str(rng.choice([r.doi for r in self.catalogue if r.doi and r.doi != truth.doi]))
            else:
                rec["doi"] = f"10.{int(rng.integers(1000, 9999))}/{int(rng.integers(10**5, 10**6))}"
        pred = WorkRecord(**rec)
        cites = render_all(pred)
        for style in cites:
            if rng.random() < STYLE_SLIP:
                cites[style] = slip(style, cites[style])
        out = {k: v for k, v in pred.model_dump().items() if k not in ("id", "url")}
        out["authors"] = [a.model_dump() for a in pred.authors]
        out["citations"] = cites
        return json.dumps(out)


def slip(style: str, text: str) -> str:
    """One typical formatting mistake per style."""
    if style == "apa":
        return text.replace(", & ", ", and ", 1) if ", & " in text else text.replace(")", "),", 1)
    if style == "mla":
        return text.replace("“", "").replace("”", "")
    if style == "chicago":
        return re.sub(r"\. (\d{4}|n\.d\.)\. ", ". ", text, count=1)
    if style == "harvard":
        return re.sub(r"\((\d{4})\)", r"\1", text, count=1)
    return re.sub(r"\b([A-Z])([A-Z])\b", r"\1. \2.", text, count=1)


class ScriptedLLM:
    simulated = False

    def __init__(self, answers: list[str], name: str = "scripted") -> None:
        self.answers = list(answers)
        self.calls: list[list[dict[str, str]]] = []
        self.name = name

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        return self.answers.pop(0) if self.answers else ""
