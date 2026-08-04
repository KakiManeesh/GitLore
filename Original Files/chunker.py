import json
import os

from Code_Chunker import chunk_codebase


GRAPHQL_DATA_FILE = "graphql_data.json"
OUTPUT_FILE = os.path.join("Output", "chunks.json")


def load_graphql_data(json_path=GRAPHQL_DATA_FILE):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_repo_name(data):
    return data.get("metadata", {}).get("name") or "unknown"


def get_author_login(item):
    author = item.get("author") or {}
    return author.get("login") or author.get("name") or "unknown"


def get_nodes(container):
    if not container:
        return []
    if isinstance(container, list):
        return container
    return container.get("nodes") or []


def append_section(lines, title, body):
    lines.append("")
    lines.append(f"{title}:")
    if body:
        lines.append(str(body).strip())
    else:
        lines.append("N/A")


def chunk_issues(data):
    repo_name = get_repo_name(data)
    chunks = []

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


def chunk_pull_requests(data):
    repo_name = get_repo_name(data)
    chunks = []

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

        reviews = get_nodes(pr.get("reviews"))
        review_lines = []
        code_review_lines = []

        for review in reviews:
            review_author = get_author_login(review)
            review_body = (review.get("body") or "").strip()
            if review_body:
                review_state = review.get("state") or "unknown"
                review_lines.append(f"{review_author} [{review_state}]: {review_body}")

            for inline_comment in get_nodes(review.get("comments")):
                inline_author = get_author_login(inline_comment)
                inline_body = (inline_comment.get("body") or "").strip()
                path = inline_comment.get("path")
                position = inline_comment.get("position")
                location = ""
                if path:
                    location = f" ({path}"
                    if position is not None:
                        location += f":{position}"
                    location += ")"
                code_review_lines.append(f"{inline_author}{location}: {inline_body}")

        if review_lines:
            lines.append("")
            lines.append("Reviews:")
            lines.extend(review_lines)

        if code_review_lines:
            lines.append("")
            lines.append("Code Review Comments:")
            lines.extend(code_review_lines)

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


def chunk_commits(data):
    repo_name = get_repo_name(data)
    chunks = []

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
        message = "\n".join(line for line in message_lines if line is not None).strip()

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


def save_chunks(chunks, output_file=OUTPUT_FILE):
    output_dir = os.path.dirname(output_file)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=4, ensure_ascii=False)


def resolve_repo_path(data):
    repo_name = get_repo_name(data)
    return os.path.join(".", repo_name)


def main():
    data = load_graphql_data()

    issue_chunks = chunk_issues(data)
    pr_chunks = chunk_pull_requests(data)
    commit_chunks = chunk_commits(data)
    repo_path = resolve_repo_path(data)
    code_chunks = chunk_codebase(repo_path)

    all_chunks = []
    all_chunks.extend(issue_chunks)
    all_chunks.extend(pr_chunks)
    all_chunks.extend(commit_chunks)
    all_chunks.extend(code_chunks)

    save_chunks(all_chunks)

    print(f"Generated {len(issue_chunks)} issue chunks")
    print(f"Generated {len(pr_chunks)} pull request chunks")
    print(f"Generated {len(commit_chunks)} commit chunks")
    print(f"Generated {len(code_chunks)} code chunks")
    print(f"Saved {len(all_chunks)} total chunks to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
