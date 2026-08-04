import os
import sys
import json
import re
import requests
import git
from dotenv import load_dotenv

# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

GITHUB_TOKEN = os.getenv("GIT_TOKEN") or os.getenv("GIT_KEY")
GRAPHQL_URL = "https://api.github.com/graphql"

# Skip binary/media files when dumping source code
SKIP_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".pdf",
    ".zip",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".mp4",
    ".mp3",
    ".wav",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".bin",
    ".dat",
    ".db",
    ".sqlite",
    ".sqlite3",
}

OUTPUT_FILE = "repo_dump.txt"
JSON_OUTPUT = "graphql_data.json"

# ============================================================
# SETUP: Authenticated Session
# ============================================================

github = requests.Session()
github.headers.update(
    {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }
)

# ============================================================
# GRAPHQL QUERIES
# ============================================================

REPO_METADATA_QUERY = """
query($owner: String!, $repo: String!) {
  repository(owner: $owner, name: $repo) {
    name
    description
    createdAt
    updatedAt
    stargazerCount
    forkCount
    url
    primaryLanguage { name }
    licenseInfo { name }
    defaultBranchRef { name }
    isArchived
    isFork
  }
}
"""

ISSUES_QUERY = """
query($owner: String!, $repo: String!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    issues(first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title body state
        createdAt updatedAt closedAt
        author { login }
        labels(first: 20) { nodes { name } }
        comments(first: 50) {
          nodes { body createdAt author { login } }
        }
      }
    }
  }
}
"""

PULL_REQUESTS_QUERY = """
query($owner: String!, $repo: String!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequests(first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title body state
        createdAt mergedAt closedAt
        additions deletions changedFiles
        author { login }
        comments(first: 50) {
          nodes { body createdAt author { login } }
        }
        reviews(first: 50) {
          nodes {
            body state author { login }
            comments(first: 50) {
              nodes { body path position author { login } }
            }
          }
        }
      }
    }
  }
}
"""

DISCUSSIONS_QUERY = """
query($owner: String!, $repo: String!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    discussions(first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        title body createdAt
        author { login }
        comments(first: 50) {
          nodes { body author { login } }
        }
      }
    }
  }
}
"""

RELEASES_QUERY = """
query($owner: String!, $repo: String!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    releases(first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name tagName description createdAt
        author { login }
      }
    }
  }
}
"""

