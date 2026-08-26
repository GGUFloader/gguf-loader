"""HuggingFace model catalog discovery with search, download, and hash verification.

Ports GPT4All's model acquisition design (download.cpp + modellist.cpp):
- Search HF API for GGUF models
- Download with HTTP Range resume
- SHA256 hash verification
- Streaming progress callbacks

The search endpoint mirrors GPT4All's:
    https://huggingface.co/api/models?filter=gguf&search=<query>&sort=likes
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

HF_API_BASE = "https://huggingface.co/api/models"
HF_RESOLVE_BASE = "https://huggingface.co"
GGUF_EXTENSIONS = {".gguf"}


@dataclass
class HFModel:
    """A GGUF model found on HuggingFace."""

    repo_id: str
    model_name: str
    likes: int = 0
    downloads: int = 0
    last_modified: str = ""
    description: str = ""
    files: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        """Human-friendly name."""
        return self.model_name or self.repo_id.split("/")[-1]

    @property
    def gguf_files(self) -> List[Dict[str, Any]]:
        """GGUF files available for download."""
        return [f for f in self.files if f.get("path", "").endswith(".gguf")]

    def to_dict(self) -> dict:
        return {
            "repo_id": self.repo_id,
            "model_name": self.model_name,
            "likes": self.likes,
            "downloads": self.downloads,
            "description": self.description[:200],
            "gguf_files": self.gguf_files,
        }


@dataclass
class DownloadProgress:
    """Progress update for a file download."""

    bytes_downloaded: int = 0
    total_bytes: int = 0
    speed_bps: float = 0.0
    elapsed_secs: float = 0.0
    status: str = ""  # "downloading", "verifying", "done", "error"

    @property
    def percent(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        return min(100.0, self.bytes_downloaded / self.total_bytes * 100)

    @property
    def speed_mbps(self) -> float:
        return self.speed_bps / (1024 * 1024)


class HFService:
    """HuggingFace model catalog client with download and verification."""

    def __init__(self, models_dir: str | Path) -> None:
        self._models_dir = Path(models_dir)
        self._models_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str = "",
        *,
        sort: str = "likes",
        limit: int = 20,
    ) -> List[HFModel]:
        """Search HuggingFace for GGUF models.

        Args:
            query: Search terms (empty = trending GGUF models)
            sort: Sort order: "likes", "downloads", "lastModified"
            limit: Max results (default 20, max 50)
        """
        limit = min(limit, 50)
        params = {
            "filter": "gguf",
            "sort": sort,
            "direction": "-1",
            "limit": str(limit),
        }
        if query:
            params["search"] = query

        url = f"{HF_API_BASE}?{urllib.parse.urlencode(params)}"
        logger.info("HF search: %s", url)

        try:
            req = urllib.request.Request(url, headers={
                "Accept": "application/json",
                "User-Agent": "ggufloader/2.0",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:  # noqa: BLE001
            logger.warning("HF search failed: %s", e)
            return []

        models: List[HFModel] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            repo_id = item.get("id", "")
            if not repo_id:
                continue

            # Get file list from siblings
            siblings = item.get("siblings") or []
            files = []
            for s in siblings:
                fname = s.get("rfilename", "")
                if fname.endswith(".gguf"):
                    files.append({
                        "path": fname,
                        "size": s.get("size", 0),
                    })

            if not files:
                continue  # skip repos with no GGUF files

            model = HFModel(
                repo_id=repo_id,
                model_name=item.get("modelId") or repo_id.split("/")[-1],
                likes=item.get("likes", 0),
                downloads=item.get("downloads", 0),
                last_modified=item.get("lastModified", ""),
                description=item.get("description", "") or "",
                files=files,
            )
            models.append(model)

        logger.info("HF search: found %d models for '%s'", len(models), query)
        return models

    # ------------------------------------------------------------------
    # File info
    # ------------------------------------------------------------------

    def get_file_info(self, repo_id: str, file_path: str) -> Dict[str, Any]:
        """Get metadata for a specific file (size, ETag/hash)."""
        url = f"{HF_RESOLVE_BASE}/{repo_id}/resolve/main/{file_path}"
        try:
            req = urllib.request.Request(url, method="HEAD", headers={
                "User-Agent": "ggufloader/2.0",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                headers = resp.headers
                size = int(headers.get("Content-Length", 0))
                etag = headers.get("ETag", "").strip('"')
                return {"size": size, "etag": etag, "url": url}
        except Exception as e:  # noqa: BLE001
            logger.warning("HF file info failed for %s/%s: %s", repo_id, file_path, e)
            return {"size": 0, "etag": "", "url": url}

    # ------------------------------------------------------------------
    # Download with resume + SHA256 verification
    # ------------------------------------------------------------------

    def download(
        self,
        repo_id: str,
        file_path: str,
        *,
        expected_hash: Optional[str] = None,
        on_progress: Optional[Callable[[DownloadProgress], None]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> Path:
        """Download a GGUF file with resume and optional SHA256 verification.

        Args:
            repo_id: HuggingFace repo (e.g. "TheBloke/Llama-2-7B-GGUF")
            file_path: File within the repo (e.g. "llama-2-7b.Q4_K_M.gguf")
            expected_hash: Optional SHA256 hex digest to verify against
            on_progress: Callback with DownloadProgress updates
            should_cancel: Return True to abort the download

        Returns:
            Path to the downloaded file

        Raises:
            RuntimeError: On download failure or hash mismatch
        """
        url = f"{HF_RESOLVE_BASE}/{repo_id}/resolve/main/{file_path}"
        dest = self._models_dir / file_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")

        # Get file size for progress
        file_info = self.get_file_info(repo_id, file_path)
        total_size = file_info.get("size", 0)

        # Resume from partial download
        existing_bytes = 0
        if tmp.exists():
            existing_bytes = tmp.stat().st_size
            if existing_bytes >= total_size and total_size > 0:
                # File already complete
                tmp.rename(dest)
                if expected_hash:
                    self._verify_hash(dest, expected_hash, on_progress)
                return dest

        t0 = time.monotonic()
        progress = DownloadProgress(status="downloading")

        try:
            # Build request with Range header for resume
            headers = {"User-Agent": "ggufloader/2.0"}
            if existing_bytes > 0:
                headers["Range"] = f"bytes={existing_bytes}-"
                logger.info("HF download resuming %s from %d bytes", file_path, existing_bytes)

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                # Check if server supports resume
                if resp.status == 206:
                    # Partial content - appending
                    mode = "ab"
                else:
                    # Full restart
                    existing_bytes = 0
                    mode = "wb"
                    tmp.unlink(missing_ok=True)

                if total_size <= 0:
                    total_size = int(resp.headers.get("Content-Length", 0))

                with open(tmp, mode) as f:
                    while True:
                        if should_cancel and should_cancel():
                            raise RuntimeError("Download cancelled")

                        chunk = resp.read(256 * 1024)  # 256KB chunks
                        if not chunk:
                            break

                        f.write(chunk)
                        existing_bytes += len(chunk)

                        # Update progress
                        elapsed = time.monotonic() - t0
                        speed = existing_bytes / max(0.001, elapsed)
                        progress.bytes_downloaded = existing_bytes
                        progress.total_bytes = total_size
                        progress.speed_bps = speed
                        progress.elapsed_secs = elapsed

                        if on_progress:
                            on_progress(progress)

            # Download complete - rename part file
            tmp.rename(dest)
            logger.info("HF download complete: %s (%d bytes)", file_path, existing_bytes)

            # Hash verification
            if expected_hash:
                self._verify_hash(dest, expected_hash, on_progress)

            # Done
            progress.status = "done"
            progress.bytes_downloaded = existing_bytes
            if on_progress:
                on_progress(progress)

            return dest

        except Exception as e:
            progress.status = "error"
            if on_progress:
                on_progress(progress)
            # Clean up partial file on error
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"Download failed: {e}") from e

    def _verify_hash(
        self,
        path: Path,
        expected: str,
        on_progress: Optional[Callable[[DownloadProgress], None]] = None,
    ) -> None:
        """Verify SHA256 hash of a downloaded file."""
        progress = DownloadProgress(status="verifying", total_bytes=path.stat().st_size)
        if on_progress:
            on_progress(progress)

        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                sha256.update(chunk)
                progress.bytes_downloaded = f.tell()
                if on_progress:
                    on_progress(progress)

        actual = sha256.hexdigest()
        if actual.lower() != expected.lower():
            path.unlink(missing_ok=True)
            raise RuntimeError(
                f"Hash mismatch: expected {expected[:16]}... got {actual[:16]}..."
            )
        logger.info("Hash verified: %s", path.name)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def list_local_models(self) -> List[Path]:
        """List GGUF files in the models directory."""
        return sorted(self._models_dir.glob("*.gguf"))

    def get_local_model_path(self, filename: str) -> Optional[Path]:
        """Get full path for a local GGUF file."""
        path = self._models_dir / filename
        return path if path.exists() else None
