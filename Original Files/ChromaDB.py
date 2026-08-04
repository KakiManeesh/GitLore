import chromadb
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("CHROMA_API_KEY")
TENANT = os.getenv("CHROMA_TENANT")
DATABASE = os.getenv("CHROMA_DATABASE")


client = chromadb.CloudClient(api_key=API_KEY, tenant=TENANT, database=DATABASE)

a = client.list_collections()
print(a)

collection = client.get_or_create_collection(name="My_Collection")

"""
collection.add(
    documents=["Python is a programming language.", "Python is used for web development."],
    metadatas=[{"source": "doc1"}, {"source": "doc2"}],
    ids=["doc1", "doc2"]
)
"""

results = collection.query(query_texts=["What is Python?"], n_results=2)

print(results)