COMMITS_QUERY = """
query($owner: String!, $repo: String!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 100, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              oid
              abbreviatedOid
              message
              messageHeadline
              messageBody
              authoredDate
              committedDate
              author {
                name
                email
                date
                user { login name }
              }
              committer {
                name
                email
                date
                user { login name }
              }
              additions
              deletions
              changedFiles
              commitUrl
              url
              parents(first: 10) {
                nodes { oid abbreviatedOid }
              }
              tree { oid }
              status {
                state
                contexts {
                  context
                  state
                  targetUrl
                  createdAt
                  creator { login }
                }
              }
              statusCheckRollup {
                state
                contexts(first: 50) {
                  nodes {
                    ... on CheckRun {
                      name
                      conclusion
                      status
                      startedAt
                      completedAt
                      detailsUrl
                      checkSuite { app { name } }
                    }
                    ... on StatusContext {
                      context
                      state
                      targetUrl
                      createdAt
                      creator { login }
                    }
                  }
                }
              }
              signature {
                ... on GpgSignature {
                  __typename
                  signature
                  signer { login name }
                  state
                  email
                  isValid
                  keyId
                  payload
                  wasSignedByGitHub
                }
                ... on SmimeSignature {
                  __typename
                  signature
                  signer { login name }
                  state
                  email
                  isValid
                  payload
                  wasSignedByGitHub
                }
                ... on UnknownSignature {
                  __typename
                  signature
                  state
                  email
                  isValid
                  payload
                }
              }
              associatedPullRequests(first: 10) {
                nodes {
                  number
                  title
                  url
                  state
                  author { login }
                }
              }
              comments(first: 50) {
                pageInfo { hasNextPage endCursor }
                nodes {
                  body
                  createdAt
                  updatedAt
                  author { login }
                  path
                  position
                  commit { oid }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

RATE_LIMIT_QUERY = """
query { rateLimit { limit remaining cost resetAt } }
"""


# ============================================================
# GRAPHQL HELPER
# ============================================================


def graphql(query, variables=None):
    response = github.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables or {}},
        timeout=(5, 60),
    )
    response.raise_for_status()
    data = response.json()

    if "errors" in data:
        if data.get("data") is None:
            raise Exception(data["errors"])
        else:
            print("⚠️  GraphQL partial errors (returning available data):")
            for err in data["errors"]:
                print(f"   - {err.get('message', err)}")

    return data


# ============================================================
# PAGINATED FETCHERS
# ============================================================


def fetch_all(query, owner, repo, path):
    """Generic paginated GraphQL fetcher."""
    all_items = []
    cursor = None

    while True:
        data = graphql(query, {"owner": owner, "repo": repo, "cursor": cursor})
        items = data["data"]["repository"][path]
        all_items.extend(items["nodes"])

        if not items["pageInfo"]["hasNextPage"]:
            break
        cursor = items["pageInfo"]["endCursor"]

    return all_items


def get_repo_metadata(owner, repo):
    return graphql(REPO_METADATA_QUERY, {"owner": owner, "repo": repo})["data"][
        "repository"
    ]


def get_rate_limit():
    return graphql(RATE_LIMIT_QUERY)["data"]["rateLimit"]


def get_all_issues(owner, repo):
    return fetch_all(ISSUES_QUERY, owner, repo, "issues")


def get_all_pull_requests(owner, repo):
    return fetch_all(PULL_REQUESTS_QUERY, owner, repo, "pullRequests")


def get_all_releases(owner, repo):
    return fetch_all(RELEASES_QUERY, owner, repo, "releases")


def get_all_discussions(owner, repo):
    all_discussions = []
    cursor = None

    while True:
        try:
            data = graphql(
                DISCUSSIONS_QUERY, {"owner": owner, "repo": repo, "cursor": cursor}
            )
            discussions = data["data"]["repository"]["discussions"]
            all_discussions.extend(discussions["nodes"])

            if not discussions["pageInfo"]["hasNextPage"]:
                break
            cursor = discussions["pageInfo"]["endCursor"]

        except Exception as e:
            msg = str(e).lower()
            if any(
                ind in msg
                for ind in [
                    "discussions are disabled",
                    "discussions not enabled",
                    "discussions disabled",
                    "feature not enabled",
                ]
            ):
                print("ℹ️  Discussions are disabled for this repository — skipping.")
                break
            else:
                print(f"❌ Unexpected error fetching discussions: {e}")
                raise

    return all_discussions


def get_all_commits(owner, repo):
    """Fetch all commits from the default branch with full GraphQL details."""
    all_commits = []
    cursor = None

    while True:
        data = graphql(COMMITS_QUERY, {"owner": owner, "repo": repo, "cursor": cursor})
        repo_data = data["data"]["repository"]

        if not repo_data.get("defaultBranchRef"):
            print("ℹ️  No default branch found — skipping commit fetch.")
            break

        target = repo_data["defaultBranchRef"]["target"]
        if not target:
            print("ℹ️  Default branch has no commits — skipping.")
            break

        history = target["history"]
        all_commits.extend(history["nodes"])

        if not history["pageInfo"]["hasNextPage"]:
            break
        cursor = history["pageInfo"]["endCursor"]

    return all_commits


# ============================================================
# LOCAL GIT REPOSITORY OPERATIONS
# ============================================================


def clone_repo(repo_url, repo_path):
    """Clone or re-clone repository."""
    if os.path.exists(repo_path):
        print(f"Clearing existing repo at {repo_path}...")
        if os.name == "nt":  # Windows
            os.system(f'rmdir /S /Q "{repo_path}"')
        else:  # Unix/Linux/Mac
            os.system(f'rm -rf "{repo_path}"')

    print(f"Cloning {repo_url}...")
    repo = git.Repo.clone_from(repo_url, repo_path)
    print("Cloned successfully.")
    return repo


def get_commit_info(commit):
    """Serialize a commit object to dict."""
    return {
        "hash": commit.hexsha,
        "author": str(commit.author),
        "email": commit.author.email,
        "date": commit.committed_datetime.isoformat(),
        "message": commit.message.strip(),
        "parents": [p.hexsha for p in commit.parents],
    }


def dump_repo_contents(tree, output_file, skip_extensions):
    """Recursively dump source code files to text output."""
    for item in tree:
        if item.type == "blob":
            _, ext = os.path.splitext(item.path)
            if ext.lower() in skip_extensions:
                continue

            with open(output_file, "a", encoding="utf-8") as f:
                f.write("=" * 100 + "\n")
                f.write(f"FILE: {item.path}\n")
                f.write("=" * 100 + "\n")

                try:
                    content = item.data_stream.read().decode("utf-8", errors="ignore")
                    f.write(content + "\n\n")
                except Exception as e:
                    f.write(f"ERROR READING FILE: {e}\n\n")

        elif item.type == "tree":
            dump_repo_contents(item, output_file, skip_extensions)


def print_file_tree(tree, level=0):
    """Print pretty file tree to console."""
    for entry in tree:
        indent = "    " * level
        if entry.type == "tree":
            print(f"{indent}📁 {entry.name}/")
            print_file_tree(entry, level + 1)
        elif entry.type == "blob":
            print(f"{indent}📄 {entry.name}")


# ============================================================
# URL PARSER
# ============================================================


def parse_github_url(url):
    """Extract owner/repo from GitHub URL."""
    url = url.rstrip("/")
    parts = url.split("/")
    if len(parts) < 2:
        raise ValueError(f"Invalid URL format: {url}")
    return parts[-2], parts[-1]


# ============================================================
# MAIN EXECUTION
# ============================================================


def main():
    # --- Input ---
    repo_input = input("Enter GitHub repo URL (or owner/repo): ").strip()

    if "/" in repo_input and not repo_input.startswith("http"):
        owner, repo = repo_input.split("/", 1)
        repo_url = f"https://github.com/{owner}/{repo}"
    else:
        owner, repo = parse_github_url(repo_input)
        repo_url = repo_input.rstrip("/")

    # Local path for cloning (use current dir + repo name)
    repo_path = os.path.join(os.getcwd(), repo)

    # --- Cleanup output files ---
    for f in [OUTPUT_FILE, JSON_OUTPUT]:
        if os.path.exists(f):
            os.remove(f)
            print(f"Deleted existing {f}")

    # ==========================================================
    # PHASE 1: GraphQL Data (GitHub API)
    # ==========================================================
    print("\n" + "=" * 60)
    print("FETCHING GITHUB GRAPHQL DATA")
    print("=" * 60)

    rate_limit_before = get_rate_limit()

    metadata = get_repo_metadata(owner, repo)
    license_name = metadata["licenseInfo"]["name"] if metadata["licenseInfo"] else None

    issues = get_all_issues(owner, repo)
    pull_requests = get_all_pull_requests(owner, repo)
    discussions = get_all_discussions(owner, repo)
    releases = get_all_releases(owner, repo)
    commits = get_all_commits(owner, repo)

    rate_limit_after = get_rate_limit()
    actual_cost = rate_limit_before["remaining"] - rate_limit_after["remaining"]

    # Save JSON data
    repo_data = {
        "metadata": metadata,
        "license_name": license_name,
        "issues": issues,
        "pull_requests": pull_requests,
        "discussions": discussions,
        "releases": releases,
        "commits": commits,
    }

    with open(JSON_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(repo_data, f, indent=4, ensure_ascii=False)

    # ==========================================================
    # PHASE 2: Local Git Data (Clone + History + Source Dump)
    # ==========================================================
    print("\n" + "=" * 60)
    print("CLONING & ANALYZING LOCAL REPOSITORY")
    print("=" * 60)

    local_repo = clone_repo(repo_url, repo_path)
    head_commit = local_repo.head.commit
    all_commits = list(local_repo.iter_commits(all=True))

    # --- Print latest commit ---
    print("\n--- LATEST COMMIT ---")
    print(f"Hash    : {head_commit.hexsha}")
    print(f"Author  : {head_commit.author}")
    print(f"Date    : {head_commit.committed_datetime}")
    print(f"Message : {head_commit.message.strip()}")

    # --- Print last 10 commits ---
    print("\n--- LAST 10 COMMITS ---")
    for commit in list(local_repo.iter_commits(all=True, max_count=10)):
        print(
            f"\n  {commit.hexsha[:8]} | {commit.author} | {commit.message.strip()[:60]}"
        )

    # --- Print file tree ---
    print("\n--- REPOSITORY FILE TREE ---")
    print_file_tree(head_commit.tree)

    # --- Root tree hash ---
    print(f"\n--- ROOT TREE HASH ---\n{head_commit.tree.hexsha}")

    # --- All commits summary ---
    print(f"\n--- ALL COMMITS ---\nTotal commits: {len(all_commits)}")

    # --- Files changed since first commit ---
    if len(all_commits) > 1:
        first_commit = all_commits[-1]
        diffs = head_commit.diff(first_commit)
        print(f"\n--- FILES CHANGED SINCE FIRST COMMIT ---")
        for diff in diffs:
            print(f"  {diff.a_path}")

    # --- Dump source code to text file ---
    print(f"\n--- DUMPING SOURCE CODE TO {OUTPUT_FILE} ---")
    dump_repo_contents(head_commit.tree, OUTPUT_FILE, SKIP_EXTENSIONS)

    # ==========================================================
    # PHASE 3: Summary Output
    # ==========================================================
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    print(f"Repository   : {metadata['name']}")
    print(f"Description  : {metadata.get('description', 'N/A')}")
    print(f"URL          : {metadata['url']}")
    print(f"Archived     : {metadata['isArchived']}")
    print(f"Fork         : {metadata['isFork']}")
    print(f"License      : {license_name or 'N/A'}")
    print(f"Stars        : {metadata['stargazerCount']}")
    print(f"Forks        : {metadata['forkCount']}")
    print(
        f"Language     : {metadata['primaryLanguage']['name'] if metadata['primaryLanguage'] else 'N/A'}"
    )

    print(f"\nIssues       : {len(issues)}")
    print(f"Pull Requests: {len(pull_requests)}")
    print(f"Discussions  : {len(discussions)}")
    print(f"Releases     : {len(releases)}")
    print(f"Commits (API): {len(commits)}")
    print(f"Commits (Git): {len(all_commits)}")

    if commits:
        latest_graphql_commit = commits[0]
        print(f"\nLatest Commit (GraphQL):")
        print(f"  OID       : {latest_graphql_commit.get('oid', 'N/A')}")
        print(
            f"  Headline  : {latest_graphql_commit.get('messageHeadline', 'N/A')[:70]}"
        )
        print(
            f"  Author    : {latest_graphql_commit.get('author', {}).get('name', 'N/A')} "
            f"({latest_graphql_commit.get('author', {}).get('user', {}).get('login', 'N/A')})"
        )
        print(f"  Authored  : {latest_graphql_commit.get('authoredDate', 'N/A')}")
        print(f"  Committed : {latest_graphql_commit.get('committedDate', 'N/A')}")
        print(f"  Additions : {latest_graphql_commit.get('additions', 'N/A')}")
        print(f"  Deletions : {latest_graphql_commit.get('deletions', 'N/A')}")
        print(f"  Files     : {latest_graphql_commit.get('changedFiles', 'N/A')}")
        parents = latest_graphql_commit.get("parents", {}).get("nodes", [])
        print(f"  Parents   : {len(parents)}")
        sig = latest_graphql_commit.get("signature")
        if sig:
            print(
                f"  Signature : {sig.get('__typename', 'N/A')} | State: {sig.get('state', 'N/A')}"
            )
        prs = latest_graphql_commit.get("associatedPullRequests", {}).get("nodes", [])
        if prs:
            print(f"  Linked PRs: {', '.join(str(p['number']) for p in prs)}")
        cmt_comments = latest_graphql_commit.get("comments", {}).get("nodes", [])
        if cmt_comments:
            print(f"  Comments  : {len(cmt_comments)}")

    print(
        f"\nRate Before  : {rate_limit_before['remaining']} / {rate_limit_before['limit']}"
    )
    print(
        f"Rate After   : {rate_limit_after['remaining']} / {rate_limit_after['limit']}"
    )
    print(f"Actual Cost  : {actual_cost}")
    print(f"Reset At     : {rate_limit_after['resetAt']}")

    print(f"\nOutput Files :")
    print(f"  - {JSON_OUTPUT} (GitHub API data)")
    print(f"  - {OUTPUT_FILE} (Source code dump)")
    print(f"  - {repo_path}/ (Cloned repository)")


if __name__ == "__main__":
    main()
