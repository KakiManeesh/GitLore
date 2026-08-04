import json
from datetime import datetime, timezone

from backend.ingestion.chunk_builder import build_repository_chunks, save_chunks
from backend.ingestion.github_client import GitHubRepositoryClient
from backend.repositories import (
    ensure_repository_dir,
    list_manifests,
    load_manifest,
    normalize_repository_id,
    repository_chunks_path,
    repository_clone_path,
    repository_graphql_path,
    save_manifest,
)
from backend.retrieval.vector_store import VectorStore


class IngestionManager:
    """Indexes GitHub repositories into chunk artifacts and Chroma."""

    def __init__(self) -> None:
        self.github = GitHubRepositoryClient()
        self.vector_store = VectorStore()

    def index_repository(self, repo_input: str) -> dict:
        owner, repo, repo_url = self.github.parse_repository_input(repo_input)
        repository_id = normalize_repository_id(owner, repo)

        ensure_repository_dir(repository_id)
        graphql_path = repository_graphql_path(repository_id)
        clone_path = repository_clone_path(repository_id)
        chunks_path = repository_chunks_path(repository_id)

        self.github.clone_repo(repo_url, clone_path)

        try:
            metadata = self.github.get_repo_metadata(owner, repo)
        except Exception:
            metadata = self.github.build_minimal_metadata(owner, repo, repo_url, clone_path)

        try:
            issues = self.github.get_all_issues(owner, repo)
        except Exception:
            issues = []

        try:
            pull_requests = self.github.get_all_pull_requests(owner, repo)
        except Exception:
            pull_requests = []

        try:
            discussions = self.github.get_all_discussions(owner, repo)
        except Exception:
            discussions = []

        try:
            releases = self.github.get_all_releases(owner, repo)
        except Exception:
            releases = []

        try:
            commits = self.github.get_all_commits(owner, repo)
        except Exception:
            commits = self.github.get_local_commits(clone_path)
        if not commits:
            commits = self.github.get_local_commits(clone_path)

        graphql_data = {
            "metadata": metadata,
            "license_name": metadata["licenseInfo"]["name"] if metadata.get("licenseInfo") else None,
            "issues": issues,
            "pull_requests": pull_requests,
            "discussions": discussions,
            "releases": releases,
            "commits": commits,
        }

        graphql_path.write_text(
            json.dumps(graphql_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        chunks = build_repository_chunks(graphql_data, clone_path)
        save_chunks(chunks, chunks_path)

        upload_stats = self.vector_store.upsert_chunks(repository_id, chunks)
        indexed_at = datetime.now(timezone.utc).isoformat()

        manifest = {
            "repository_id": repository_id,
            "owner": owner,
            "repo": repo,
            "repository_url": repo_url,
            "collection_name": repository_id,
            "clone_path": str(clone_path),
            "graphql_path": str(graphql_path),
            "chunks_path": str(chunks_path),
            "indexed_at": indexed_at,
            "metadata": {
                "description": metadata.get("description"),
                "primary_language": (metadata.get("primaryLanguage") or {}).get("name"),
                "stars": metadata.get("stargazerCount", 0),
                "forks": metadata.get("forkCount", 0),
                "default_branch": (metadata.get("defaultBranchRef") or {}).get("name"),
            },
            "stats": {
                "issues": len(issues),
                "pull_requests": len(pull_requests),
                "discussions": len(discussions),
                "releases": len(releases),
                "commits": len(commits),
                "chunks": len(chunks),
                **upload_stats,
            },
        }

        save_manifest(repository_id, manifest)
        return manifest

    def list_indexed_repositories(self) -> list[dict]:
        return list_manifests()

    def get_indexed_repository(self, repository_id: str) -> dict:
        manifest = load_manifest(repository_id)
        if not manifest:
            raise FileNotFoundError(f"Repository '{repository_id}' has not been indexed.")
        return manifest

    def run_ingestion(self, repo_url: str) -> dict:
        return self.index_repository(repo_url)
