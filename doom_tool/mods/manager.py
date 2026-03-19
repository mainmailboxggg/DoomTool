from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from doom_tool.core.config import AppConfig
from doom_tool.core.downloader import _sha256_file


@dataclass(frozen=True)
class ModCandidate:
    id: str
    url: str
    filename: str | None
    sha256: str | None
    size_bytes: int | None
    priority: int
    archive: str | None


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


class ModsManager:
    def __init__(self, cfg: AppConfig, verbose: bool = False):
        self.cfg = cfg
        self.verbose = verbose

    def _fetch_json(self, url: str) -> Any:
        headers = {"User-Agent": "doom-tool/0.1"}
        req = Request(url, headers=headers, method="GET")
        with urlopen(req, timeout=30) as resp:
            data = resp.read().decode("utf-8")
        return json.loads(data)

    def _load_manifest(self) -> dict[str, Any]:
        src = self.cfg.mods_manifest
        if src.startswith("http://") or src.startswith("https://"):
            if self.verbose:
                print(f"[mods] Fetching mods manifest from {src}")
            return self._fetch_json(src)
        p = Path(src)
        if not p.exists():
            raise FileNotFoundError(f"Mods manifest not found: {p}")
        return json.loads(p.read_text(encoding="utf-8"))

    def _probe_url(self, url: str, timeout_s: float = 15.0) -> tuple[bool, int | None]:
        headers = {"User-Agent": "doom-tool/0.1"}
        req = Request(url, headers=headers, method="HEAD")
        try:
            with urlopen(req, timeout=timeout_s) as resp:
                length = resp.headers.get("Content-Length")
                return True, _safe_int(length)
        except Exception:
            pass

        # Range probe fallback
        req = Request(url, headers={**headers, "Range": "bytes=0-0"}, method="GET")
        try:
            with urlopen(req, timeout=timeout_s) as resp:
                length = resp.headers.get("Content-Length")
                return 200 <= resp.status < 400, _safe_int(length)
        except HTTPError as e:
            if 200 <= e.code < 400:
                return True, None
            return False, None
        except URLError:
            return False, None

    def _download_file(self, url: str, out_path: Path, verbose: bool) -> int | None:
        # Keep downloader in core; this is a simplified variant for mods.
        headers = {"User-Agent": "doom-tool/0.1"}
        req = Request(url, headers=headers, method="GET")
        with urlopen(req, timeout=60) as resp:
            content_length = resp.headers.get("Content-Length")
            total = int(content_length) if content_length and content_length.isdigit() else None

            out_path.parent.mkdir(parents=True, exist_ok=True)
            start = time.time()
            downloaded = 0
            chunk_size = 1024 * 1024
            with out_path.open("wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if verbose and total:
                        pct = (downloaded / total) * 100
                        elapsed = max(time.time() - start, 0.001)
                        rate_mbps = (downloaded / (1024 * 1024)) / elapsed
                        print(f"[mods:download] {out_path.name}: {pct:6.2f}% ~{rate_mbps:.2f} MiB/s")
            return total

    def _select_best_candidate(self, candidates: list[ModCandidate]) -> tuple[ModCandidate, str]:
        valid: list[tuple[ModCandidate, int | None]] = []
        for cand in candidates:
            ok, content_length = self._probe_url(cand.url)
            if ok:
                valid.append((cand, content_length))
        if not valid:
            raise RuntimeError("No reachable mod sources found")

        def score(item: tuple[ModCandidate, int | None]) -> tuple[int, int]:
            cand, prob_size = item
            size = cand.size_bytes if cand.size_bytes is not None else prob_size
            effective = size if size is not None else 10**30
            return (effective, cand.priority)

        chosen_cand, chosen_size = sorted(valid, key=score)[0]
        resolved_filename = _resolve_filename(chosen_cand.url, chosen_cand.filename, fallback=f"{chosen_cand.id}.bin")
        return chosen_cand, resolved_filename

    def install_all(self, dry_run: bool) -> None:
        manifest = self._load_manifest()
        mods_raw = manifest.get("mods") or []
        if not mods_raw:
            if self.verbose:
                print("[mods] No mods configured in manifest.")
            return

        local_mods_dir = self.cfg.root_dir / "user_mods"
        if self.verbose and local_mods_dir.exists():
            print(f"[mods] Found local mods folder: {local_mods_dir}")

        # Remote/discovered mods from manifest
        for m in mods_raw:
            game_id = str(m.get("game_id") or "")
            if not game_id or game_id not in self.cfg.games:
                continue

            mod_id = str(m.get("id") or m.get("name") or "mod")
            archive = m.get("archive")
            install_subdir = str(m.get("install_subdir") or "mods")

            dest_dir = self.cfg.install_dir / game_id / install_subdir
            dest_dir.mkdir(parents=True, exist_ok=True)

            # Candidate selection:
            if m.get("candidates"):
                candidates: list[ModCandidate] = []
                for i, c in enumerate(m["candidates"]):
                    candidates.append(
                        ModCandidate(
                            id=str(c.get("id") or f"{mod_id}_cand_{i+1}"),
                            url=str(c["url"]),
                            filename=c.get("filename"),
                            sha256=c.get("sha256"),
                            size_bytes=_safe_int(c.get("size_bytes")),
                            priority=_safe_int(c.get("priority")) or 0,
                            archive=c.get("archive") or archive,
                        )
                    )
                chosen, resolved_filename = self._select_best_candidate(candidates)
            else:
                chosen = ModCandidate(
                    id=mod_id,
                    url=str(m["url"]),
                    filename=m.get("filename"),
                    sha256=m.get("sha256"),
                    size_bytes=_safe_int(m.get("size_bytes")),
                    priority=_safe_int(m.get("priority")) or 0,
                    archive=m.get("archive") or archive,
                )
                resolved_filename = _resolve_filename(chosen.url, chosen.filename, fallback=f"{mod_id}.bin")

            dl_dir = self.cfg.download_dir / "mods"
            dl_path = dl_dir / resolved_filename

            if self.verbose:
                print(f"[mods] {game_id}:{mod_id} -> {chosen.url}")

            if dry_run:
                print(f"[mods] DRY RUN: would install '{mod_id}' into {dest_dir}")
                continue

            # Download if needed
            if dl_path.exists() and chosen.sha256:
                if _sha256_file(dl_path).lower() == chosen.sha256.lower():
                    if self.verbose:
                        print(f"[mods:download] Cached sha256 ok: {dl_path.name}")
                else:
                    dl_path.unlink(missing_ok=True)

            if not dl_path.exists():
                if self.verbose:
                    print(f"[mods:download] Fetching: {dl_path.name}")
                self._download_file(chosen.url, dl_path, verbose=self.verbose)

            if chosen.sha256:
                current = _sha256_file(dl_path)
                if current.lower() != chosen.sha256.lower():
                    raise RuntimeError(f"sha256 mismatch for mod '{mod_id}'")

            # Install
            if chosen.archive == "zip":
                if self.verbose:
                    print(f"[mods:install] Extracting '{mod_id}' into {dest_dir}")
                import zipfile

                with zipfile.ZipFile(dl_path) as zf:
                    zf.extractall(dest_dir)
            else:
                # Generic install: copy raw file into the dest folder.
                dst = dest_dir / resolved_filename
                if self.verbose:
                    print(f"[mods:install] Copying '{mod_id}' -> {dst}")
                shutil.copy2(dl_path, dst)

        # Local mods folder discovery (optional)
        if local_mods_dir.exists():
            for p in local_mods_dir.iterdir():
                if p.is_dir():
                    continue
                # Heuristic: install file into all configured games' mods folder.
                for game_id in self.cfg.games:
                    dest_dir = self.cfg.install_dir / game_id / "mods"
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    if dry_run:
                        print(f"[mods] DRY RUN: would copy local mod {p.name} to {dest_dir}")
                        continue
                    shutil.copy2(p, dest_dir / p.name)

