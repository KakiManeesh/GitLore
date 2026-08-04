import json
import os
import re
from os import getenv

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from rank_bm25 import BM25Okapi

from chroma_retriever import create_chroma_client, query_chroma

load_dotenv()

groq_api = getenv("GROQ_API_KEY")

model = ChatGroq(
    api_key=groq_api,
    model="llama-3.1-8b-instant",
    temperature=0.2,
)


# =====================================================
# HYBRID SEARCH SETUP
# =====================================================


def tokenize(text):
    return re.findall(r"\w+", text.lower())


def build_bm25_index(chunks_path="Output/chunks.json"):
    try:
        chunks = json.load(open(chunks_path))
        texts = [c["content"] for c in chunks]
        bm25 = BM25Okapi([tokenize(t) for t in texts])
        return bm25, chunks
    except Exception as e:
        print(f"BM25 index build failed: {e}")
        return None, []


bm25_index, bm25_chunks = build_bm25_index()


# =====================================================
# CROSS-ENCODER RERANKER
# =====================================================


def load_reranker():
    try:
        from sentence_transformers import CrossEncoder

        return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    except ImportError:
        print("sentence-transformers not installed, cross-encoder disabled.")
        return None


reranker = load_reranker()


def rerank_with_crossencoder(query, combined_docs, combined_metas, top_k=5):
    if reranker is None or not combined_docs:
        return combined_docs[:top_k], combined_metas[:top_k]

    pairs = [(query, doc) for doc in combined_docs]
    scores = reranker.predict(pairs)

    ranked = sorted(
        zip(scores, combined_docs, combined_metas), key=lambda x: x[0], reverse=True
    )

    docs = [doc for _, doc, _ in ranked[:top_k]]
    metas = [meta for _, _, meta in ranked[:top_k]]

    return docs, metas


# =====================================================
# RECIPROCAL RANK FUSION
# =====================================================


def reciprocal_rank_fusion(dense_results, bm25_results, k=60):
    scores = {}

    for rank, (doc, meta) in enumerate(dense_results):
        doc_id = meta.get("file_path", "") + meta.get("symbol_name", "")
        scores[doc_id] = {
            "score": scores.get(doc_id, {}).get("score", 0) + 1 / (rank + k),
            "doc": doc,
            "meta": meta,
        }

    for rank, (doc, meta) in enumerate(bm25_results):
        doc_id = meta.get("file_path", "") + meta.get("symbol_name", "")
        scores[doc_id] = {
            "score": scores.get(doc_id, {}).get("score", 0) + 1 / (rank + k),
            "doc": doc,
            "meta": meta,
        }

    fused = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
    return [(item["doc"], item["meta"]) for _, item in fused]


# =====================================================
# HYBRID SEARCH WITH RRF + CROSS-ENCODER
# =====================================================


def hybrid_search(collection, query, n_results=10, top_k=5):
    dense_raw = collection.query(query_texts=[query], n_results=n_results)

    bm25_scores = bm25_index.get_scores(tokenize(query))
    bm25_top_indices = sorted(
        range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True
    )[:n_results]

    dense_results = list(zip(dense_raw["documents"][0], dense_raw["metadatas"][0]))

    bm25_results = [
        (
            bm25_chunks[idx]["content"],
            {
                "file_path": bm25_chunks[idx].get("file_path", "N/A"),
                "symbol_name": bm25_chunks[idx].get("symbol_name", "N/A"),
                "source": bm25_chunks[idx].get("source", "code"),
            },
        )
        for idx in bm25_top_indices
    ]

    fused = reciprocal_rank_fusion(dense_results, bm25_results)

    fused_docs = [doc for doc, _ in fused]
    fused_metas = [meta for _, meta in fused]

    docs, metas = rerank_with_crossencoder(query, fused_docs, fused_metas, top_k=top_k)

    return {"documents": [docs], "metadatas": [metas]}


# =====================================================
# REPO CONTEXT HELPER
# =====================================================


def get_repo_context(repo_path):
    files = []
    for root, dirs, filenames in os.walk(repo_path):
        dirs[:] = [
            d
            for d in dirs
            if d not in {".git", "node_modules", ".next", "dist", "__pycache__"}
        ]
        for f in filenames:
            if not f.startswith("."):
                files.append(os.path.relpath(os.path.join(root, f), repo_path))
    return "\n".join(sorted(files))


