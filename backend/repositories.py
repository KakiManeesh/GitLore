import json
import re
from pathlib import Path

from backend.config import config


def normalize_repository_id(owner: str, repo: str) -> str:
    slug = f"{owner}__{repo}".lower()
    return re.sub(r"[^a-z0-9_.-]+", "-", slug).strip("-")


def repository_dir(repository_id: str) -> Path:
    return config.REPOSITORIES_DIR / repository_id


def repository_manifest_path(repository_id: str) -> Path:
    return repository_dir(repository_id) / "manifest.json"


def repository_graphql_path(repository_id: str) -> Path:
    return repository_dir(repository_id) / "graphql_data.json"


def repository_chunks_path(repository_id: str) -> Path:
    return repository_dir(repository_id) / "chunks.json"


def repository_clone_path(repository_id: str) -> Path:
    return repository_dir(repository_id) / "repo"


def ensure_repository_dir(repository_id: str) -> Path:
    path = repository_dir(repository_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_manifest(repository_id: str) -> dict | None:
    manifest_path = repository_manifest_path(repository_id)
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def save_manifest(repository_id: str, manifest: dict) -> dict:
    manifest_path = repository_manifest_path(repository_id)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest


def list_manifests() -> list[dict]:
    manifests: list[dict] = []
    if not config.REPOSITORIES_DIR.exists():
        return manifests

    for manifest_path in config.REPOSITORIES_DIR.glob("*/manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifests.append(manifest)
        except Exception:
            continue

    manifests.sort(key=lambda item: item.get("indexed_at", ""), reverse=True)
    return manifests
