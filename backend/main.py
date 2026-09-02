import argparse
import sys

from backend.agent.agent import AgenticRagSystem
from backend.ingestion.ingestion_manager import IngestionManager
from backend.llm import create_chat_model


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

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

    model = create_chat_model()
    result = AgenticRagSystem(model, args.repository_id).query(args.question)
    print(result["answer"])


if __name__ == "__main__":
    main()
