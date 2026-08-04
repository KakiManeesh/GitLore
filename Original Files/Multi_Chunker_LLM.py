import json
from os import getenv

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from chroma_retriever import create_chroma_client, query_chroma

load_dotenv()

groq_api = getenv("GROQ_API_KEY")

model = ChatGroq(
    api_key=groq_api,
    model="llama-3.1-8b-instant",
    temperature=0.2,
)


# =====================================================
# STEP 1 : Generate Subqueries
# =====================================================


def generate_subqueries(model, query: str):
    SYSTEM_PROMPT = """
You are an expert software architect.

Your ONLY task is to break a repository question into retrieval questions.

Rules:
- Generate between 3 and 6 subqueries.
- Each subquery should retrieve ONE aspect of the answer.
- Do NOT answer the question.
- Do NOT explain anything.
- Output ONLY valid JSON.

Example:

{
    "subqueries":[
        "Where is authentication implemented?",
        "How is user state managed?",
        "Which files interact with Firebase?"
    ]
}
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
# STEP 2 : Setup Chroma
# =====================================================

collection = create_chroma_client(repo=getenv("REPO_NAME", "daily-drive"))

query = input("Ask GitLore: ")

subqueries = generate_subqueries(model, query)

print("\nGenerated Subqueries\n")

for q in subqueries:
    print("-", q)


# =====================================================
# STEP 3 : Retrieve Context
# =====================================================

all_docs = []
all_metas = []
seen = set()

for subquery in subqueries:
    results = query_chroma(
        collection=collection,
        query=subquery,
        n=5,
    )

    docs = results["documents"][0]
    metas = results["metadatas"][0]

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


print(f"\nRetrieved {len(all_docs)} unique chunks.\n")


# =====================================================
# STEP 4 : Build Context
# =====================================================

context = ""

for i, (doc, meta) in enumerate(zip(all_docs, all_metas), start=1):
    source = meta.get("source", "unknown")

    context += f"""
==============================
DOCUMENT {i}

SOURCE: {source}
FILE: {meta.get("file_path", "N/A")}
SYMBOL: {meta.get("symbol_name", "N/A")}
==============================

{doc}

"""


# =====================================================
# STEP 5 : Final Prompt
# =====================================================

SYSTEM_PROMPT = """
You are GitLore, an expert repository analysis assistant.

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

{query}

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
