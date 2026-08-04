import argparse

from langchain_groq import ChatGroq

from backend.agent.agent import AgenticRagSystem
from backend.config import config
from backend.ingestion.ingestion_manager import IngestionManager


def main():
    parser = argparse.ArgumentParser(description="GitLore backend utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Index a GitHub repository")
    index_parser.add_argument("repository_url")

    query_parser = subparsers.add_parser("query", help="Query an indexed repository")
    query_parser.add_argument("repository_id")
    query_parser.add_argument("question")

    args = parser.parse_args()

    if args.command == "index":
        manifest = IngestionManager().index_repository(args.repository_url)
        print(f"Indexed {manifest['repository_id']} with {manifest['stats']['chunks']} chunks")
        return

    model = ChatGroq(
        api_key=config.GROQ_API_KEY,
        model=config.GROQ_MODEL,
        temperature=config.GROQ_TEMPERATURE,
    )
    result = AgenticRagSystem(model, args.repository_id).query(args.question)
    print(result["answer"])


if __name__ == "__main__":
    main()
