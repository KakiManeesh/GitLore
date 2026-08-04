import chromadb
import os
import json
from dotenv import load_dotenv


def load_env_variables():
    load_dotenv()
    CHROMA_API_KEY = os.getenv("CHROMA_API_KEY")
    CHROMA_TENANT = os.getenv("CHROMA_TENANT")
    CHROMA_DATABASE = os.getenv("CHROMA_DATABASE")
    return CHROMA_API_KEY, CHROMA_TENANT, CHROMA_DATABASE


def create_chroma_client(repo=None):
    if repo is None:
        repo = os.getenv("REPO_NAME", "daily-drive")
    CHROMA_API_KEY, CHROMA_TENANT, CHROMA_DATABASE = load_env_variables()
    client = chromadb.CloudClient(
        api_key=CHROMA_API_KEY, tenant=CHROMA_TENANT, database=CHROMA_DATABASE
    )
    collection = client.get_or_create_collection(name=f"{repo}")
    return collection


def query_chroma(collection, query, n=7):
    query_result = collection.query(
        query_texts=[query],
        n_results=n,
    )
    return query_result
