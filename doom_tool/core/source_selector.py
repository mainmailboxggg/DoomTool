from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlparse

from doom_tool.core.config import AppConfig


@dataclass(frozen=True)
class DownloadCandidate:
    id: str
    url: str
    filename: str | None
    sha256: str | None
    size_bytes: int | None
    priority: int
    archive: str | None
    install_subdir: str | None


@dataclass(frozen=True)
class SelectedSource:
    candidate: DownloadCandidate
    resolved_filename: str
    expected_size_bytes: int | None


def _safe_int(v: Any) -> int | None:
    try:
        if v is None:
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


def _resolve_filename(url: str, filename: str | None, fallback: str) -> str:
    if filename:
        return filename
    parsed = urlparse(url)
    name = Path(parsed.path).name
    return name if name else fallback


class SourceSelector:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg

    def _probe_url(self, url: str, timeout_s: float = 15.0) -> tuple[bool, int | None]:
        """
        Returns (ok, content_length_bytes_if_known).
        Uses HEAD when possible; falls back to a ranged GET probe.
        """
        headers = {"User-Agent": "doom-tool/0.1"}

        req = Request(url, headers=headers, method="HEAD")
        try:
            with urlopen(req, timeout=timeout_s) as resp:
                length = resp.headers.get("Content-Length")
                return True, _safe_int(length)
        except Exception:
            pass

        # Fallback: request a single byte via Range to validate reachability.
        req = Request(url, headers={**headers, "Range": "bytes=0-0"}, method="GET")
        try:
            with urlopen(req, timeout=timeout_s) as resp:
                length = resp.headers.get("Content-Length")
                return 200 <= resp.status < 400, _safe_int(length)
        except HTTPError as e:
            # Some servers reject Range; treat any 2xx/3xx as OK.
            if 200 <= e.code < 400:
                return True, None
            return False, None
        except URLError:
            return False, None

    def select_from_manifest(self, game_id: str, manifest_path: Path) -> SelectedSource:
        if not manifest_path.exists():
            raise FileNotFoundError(f"Sources manifest not found for '{game_id}': {manifest_path}")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        candidates_raw = manifest.get("candidates") or []
        if not candidates_raw:
            raise ValueError(f"Sources manifest for '{game_id}' has no candidates")

        candidates: list[DownloadCandidate] = []
        for i, c in enumerate(candidates_raw):
            cid = str(c.get("id") or f"candidate_{i+1}")
            candidates.append(
                DownloadCandidate(
                    id=cid,
                    url=str(c["url"]),
                    filename=c.get("filename"),
                    sha256=c.get("sha256"),
                    size_bytes=_safe_int(c.get("size_bytes")),
                    priority=_safe_int(c.get("priority")) or 0,
                    archive=c.get("archive"),
                    install_subdir=c.get("install_subdir"),
                )
            )

        # Probe candidates online.
        valid: list[tuple[DownloadCandidate, int | None]] = []
        for cand in candidates:
            ok, content_length = self._probe_url(cand.url)
            if ok:
                valid.append((cand, content_length))

        if not valid:
            raise RuntimeError(f"No reachable sources found for '{game_id}'")

        # "Speed" heuristic:
        # Prefer smaller expected download size; break ties by priority (lower is better).
        def score(item: tuple[DownloadCandidate, int | None]) -> tuple[int, int]:
            cand, prob_size = item
            size = cand.size_bytes if cand.size_bytes is not None else prob_size
            effective = size if size is not None else 10**30
            return (effective, cand.priority)

        chosen_cand, chosen_size = sorted(valid, key=score)[0]
        resolved_filename = _resolve_filename(chosen_cand.url, chosen_cand.filename, fallback=f"{game_id}.bin")

        return SelectedSource(
            candidate=chosen_cand,
            resolved_filename=resolved_filename,
            expected_size_bytes=chosen_size if chosen_size is not None else chosen_cand.size_bytes,
        )

