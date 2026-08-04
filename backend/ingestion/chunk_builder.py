import json
from pathlib import Path

from backend.ingestion.code_chunker import chunk_codebase


def load_graphql_data(json_path: str | Path) -> dict:
    with open(json_path, "r", encoding="utf-8") as file:
        return json.load(file)


def get_repo_name(data: dict) -> str:
    return data.get("metadata", {}).get("name") or "unknown"


def get_author_login(item: dict) -> str:
    author = item.get("author") or {}
    return author.get("login") or author.get("name") or "unknown"


def get_nodes(container) -> list:
    if not container:
        return []
    if isinstance(container, list):
        return container
    return container.get("nodes") or []


def append_section(lines: list[str], title: str, body: str) -> None:
    lines.append("")
    lines.append(f"{title}:")
    lines.append(str(body).strip() if body else "N/A")


def chunk_issues(data: dict) -> list[dict]:
    repo_name = get_repo_name(data)
    chunks: list[dict] = []

    for issue in data.get("issues") or []:
        number = issue.get("number")
        title = issue.get("title") or ""
        body = issue.get("body") or ""
        state = issue.get("state") or "unknown"
        author = get_author_login(issue)

        lines = [f"Issue #{number} [{state}]: {title}".strip()]
        append_section(lines, "Description", body)

        comments = get_nodes(issue.get("comments"))
        if comments:
            lines.append("")
            lines.append("Comments:")
            for comment in comments:
                comment_author = get_author_login(comment)
                comment_body = (comment.get("body") or "").strip()
                lines.append(f"{comment_author}: {comment_body}")

        chunks.append(
            {
                "content": "\n".join(lines).strip(),
                "metadata": {
                    "source": "issue",
                    "number": number,
                    "state": state,
                    "author": author,
                    "repo": repo_name,
                    "createdAt": issue.get("createdAt"),
                    "updatedAt": issue.get("updatedAt"),
                    "closedAt": issue.get("closedAt"),
                },
            }
        )

    return chunks


def chunk_pull_requests(data: dict) -> list[dict]:
    repo_name = get_repo_name(data)
    chunks: list[dict] = []

    for pr in data.get("pull_requests") or []:
        number = pr.get("number")
        title = pr.get("title") or ""
        body = pr.get("body") or ""
        state = pr.get("state") or "unknown"
        author = get_author_login(pr)

        lines = [f"PR #{number} [{state}]: {title}".strip()]
        append_section(lines, "Description", body)

        comments = get_nodes(pr.get("comments"))
        if comments:
            lines.append("")
            lines.append("Comments:")
            for comment in comments:
                comment_author = get_author_login(comment)
                comment_body = (comment.get("body") or "").strip()
                lines.append(f"{comment_author}: {comment_body}")

        review_lines: list[str] = []
        inline_lines: list[str] = []
        for review in get_nodes(pr.get("reviews")):
            review_author = get_author_login(review)
            review_body = (review.get("body") or "").strip()
            review_state = review.get("state") or "unknown"
            if review_body:
                review_lines.append(f"{review_author} [{review_state}]: {review_body}")

            for inline_comment in get_nodes(review.get("comments")):
                inline_author = get_author_login(inline_comment)
                inline_body = (inline_comment.get("body") or "").strip()
                path = inline_comment.get("path")
                position = inline_comment.get("position")
                if path and position is not None:
                    inline_lines.append(f"{inline_author} ({path}:{position}): {inline_body}")
                else:
                    inline_lines.append(f"{inline_author}: {inline_body}")

        if review_lines:
            lines.append("")
            lines.append("Reviews:")
            lines.extend(review_lines)

        if inline_lines:
            lines.append("")
            lines.append("Code Review Comments:")
            lines.extend(inline_lines)

        chunks.append(
            {
                "content": "\n".join(lines).strip(),
                "metadata": {
                    "source": "pr",
                    "number": number,
                    "state": state,
                    "author": author,
                    "repo": repo_name,
                    "createdAt": pr.get("createdAt"),
                    "mergedAt": pr.get("mergedAt"),
                    "closedAt": pr.get("closedAt"),
                    "additions": pr.get("additions"),
                    "deletions": pr.get("deletions"),
                    "changedFiles": pr.get("changedFiles"),
                },
            }
        )

    return chunks


def chunk_commits(data: dict) -> list[dict]:
    repo_name = get_repo_name(data)
    chunks: list[dict] = []

    for commit in data.get("commits") or []:
        headline = (
            commit.get("messageHeadline")
            or commit.get("message")
            or commit.get("oid")
            or ""
        )
        body = (commit.get("messageBody") or "").strip()
        author_name = get_author_login(commit)

        message_lines = [headline.strip()]
        if body:
            message_lines.extend(["", body])
        message = "\n".join(message_lines).strip()

        additions = commit.get("additions")
        deletions = commit.get("deletions")
        changed_files = commit.get("changedFiles")

        content = (
            f"Commit: {headline.strip()}\n\n"
            f"Message:\n{message or 'N/A'}\n\n"
            f"Author:\n{author_name}\n\n"
            "Stats:\n"
            f"{additions if additions is not None else 0} additions\n"
            f"{deletions if deletions is not None else 0} deletions\n"
            f"{changed_files if changed_files is not None else 0} files changed"
        )

        chunks.append(
            {
                "content": content.strip(),
                "metadata": {
                    "source": "commit",
                    "hash": commit.get("oid"),
                    "short_hash": commit.get("abbreviatedOid"),
                    "author": author_name,
                    "date": commit.get("committedDate"),
                    "additions": additions,
                    "deletions": deletions,
                    "changedFiles": changed_files,
                    "repo": repo_name,
                },
            }
        )

    return chunks


def build_repository_chunks(graphql_data: dict, repo_path: str | Path) -> list[dict]:
    issue_chunks = chunk_issues(graphql_data)
    pr_chunks = chunk_pull_requests(graphql_data)
    commit_chunks = chunk_commits(graphql_data)
    code_chunks = chunk_codebase(str(repo_path))

    chunks: list[dict] = []
    chunks.extend(issue_chunks)
    chunks.extend(pr_chunks)
    chunks.extend(commit_chunks)
    chunks.extend(code_chunks)
    return chunks


def save_chunks(chunks: list[dict], output_file: str | Path) -> None:
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(chunks, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