# =====================================================
# STEP 0 : Clarify Question
# =====================================================


def clarify_question(model, query: str, repo_context: str):
    SYSTEM_PROMPT = f"""
You understand this repository:

{repo_context}

Your job: clarify what the user is ACTUALLY asking.

Return JSON:

{{
    "clarified_question": "what you think they're asking",
    "aspects": ["aspect 1", "aspect 2", "aspect 3"]
}}

Example:
{{
    "clarified_question": "Show me where task creation is implemented and how it updates the UI",
    "aspects": ["implementation location", "code that creates task", "how UI updates"]
}}
"""

    response = model.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=query)]
    )

    try:
        return json.loads(response.content)
    except Exception:
        return {
            "clarified_question": query,
            "aspects": ["general implementation details"],
        }


# =====================================================
# STEP 1 : Generate Subqueries
# =====================================================


def generate_subqueries(model, query: str, repo_context: str, aspects: list):
    SYSTEM_PROMPT = f"""
You are analyzing this repository structure:

{repo_context}

The user wants to understand: {query}

Focus on these aspects: {", ".join(aspects)}

Your ONLY task is to break this into retrieval questions.
Consider what files and patterns you see in the structure.

Rules:
- Generate between 3 and 6 realistic subqueries (no API endpoints, no features that don't exist)
- Each subquery should retrieve ONE aspect and map to one of the listed aspects
- Do NOT answer the question
- Output ONLY valid JSON

Example:

{{
    "subqueries":[
        "Where is authentication implemented?",
        "How is user state managed?",
        "Which files interact with Firebase?"
    ]
}}
"""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=query),
    ]

    response = model.invoke(messages)

    try:
        return json.loads(response.content)["subqueries"]
    except Exception:
        print("Failed to parse JSON. Using original query.")
        return [query]


# =====================================================
# STEP 2 : Reflection Step
# =====================================================


def reflection_step(model, question, aspects, current_context):
    SYSTEM_PROMPT = f"""
You are investigating a software repository.

The user wants to understand: {question}

Key aspects to cover: {", ".join(aspects)}

Your job is NOT to answer the question.

Determine whether enough information exists to cover ALL aspects.

Return ONLY valid JSON.

Format:

{{
    "enough": true,
    "next_query": "",
    "source_filter": "code",
    "priority": "high"
}}

or

{{
    "enough": false,
    "next_query": "what should be searched next",
    "source_filter": "code",
    "priority": "high"
}}

Valid source_filter values: "code", "commit", "issue", "pr".
If the next search should be broad, use "code".
"""

    USER_PROMPT = f"""
Question:

{question}

Current Evidence (files and symbols retrieved so far):

{current_context}
"""

    response = model.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=USER_PROMPT),
        ]
    )

    try:
        reflection = json.loads(response.content)
        if not isinstance(reflection, dict):
            return {
                "enough": True,
                "next_query": "",
                "source_filter": "code",
                "priority": "medium",
            }
        reflection.setdefault("enough", True)
        reflection.setdefault("next_query", "")
        reflection.setdefault("source_filter", "code")
        reflection.setdefault("priority", "medium")
        return reflection
    except Exception:
        return {
            "enough": True,
            "next_query": "",
            "source_filter": "code",
            "priority": "medium",
        }


# =====================================================
# STEP 3 : Setup Chroma
# =====================================================

collection = create_chroma_client(repo=os.getenv("REPO_NAME", "daily-drive"))

query = input("Ask GitLore: ")

repo_context = get_repo_context(".")

print("\nClarifying question...")
clarification = clarify_question(model, query, repo_context)
clarified_question = clarification.get("clarified_question", query)
aspects = clarification.get("aspects", ["general implementation details"])

print(f"\nClarified: {clarified_question}")
print(f"Aspects: {', '.join(aspects)}")

subqueries = generate_subqueries(model, clarified_question, repo_context, aspects)

print("\nGenerated Subqueries\n")
for q in subqueries:
    print("-", q)


# =====================================================
# STEP 4 : Iterative Retrieval with Hybrid Search
# =====================================================

all_docs = []
all_metas = []
seen = set()

pending_queries = subqueries.copy()
pending_sources = ["code"] * len(pending_queries)

reflection = {"enough": False}

MAX_ITERATIONS = 15
iteration = 0
seen_queries = set()


