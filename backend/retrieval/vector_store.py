import chromadb

from backend.config import config


class VectorStore:
    _client = None

    @classmethod
    def get_client(cls):
        if cls._client is not None:
            return cls._client

        if config.CHROMA_API_KEY and config.CHROMA_TENANT and config.CHROMA_DATABASE:
            cls._client = chromadb.CloudClient(
                api_key=config.CHROMA_API_KEY,
                tenant=config.CHROMA_TENANT,
                database=config.CHROMA_DATABASE,
            )
        else:
            cls._client = chromadb.PersistentClient(path=str(config.LOCAL_CHROMA_DIR))

        return cls._client

    @classmethod
    def get_collection(cls, repository_id: str):
        client = cls.get_client()
        return client.get_or_create_collection(name=repository_id)

    @classmethod
    def upsert_chunks(cls, repository_id: str, chunks: list[dict]) -> dict:
        collection = cls.get_collection(repository_id)
        uploaded = 0
        skipped = 0

        for idx, chunk in enumerate(chunks):
            metadata = chunk.get("metadata", {})
            source = metadata.get("source", "unknown")
            doc_id = cls.build_document_id(repository_id, source, metadata, idx)

            try:
                collection.upsert(
                    documents=[chunk["content"]],
                    metadatas=[{**metadata, "repository_id": repository_id}],
                    ids=[doc_id],
                )
                uploaded += 1
            except Exception:
                skipped += 1

        return {
            "uploaded": uploaded,
            "skipped": skipped,
            "collection_name": repository_id,
        }

    @staticmethod
    def build_document_id(
        repository_id: str,
        source: str,
        metadata: dict,
        fallback_index: int,
    ) -> str:
        if source == "issue":
            return f"{repository_id}_issue_{metadata.get('number', fallback_index)}"

        if source == "commit":
            commit_hash = metadata.get("short_hash") or metadata.get("hash", fallback_index)
            return f"{repository_id}_commit_{commit_hash}"

        if source == "code":
            file_path = metadata.get("file_path", "unknown_file")
            symbol_name = metadata.get("symbol_name", "unknown_symbol")
            safe_path = file_path.replace("/", "_").replace("\\", "_").replace(":", "_")
            return f"{repository_id}_code_{safe_path}_{symbol_name}"

        if source == "pr":
            return f"{repository_id}_pr_{metadata.get('number', fallback_index)}"

        return f"{repository_id}_{source}_{fallback_index}"

    @classmethod
    def query(
        cls,
        repository_id: str,
        query: str,
        n_results: int = 10,
        source_filter: str | None = None,
    ) -> dict:
        collection = cls.get_collection(repository_id)
        query_kwargs = {"query_texts": [query], "n_results": n_results}
        if source_filter and source_filter in {"code", "commit", "issue", "pr"}:
            query_kwargs["where"] = {"source": source_filter}
        return collection.query(**query_kwargs)
