import json
import os
from time import time
import chromadb
from dotenv import load_dotenv

load_dotenv()

# =========================
# Chroma Cloud Config
# =========================

API_KEY = os.getenv("CHROMA_API_KEY")
TENANT = os.getenv("CHROMA_TENANT")
DATABASE = os.getenv("CHROMA_DATABASE")
start = time()
client = chromadb.CloudClient(
    api_key=API_KEY,
    tenant=TENANT,
    database=DATABASE,
)

# =========================
# Repository Config
# =========================

repo_name = os.getenv("REPO_NAME", "daily-drive")

collection = client.get_or_create_collection(name=repo_name)

# =========================
# Load Chunks
# =========================

with open("Output/chunks.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)
loaded = time()
print(f"Loaded {len(chunks)} chunks")

uploaded = 0
skipped = 0

# =========================
# Upload Chunks
# =========================

for idx, chunk in enumerate(chunks):
    metadata = chunk.get("metadata", {})
    source = metadata.get("source", "unknown")

    # -------------------------
    # Build deterministic IDs
    # -------------------------

    if source == "issue":
        issue_number = metadata.get("number", idx)

        doc_id = f"{repo_name}_issue_{issue_number}"

    elif source == "commit":
        commit_hash = metadata.get("short_hash")

        if not commit_hash:
            commit_hash = metadata.get("hash", idx)

        doc_id = f"{repo_name}_commit_{commit_hash}"

    elif source == "code":
        file_path = metadata.get("file_path", "unknown_file")
        symbol_name = metadata.get("symbol_name", "unknown_symbol")

        safe_path = file_path.replace("/", "_").replace("\\", "_").replace(":", "_")

        doc_id = f"{repo_name}_code_{safe_path}_{symbol_name}"

    elif source == "pull_request":
        pr_number = metadata.get("number", idx)

        doc_id = f"{repo_name}_pr_{pr_number}"

    else:
        doc_id = f"{repo_name}_{source}_{idx}"

    # -------------------------
    # Upload
    # -------------------------

    try:
        collection.upsert(
            documents=[chunk["content"]],
            metadatas=[
                {
                    **metadata,
                    "repo_name": repo_name,
                }
            ],
            ids=[doc_id],
        )

        uploaded += 1

    except Exception as e:
        skipped += 1

        print(f"[SKIPPED] {doc_id}")
        print(f"Reason: {e}")

end = time()
# =========================
# Summary
# =========================

print("\n===== Upload Complete =====")
print(f"Uploaded : {uploaded}")
print(f"Skipped  : {skipped}")
print(f"Collection: {repo_name}")
print("===========================\n")
print(f"Time taken to load :{loaded - start:.2f} seconds")
print(f"Time taken: {end - start:.2f} seconds")
print(f"Average time per chunk: {(end - start) / len(chunks):.4f} seconds")
