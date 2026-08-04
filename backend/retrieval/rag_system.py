import json
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from backend.config import config
from backend.repositories import load_manifest
from backend.retrieval.vector_store import VectorStore


def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


class RagSystem:
    """Hybrid retrieval over Chroma plus BM25 for one indexed repository."""

    reranker = None

    def __init__(self, repository_id: str):
        self.repository_id = repository_id
        self.manifest = load_manifest(repository_id)
        if not self.manifest:
            raise FileNotFoundError(f"Repository '{repository_id}' has not been indexed.")

        self.collection = VectorStore.get_collection(repository_id)
        self.clone_path = Path(self.manifest["clone_path"])
        self.chunks_path = Path(self.manifest["chunks_path"])
        self.bm25_index, self.bm25_chunks = self.build_bm25_index(self.chunks_path)
        self.reranker = self.load_reranker()

    @classmethod
    def load_reranker(cls):
        if cls.reranker is not None:
            return cls.reranker

        try:
            from sentence_transformers import CrossEncoder

            cls.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        except Exception:
            cls.reranker = False

        return cls.reranker

    def build_bm25_index(self, chunks_path: Path):
        try:
            chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
            texts = [chunk["content"] for chunk in chunks]
            bm25 = BM25Okapi([tokenize(text) for text in texts]) if texts else None
            return bm25, chunks
        except Exception:
            return None, []

    def rerank_with_crossencoder(
        self,
        query: str,
        combined_docs: list[str],
        combined_metas: list[dict],
        top_k: int = 5,
    ) -> tuple[list[str], list[dict]]:
        if not self.reranker or not combined_docs:
            return combined_docs[:top_k], combined_metas[:top_k]

        pairs = [(query, doc) for doc in combined_docs]
        scores = self.reranker.predict(pairs)
        ranked = sorted(
            zip(scores, combined_docs, combined_metas),
            key=lambda item: item[0],
            reverse=True,
        )
        docs = [doc for _, doc, _ in ranked[:top_k]]
        metas = [meta for _, _, meta in ranked[:top_k]]
        return docs, metas

    def reciprocal_rank_fusion(
        self,
        dense_results: list[tuple[str, dict]],
        bm25_results: list[tuple[str, dict]],
        k: int = 60,
    ) -> list[tuple[str, dict]]:
        scores = {}

        for rank, (doc, meta) in enumerate(dense_results):
            doc_id = self._doc_identity(meta)
            scores[doc_id] = {
                "score": scores.get(doc_id, {}).get("score", 0) + 1 / (rank + k),
                "doc": doc,
                "meta": meta,
            }

        for rank, (doc, meta) in enumerate(bm25_results):
            doc_id = self._doc_identity(meta)
            scores[doc_id] = {
                "score": scores.get(doc_id, {}).get("score", 0) + 1 / (rank + k),
                "doc": doc,
                "meta": meta,
            }

        fused = sorted(scores.items(), key=lambda item: item[1]["score"], reverse=True)
        return [(item["doc"], item["meta"]) for _, item in fused]

    def hybrid_search(
        self,
        query: str,
        n_results: int | None = None,
        top_k: int | None = None,
        source_filter: str | None = None,
    ) -> dict:
        n_results = n_results or config.HYBRID_SEARCH_RESULTS
        top_k = top_k or config.HYBRID_TOP_K

        dense_raw = VectorStore.query(
            self.repository_id,
            query,
            n_results=n_results,
            source_filter=source_filter,
        )
        dense_results = list(
            zip(
                dense_raw.get("documents", [[]])[0],
                dense_raw.get("metadatas", [[]])[0],
            )
        )

        bm25_results: list[tuple[str, dict]] = []
        if self.bm25_index is not None and self.bm25_chunks:
            scored_chunks = []
            for idx, score in enumerate(self.bm25_index.get_scores(tokenize(query))):
                chunk = self.bm25_chunks[idx]
                metadata = chunk.get("metadata", {})
                if source_filter and metadata.get("source") != source_filter:
                    continue
                scored_chunks.append((score, chunk))

            scored_chunks.sort(key=lambda item: item[0], reverse=True)
            for _, chunk in scored_chunks[:n_results]:
                bm25_results.append((chunk["content"], chunk.get("metadata", {})))

        fused = self.reciprocal_rank_fusion(dense_results, bm25_results)
        fused_docs = [doc for doc, _ in fused]
        fused_metas = [meta for _, meta in fused]
        docs, metas = self.rerank_with_crossencoder(query, fused_docs, fused_metas, top_k=top_k)
        return {"documents": [docs], "metadatas": [metas]}

    @staticmethod
    def _doc_identity(meta: dict) -> str:
        return "|".join(
            str(meta.get(key, ""))
            for key in ("source", "file_path", "symbol_name", "hash", "number")
        )