def build_retrieval_where(source_filter):
    if source_filter in {"code", "commit", "issue", "pr"}:
        return {"source": source_filter}
    return None


while (
    pending_queries and reflection.get("enough") is False and iteration < MAX_ITERATIONS
):
    iteration += 1
    print(f"\n========== Iteration {iteration} ==========\n")

    current_query = pending_queries.pop(0)
    current_source = pending_sources.pop(0)

    query_hash = hash(current_query)
    if query_hash in seen_queries:
        print("⚠️  Detected query cycle, stopping.")
        reflection["enough"] = True
        break
    seen_queries.add(query_hash)

    print("Searching:", current_query)

    try:
        retrieval_where = build_retrieval_where(current_source)

        if bm25_index is not None:
            results = hybrid_search(
                collection=collection, query=current_query, n_results=10, top_k=5
            )
        else:
            query_kwargs = {
                "query_texts": [current_query],
                "n_results": 10,
            }
            if retrieval_where:
                query_kwargs["where"] = retrieval_where
            results = collection.query(**query_kwargs)

        docs = results["documents"][0]
        metas = results["metadatas"][0]

    except Exception as e:
        print("Retrieval Error:", e)
        continue

    for doc, meta in zip(docs, metas):
        unique_id = (
            meta.get("source"),
            meta.get("file_path"),
            meta.get("symbol_name"),
            meta.get("hash"),
            meta.get("number"),
        )
        if unique_id in seen:
            continue
        seen.add(unique_id)
        all_docs.append(doc)
        all_metas.append(meta)

    evidence = "\n".join(
        [
            f"- {m.get('file_path')} → {m.get('symbol_name')} ({m.get('source')})"
            for m in all_metas[-5:]
        ]
    )

    reflection = reflection_step(
        model=model,
        question=clarified_question,
        aspects=aspects,
        current_context=evidence,
    )

    print("\nReflection Result:")
    print(reflection)

    if reflection.get("enough") is True:
        print("\nEnough context gathered.\n")
        break

    next_query = reflection.get("next_query", "").strip()
    next_source = reflection.get("source_filter", "code")

    if next_query:
        next_hash = hash(next_query)
        if next_hash in seen_queries:
            print("⚠️  Detected next query would cycle, forcing stop.")
            reflection["enough"] = True
            break

        print("Next Search:", next_query)
        print("Source Filter:", next_source)
        pending_queries.append(next_query)
        pending_sources.append(next_source)

print(f"\nRetrieved {len(all_docs)} unique chunks.\n")


# =====================================================
# STEP 5 : Build Context (with token cap)
# =====================================================

context = ""
context_tokens = 0
MAX_CONTEXT_TOKENS = 4500

for i, (doc, meta) in enumerate(zip(all_docs, all_metas), start=1):
    source = meta.get("source", "unknown")

    chunk = f"""
==============================
DOCUMENT {i}

SOURCE: {source}
FILE: {meta.get("file_path", "N/A")}
SYMBOL: {meta.get("symbol_name", "N/A")}
==============================

{doc}

"""

    chunk_tokens = len(chunk) // 4

    if context_tokens + chunk_tokens > MAX_CONTEXT_TOKENS:
        context += "\n...(remaining documents truncated due to token limit)\n"
        print(f"⚠️  Context truncated at {i - 1} documents to stay within token limit.")
        break

    context += chunk
    context_tokens += chunk_tokens


# =====================================================
# STEP 6 : Final Answer
# =====================================================

SYSTEM_PROMPT = f"""
You are GitLore, an expert repository analysis assistant.

The user originally asked: {query}
We clarified this as: {clarified_question}
Key aspects to cover: {", ".join(aspects)}

Rules:

- Use ONLY the provided repository documents.
- Never invent functionality.
- If information is missing, explicitly say so.
- Prefer explaining relationships between files rather than listing them.
- Cite file names whenever possible.
- Think like a senior software engineer reviewing an unfamiliar repository.
"""

USER_PROMPT = f"""
Repository Documents:

{context}

User Question:

{clarified_question}

Answer using the format below.

Summary:
...

Relevant Files:
- ...
- ...

Detailed Explanation:
...
"""

messages = [
    SystemMessage(content=SYSTEM_PROMPT),
    HumanMessage(content=USER_PROMPT),
]

response = model.invoke(messages)

print("\n==============================")
print("GitLore Answer")
print("==============================\n")
print(response.content)
