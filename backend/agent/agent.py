import json
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage

from backend.config import config
from backend.retrieval.rag_system import RagSystem


class AgenticRagSystem:
    """Agentic RAG workflow adapted from the original scripts."""

    def __init__(self, model, repository_id: str):
        self.model = model
        self.rag = RagSystem(repository_id)
        self.repository_id = repository_id

    @staticmethod
    def extract_json_object(content: str) -> dict:
        """Extract the first JSON object from model output that may include fences or prose."""
        cleaned = content.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
        if fenced:
            cleaned = fenced.group(1)

        start = cleaned.find("{")
        if start == -1:
            raise ValueError("No JSON object found in model response.")

        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(cleaned)):
            char = cleaned[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(cleaned[start : index + 1])

        raise ValueError("Unterminated JSON object in model response.")

    def invoke_content(self, messages: list[SystemMessage | HumanMessage]) -> str:
        response = self.model.invoke(messages)
        return response.content

    @staticmethod
    def string_list(value, fallback: list[str]) -> list[str]:
        if not isinstance(value, list):
            return fallback
        normalized = [str(item).strip() for item in value if str(item).strip()]
        return normalized or fallback

    def get_repo_context(self) -> str:
        files = []
        repo_path = self.rag.clone_path
        for root, dirs, filenames in os.walk(repo_path):
            dirs[:] = [
                directory
                for directory in dirs
                if directory not in {".git", "node_modules", ".next", "dist", "__pycache__"}
            ]
            for filename in filenames:
                if not filename.startswith("."):
                    file_path = os.path.relpath(os.path.join(root, filename), repo_path)
                    files.append(file_path.replace(os.sep, "/"))
        return "\n".join(sorted(files))

    def clarify_question(self, query: str, repo_context: str) -> dict:
        system_prompt = f"""
You understand this repository:

{repo_context}

Your job: clarify what the user is actually asking.

Return only valid JSON. Do not call tools. No tools are available.

{{
  "clarified_question": "what you think they are asking",
  "aspects": ["aspect 1", "aspect 2", "aspect 3"]
}}
"""
        try:
            content = self.invoke_content(
                [SystemMessage(content=system_prompt), HumanMessage(content=query)]
            )
            payload = self.extract_json_object(content)
            return {
                "clarified_question": str(payload.get("clarified_question") or query),
                "aspects": self.string_list(
                    payload.get("aspects"),
                    ["general implementation details"],
                ),
            }
        except Exception:
            return {
                "clarified_question": query,
                "aspects": ["general implementation details"],
            }

    def generate_subqueries(self, query: str, repo_context: str, aspects: list[str]) -> list[str]:
        system_prompt = f"""
You are analyzing this repository structure:

{repo_context}

The user wants to understand: {query}

Focus on these aspects: {", ".join(aspects)}

Generate between 3 and 6 realistic retrieval subqueries.
Return only valid JSON in this format. Do not call tools. No tools are available.

{{
  "subqueries": [
    "subquery one",
    "subquery two"
  ]
}}
"""
        try:
            content = self.invoke_content(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=query),
                ]
            )
            payload = self.extract_json_object(content)
            return self.string_list(payload.get("subqueries"), [query])
        except Exception:
            return [query]

    def reflection_step(self, question: str, aspects: list[str], current_context: str) -> dict:
        system_prompt = f"""
You are investigating a software repository.

The user wants to understand: {question}
Key aspects to cover: {", ".join(aspects)}

Return only valid JSON. Do not call tools. No tools are available.

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
"""
        user_prompt = f"""
Question:
{question}

Current Evidence:
{current_context}
"""
        try:
            content = self.invoke_content(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )
            reflection = self.extract_json_object(content)
            if not isinstance(reflection, dict):
                raise ValueError("Invalid reflection payload")
            reflection.setdefault("enough", True)
            reflection.setdefault("next_query", "")
            reflection.setdefault("source_filter", "code")
            reflection.setdefault("priority", "medium")
            if reflection["source_filter"] not in {"code", "commit", "issue", "pr"}:
                reflection["source_filter"] = "code"
            return reflection
        except Exception:
            return {
                "enough": True,
                "next_query": "",
                "source_filter": "code",
                "priority": "medium",
            }

    def query(self, user_question: str) -> dict:
        repo_context = self.get_repo_context()
        clarification = self.clarify_question(user_question, repo_context)
        clarified_question = clarification.get("clarified_question", user_question)
        aspects = clarification.get("aspects", ["general implementation details"])
        subqueries = self.generate_subqueries(clarified_question, repo_context, aspects)

        all_docs: list[str] = []
        all_metas: list[dict] = []
        seen_docs = set()
        pending_queries = subqueries.copy()
        pending_sources = ["code"] * len(pending_queries)
        reflection = {"enough": False}
        seen_queries = set()
        iteration = 0

        while (
            pending_queries
            and reflection.get("enough") is False
            and iteration < config.MAX_AGENT_ITERATIONS
        ):
            iteration += 1
            current_query = pending_queries.pop(0)
            current_source = pending_sources.pop(0)

            query_key = (current_query, current_source)
            if query_key in seen_queries:
                reflection["enough"] = True
                break
            seen_queries.add(query_key)

            try:
                results = self.rag.hybrid_search(
                    current_query,
                    n_results=config.HYBRID_SEARCH_RESULTS,
                    top_k=config.HYBRID_TOP_K,
                    source_filter=current_source,
                )
                docs = results.get("documents", [[]])[0]
                metas = results.get("metadatas", [[]])[0]
            except Exception:
                continue

            for doc, meta in zip(docs, metas):
                unique_id = (
                    meta.get("source"),
                    meta.get("file_path"),
                    meta.get("symbol_name"),
                    meta.get("hash"),
                    meta.get("number"),
                )
                if unique_id in seen_docs:
                    continue
                seen_docs.add(unique_id)
                all_docs.append(doc)
                all_metas.append(meta)

            evidence = "\n".join(
                [
                    f"- {meta.get('file_path', 'N/A')} -> {meta.get('symbol_name', 'N/A')} ({meta.get('source', 'unknown')})"
                    for meta in all_metas[-5:]
                ]
            )
            reflection = self.reflection_step(clarified_question, aspects, evidence)

            if reflection.get("enough") is True:
                break

            next_query = reflection.get("next_query", "").strip()
            next_source = reflection.get("source_filter", "code")
            if next_query:
                pending_queries.append(next_query)
                pending_sources.append(next_source)

        context = ""
        context_tokens = 0
        for index, (doc, meta) in enumerate(zip(all_docs, all_metas), start=1):
            chunk = (
                "==============================\n"
                f"DOCUMENT {index}\n"
                f"SOURCE: {meta.get('source', 'unknown')}\n"
                f"FILE: {meta.get('file_path', 'N/A')}\n"
                f"SYMBOL: {meta.get('symbol_name', 'N/A')}\n"
                "==============================\n\n"
                f"{doc}\n\n"
            )
            chunk_tokens = len(chunk) // 4
            if context_tokens + chunk_tokens > config.MAX_CONTEXT_TOKENS:
                context += "\n...(remaining documents truncated due to token limit)\n"
                break
            context += chunk
            context_tokens += chunk_tokens

        system_prompt = f"""
You are GitLore, an expert repository analysis assistant.

The user originally asked: {user_question}
We clarified this as: {clarified_question}
Key aspects to cover: {", ".join(aspects)}

Rules:
- Use only the provided repository documents.
- Never invent functionality.
- If information is missing, explicitly say so.
- Prefer explaining relationships between files rather than listing them.
- Cite file names whenever possible.
- Think like a senior software engineer reviewing an unfamiliar repository.
- Do not call tools. No tools are available.
"""
        user_prompt = f"""
Repository Documents:

{context}

User Question:

{clarified_question}

Answer using this format:

Summary:
...

Relevant Files:
- ...
- ...

Detailed Explanation:
...
"""
        try:
            answer = self.invoke_content(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )
        except Exception as exc:
            answer = self.build_extract_answer(user_question, clarified_question, all_docs, all_metas, exc)
        return {
            "repository_id": self.repository_id,
            "answer": answer,
            "clarified_question": clarified_question,
            "subqueries": subqueries,
            "documents_retrieved": len(all_docs),
            "aspects": aspects,
        }

    @staticmethod
    def build_extract_answer(
        user_question: str,
        clarified_question: str,
        docs: list[str],
        metas: list[dict],
        error: Exception,
    ) -> str:
        if not docs:
            return (
                "Summary:\n"
                "GitLore could not retrieve repository evidence for this question.\n\n"
                "Relevant Files:\n"
                "- None retrieved.\n\n"
                "Detailed Explanation:\n"
                f"The LLM synthesis step also failed: {error}"
            )

        lines = [
            "Summary:",
            "GitLore retrieved repository evidence, but the LLM synthesis step failed. The grounded excerpts below are returned instead.",
            "",
            "Relevant Files:",
        ]
        for meta in metas[:5]:
            file_path = meta.get("file_path") or meta.get("source") or "repository artifact"
            symbol = meta.get("symbol_name")
            lines.append(f"- {file_path}{f' -> {symbol}' if symbol else ''}")

        lines.extend(
            [
                "",
                "Detailed Explanation:",
                f"Original question: {user_question}",
                f"Clarified question: {clarified_question}",
                f"Synthesis error: {error}",
                "",
                "Grounded excerpts:",
            ]
        )
        for index, (doc, meta) in enumerate(zip(docs[:3], metas[:3]), start=1):
            source = meta.get("source", "unknown")
            file_path = meta.get("file_path", "N/A")
            symbol = meta.get("symbol_name", "N/A")
            excerpt = doc.strip().replace("\r\n", "\n")[:900]
            lines.append(f"\n[{index}] {source} {file_path} {symbol}\n{excerpt}")

        return "\n".join(lines)
