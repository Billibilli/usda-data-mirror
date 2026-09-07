#!/usr/bin/env python3
"""Fetch configured USDA Socrata datasets with provenance and integrity gates."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "datasets.json"
DATA_DIR = ROOT / "data"
META_DIR = ROOT / "meta"
USER_AGENT = "Billibilli/usda-data-mirror/1.0"


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def request_json(url: str) -> tuple[Any, dict[str, str]]:
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    token = os.environ.get("USDA_APP_TOKEN")
    if token:
        headers["X-App-Token"] = token
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        content_type = response.headers.get("Content-Type", "")
        body = response.read()
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} from {url}")
        if "json" not in content_type.lower():
            raise RuntimeError(f"non-JSON response from {url}: {content_type!r}")
        return json.loads(body), {k.lower(): v for k, v in response.headers.items()}


def schema(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({str(key) for row in rows for key in row})


def previous_count(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return len(old) if isinstance(old, list) else None


def fetch_dataset(item: dict[str, Any]) -> dict[str, Any]:
    dataset_id = item["id"]
    domain = item["domain"]
    limit = int(item.get("limit", 50000))
    data_url = f"https://{domain}/resource/{dataset_id}.json?" + urllib.parse.urlencode({"$limit": limit})
    metadata_url = f"https://{domain}/api/views/{dataset_id}"

    metadata, _ = request_json(metadata_url)
    metadata_id = metadata.get("id") if isinstance(metadata, dict) else None
    if metadata_id != dataset_id:
        raise RuntimeError(f"metadata ID mismatch for {dataset_id}: {metadata_id!r}")

    rows, response_headers = request_json(data_url)
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"{dataset_id}: expected non-empty JSON array")
    if not all(isinstance(row, dict) for row in rows):
        raise RuntimeError(f"{dataset_id}: rows must be JSON objects")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)
    output = DATA_DIR / f"{dataset_id}.json"
    old_count = previous_count(output)
    if old_count and len(rows) < max(1, old_count // 2):
        raise RuntimeError(f"{dataset_id}: row-count collapse {old_count} -> {len(rows)}")

    columns = schema(rows)
    payload = canonical_bytes(rows)
    output.write_bytes(payload)
    (META_DIR / f"{dataset_id}.sha256").write_text(f"{sha256(payload)}  data/{dataset_id}.json\n", encoding="utf-8")

    return {
        "key": item["key"],
        "id": dataset_id,
        "name": metadata.get("name"),
        "description": metadata.get("description"),
        "source_updated_at_unix": metadata.get("rowsUpdatedAt"),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_url": data_url,
        "metadata_url": metadata_url,
        "row_count": len(rows),
        "previous_row_count": old_count,
        "columns": columns,
        "schema_sha256": sha256(canonical_bytes(columns)),
        "data_sha256": sha256(payload),
        "content_type": response_headers.get("content-type"),
    }


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    datasets = config.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise RuntimeError("config/datasets.json has no datasets")

    results = []
    failures = []
    for item in datasets:
        try:
            result = fetch_dataset(item)
            results.append(result)
            print(f"OK {result['id']}: {result['row_count']} rows", file=sys.stderr)
        except (OSError, ValueError, RuntimeError, urllib.error.URLError) as exc:
            failures.append({"id": item.get("id"), "error": f"{type(exc).__name__}: {exc}"})
            print(f"FAIL {item.get('id')}: {exc}", file=sys.stderr)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if not failures else "partial" if results else "failed",
        "datasets": results,
        "failures": failures,
    }
    META_DIR.mkdir(parents=True, exist_ok=True)
    (META_DIR / "manifest.json").write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
