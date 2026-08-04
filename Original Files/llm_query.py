from os import getenv
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from chroma_retriever import create_chroma_client, query_chroma

load_dotenv()
groq_api = getenv("GROQ_API_KEY")
model = ChatGroq(api_key=groq_api, model="llama-3.1-8b-instant", temperature=0.2)

collection = create_chroma_client(repo=getenv("REPO_NAME", "daily-drive"))
query = input("Ask GitLore: ")
results = query_chroma(collection=collection, query=query, n=15)

docs = results["documents"][0]
metas = results["metadatas"][0]
context = ""

for i, (doc, meta) in enumerate(zip(docs, metas), start=1):
    source = meta.get("source", "unknown")
    file_path = meta.get("file_path", "N/A")

    context += f"""
[DOCUMENT {i}]
SOURCE: {source}
FILE: {file_path}

{doc}

"""


SYSTEM_PROMPT = """
You are GitLore, a repository analysis assistant.

Rules:
- Answer ONLY from the provided repository documents.
- Never invent functionality not present in the documents.
- When discussing code, cite the relevant file names.
- If information is missing, explicitly say it is not available in the retrieved documents.
- Be concise and technical.
"""

USER_PROMPT = f"""
Repository Documents:

{context}

Question:
{query}

Use the below format for your answer:
Answer Format:

Summary:
...

Relevant Files:
- ...
- ...

Evidence:
...

"""

messages = [
    SystemMessage(content=SYSTEM_PROMPT),
    HumanMessage(content=USER_PROMPT),
]
result = model.invoke(messages)

print(result.content)
