import os
import json
import stat
import shutil
from pathlib import Path

import git
import requests

from backend.config import config


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


class GitHubRepositoryClient:
    graphql_url = "https://api.github.com/graphql"
    rest_url = "https://api.github.com"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
            }
        )
        if config.GITHUB_TOKEN:
            self.session.headers["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"

        self.public_session = requests.Session()
        self.public_session.headers.update({"Accept": "application/vnd.github+json"})

    def parse_repository_input(self, repo_input: str) -> tuple[str, str, str]:
        cleaned = repo_input.strip().rstrip("/")
        if cleaned.endswith(".git"):
            cleaned = cleaned[:-4]

        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            parts = cleaned.split("/")
            if len(parts) < 2:
                raise ValueError(f"Invalid repository URL: {repo_input}")
            owner, repo = parts[-2], parts[-1]
            return owner, repo, cleaned

        if "/" not in cleaned:
            raise ValueError("Repository must be a full GitHub URL or owner/repo.")

        owner, repo = cleaned.split("/", 1)
        return owner, repo, f"https://github.com/{owner}/{repo}"

    def graphql(self, query: str, variables: dict | None = None) -> dict:
        response = self.session.post(
            self.graphql_url,
            json={"query": query, "variables": variables or {}},
            timeout=(5, 60),
        )
        if response.status_code == 401:
            raise PermissionError("GitHub GraphQL authorization failed.")
        response.raise_for_status()
        payload = response.json()

        if "errors" in payload and payload.get("data") is None:
            raise RuntimeError(json.dumps(payload["errors"], ensure_ascii=False))

        return payload

    def fetch_all(self, query: str, owner: str, repo: str, path: str) -> list[dict]:
        items: list[dict] = []
        cursor = None

        while True:
            payload = self.graphql(
                query,
                {"owner": owner, "repo": repo, "cursor": cursor},
            )
            page = payload["data"]["repository"][path]
            items.extend(page["nodes"])
            if not page["pageInfo"]["hasNextPage"]:
                break
            cursor = page["pageInfo"]["endCursor"]

        return items

    def get_repo_metadata(self, owner: str, repo: str) -> dict:
        try:
            return self.graphql(REPO_METADATA_QUERY, {"owner": owner, "repo": repo})[
                "data"
            ]["repository"]
        except Exception:
            return self.get_repo_metadata_rest(owner, repo)

    def get_all_issues(self, owner: str, repo: str) -> list[dict]:
        try:
            return self.fetch_all(ISSUES_QUERY, owner, repo, "issues")
        except Exception:
            return self.get_all_issues_rest(owner, repo)

    def get_all_pull_requests(self, owner: str, repo: str) -> list[dict]:
        try:
            return self.fetch_all(PULL_REQUESTS_QUERY, owner, repo, "pullRequests")
        except Exception:
            return self.get_all_pull_requests_rest(owner, repo)

    def get_all_releases(self, owner: str, repo: str) -> list[dict]:
        try:
            return self.fetch_all(RELEASES_QUERY, owner, repo, "releases")
        except Exception:
            return self.get_all_releases_rest(owner, repo)

    def get_all_discussions(self, owner: str, repo: str) -> list[dict]:
        discussions: list[dict] = []
        cursor = None

        while True:
            try:
                payload = self.graphql(
                    DISCUSSIONS_QUERY,
                    {"owner": owner, "repo": repo, "cursor": cursor},
                )
                page = payload["data"]["repository"]["discussions"]
            except Exception:
                return discussions

            discussions.extend(page["nodes"])
            if not page["pageInfo"]["hasNextPage"]:
                break
            cursor = page["pageInfo"]["endCursor"]

        return discussions

    def get_all_commits(self, owner: str, repo: str) -> list[dict]:
        try:
            commits: list[dict] = []
            cursor = None

            while True:
                payload = self.graphql(
                    COMMITS_QUERY,
                    {"owner": owner, "repo": repo, "cursor": cursor},
                )
                repo_data = payload["data"]["repository"]
                default_branch = repo_data.get("defaultBranchRef")
                if not default_branch or not default_branch.get("target"):
                    return commits

                history = default_branch["target"]["history"]
                commits.extend(history["nodes"])
                if not history["pageInfo"]["hasNextPage"]:
                    break
                cursor = history["pageInfo"]["endCursor"]

            return commits
        except Exception:
            return self.get_all_commits_rest(owner, repo)

    def rest_get(self, path: str, params: dict | None = None) -> requests.Response:
        response = self.public_session.get(
            f"{self.rest_url}{path}",
            params=params,
            timeout=(5, 60),
        )
        response.raise_for_status()
        return response

    def paginate_rest(self, path: str, params: dict | None = None, max_pages: int = 10) -> list[dict]:
        if getattr(self, "_rate_limited", False):
            return []
        items: list[dict] = []
        page = 1
        base_params = dict(params or {})
        while page <= max_pages:
            current_params = {**base_params, "per_page": 100, "page": page}
            try:
                response = self.rest_get(path, current_params)
            except requests.exceptions.HTTPError as exc:
                if exc.response is not None:
                    if exc.response.status_code == 422:
                        break
                    if exc.response.status_code == 403:
                        self._rate_limited = True
                        break
                raise
            payload = response.json()
            if not payload:
                break
            items.extend(payload)
            if len(payload) < 100:
                break
            page += 1
        return items

    def get_repo_metadata_rest(self, owner: str, repo: str) -> dict:
        payload = self.rest_get(f"/repos/{owner}/{repo}").json()
        return {
            "name": payload.get("name"),
            "description": payload.get("description"),
            "createdAt": payload.get("created_at"),
            "updatedAt": payload.get("updated_at"),
            "stargazerCount": payload.get("stargazers_count", 0),
            "forkCount": payload.get("forks_count", 0),
            "url": payload.get("html_url"),
            "primaryLanguage": {"name": payload.get("language")} if payload.get("language") else None,
            "licenseInfo": {"name": (payload.get("license") or {}).get("name")} if payload.get("license") else None,
            "defaultBranchRef": {"name": payload.get("default_branch")} if payload.get("default_branch") else None,
            "isArchived": payload.get("archived", False),
            "isFork": payload.get("fork", False),
        }

    def get_all_issues_rest(self, owner: str, repo: str) -> list[dict]:
        items = self.paginate_rest(f"/repos/{owner}/{repo}/issues", {"state": "all"})
        issues = []
        for item in items:
            if "pull_request" in item:
                continue
            comments = self.fetch_issue_comments_rest(owner, repo, item.get("number"))
            issues.append(
                {
                    "number": item.get("number"),
                    "title": item.get("title"),
                    "body": item.get("body"),
                    "state": item.get("state"),
                    "createdAt": item.get("created_at"),
                    "updatedAt": item.get("updated_at"),
                    "closedAt": item.get("closed_at"),
                    "author": {"login": (item.get("user") or {}).get("login")},
                    "labels": {"nodes": [{"name": label.get("name")} for label in item.get("labels", [])]},
                    "comments": {"nodes": comments},
                }
            )
        return issues

    def fetch_issue_comments_rest(self, owner: str, repo: str, issue_number: int | None) -> list[dict]:
        if not issue_number:
            return []
        items = self.paginate_rest(f"/repos/{owner}/{repo}/issues/{issue_number}/comments")
        return [
            {
                "body": item.get("body"),
                "createdAt": item.get("created_at"),
                "author": {"login": (item.get("user") or {}).get("login")},
            }
            for item in items[:50]
        ]

    def get_all_pull_requests_rest(self, owner: str, repo: str) -> list[dict]:
        items = self.paginate_rest(f"/repos/{owner}/{repo}/pulls", {"state": "all"})
        pull_requests = []
        for item in items:
            comments = self.fetch_pull_request_comments_rest(owner, repo, item.get("number"))
            reviews = self.fetch_pull_request_reviews_rest(owner, repo, item.get("number"))
            pull_requests.append(
                {
                    "number": item.get("number"),
                    "title": item.get("title"),
                    "body": item.get("body"),
                    "state": item.get("state"),
                    "createdAt": item.get("created_at"),
                    "mergedAt": item.get("merged_at"),
                    "closedAt": item.get("closed_at"),
                    "additions": item.get("additions"),
                    "deletions": item.get("deletions"),
                    "changedFiles": item.get("changed_files"),
                    "author": {"login": (item.get("user") or {}).get("login")},
                    "comments": {"nodes": comments},
                    "reviews": {"nodes": reviews},
                }
            )
        return pull_requests

    def fetch_pull_request_comments_rest(self, owner: str, repo: str, pr_number: int | None) -> list[dict]:
        if not pr_number:
            return []
        items = self.paginate_rest(f"/repos/{owner}/{repo}/issues/{pr_number}/comments")
        return [
            {
                "body": item.get("body"),
                "createdAt": item.get("created_at"),
                "author": {"login": (item.get("user") or {}).get("login")},
            }
            for item in items[:50]
        ]

    def fetch_pull_request_reviews_rest(self, owner: str, repo: str, pr_number: int | None) -> list[dict]:
        if not pr_number:
            return []
        items = self.paginate_rest(f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews")
        reviews = []
        for item in items[:50]:
            reviews.append(
                {
                    "body": item.get("body"),
                    "state": item.get("state"),
                    "author": {"login": (item.get("user") or {}).get("login")},
                    "comments": {"nodes": []},
                }
            )
        return reviews

    def get_all_releases_rest(self, owner: str, repo: str) -> list[dict]:
        items = self.paginate_rest(f"/repos/{owner}/{repo}/releases")
        return [
            {
                "name": item.get("name"),
                "tagName": item.get("tag_name"),
                "description": item.get("body"),
                "createdAt": item.get("created_at"),
                "author": {"login": (item.get("author") or {}).get("login")},
            }
            for item in items
        ]

    def get_all_commits_rest(self, owner: str, repo: str) -> list[dict]:
        items = self.paginate_rest(f"/repos/{owner}/{repo}/commits")
        commits = []
        for item in items:
            commit = item.get("commit") or {}
            author = commit.get("author") or {}
            commits.append(
                {
                    "oid": item.get("sha"),
                    "abbreviatedOid": (item.get("sha") or "")[:7],
                    "message": commit.get("message"),
                    "messageHeadline": (commit.get("message") or "").splitlines()[0] if commit.get("message") else "",
                    "messageBody": "\n".join((commit.get("message") or "").splitlines()[1:]).strip(),
                    "authoredDate": author.get("date"),
                    "committedDate": author.get("date"),
                    "author": {
                        "name": author.get("name"),
                        "email": author.get("email"),
                        "date": author.get("date"),
                        "user": {"login": (item.get("author") or {}).get("login"), "name": author.get("name")},
                    },
                    "committer": {
                        "name": (commit.get("committer") or {}).get("name"),
                        "email": (commit.get("committer") or {}).get("email"),
                        "date": (commit.get("committer") or {}).get("date"),
                        "user": {
                            "login": (item.get("committer") or {}).get("login"),
                            "name": (commit.get("committer") or {}).get("name"),
                        },
                    },
                    "additions": None,
                    "deletions": None,
                    "changedFiles": None,
                    "commitUrl": item.get("html_url"),
                    "url": item.get("html_url"),
                    "parents": {"nodes": [{"oid": parent.get("sha"), "abbreviatedOid": (parent.get("sha") or "")[:7]} for parent in item.get("parents", [])]},
                    "tree": {"oid": None},
                    "status": None,
                    "statusCheckRollup": None,
                    "signature": None,
                    "associatedPullRequests": {"nodes": []},
                    "comments": {"nodes": []},
                }
            )
        return commits

    def clone_repo(self, repo_url: str, repo_path: Path) -> None:
        repo_path = repo_path.resolve()
        allowed_root = config.REPOSITORIES_DIR.resolve()
        if allowed_root not in repo_path.parents:
            raise ValueError("Clone path must stay within the repositories workspace.")

        if repo_path.exists():
            shutil.rmtree(repo_path, onerror=self._handle_remove_readonly)

        repo_path.parent.mkdir(parents=True, exist_ok=True)
        git.Repo.clone_from(repo_url, repo_path)

    @staticmethod
    def _handle_remove_readonly(func, path, exc_info):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    def build_minimal_metadata(self, owner: str, repo: str, repo_url: str, clone_path: Path) -> dict:
        default_branch = None
        try:
            local_repo = git.Repo(clone_path)
            default_branch = local_repo.active_branch.name
        except Exception:
            default_branch = None

        return {
            "name": repo,
            "description": None,
            "createdAt": None,
            "updatedAt": None,
            "stargazerCount": 0,
            "forkCount": 0,
            "url": repo_url,
            "primaryLanguage": None,
            "licenseInfo": None,
            "defaultBranchRef": {"name": default_branch} if default_branch else None,
            "isArchived": False,
            "isFork": False,
        }

    def get_local_commits(self, clone_path: Path) -> list[dict]:
        repo = git.Repo(clone_path)
        commits = []
        for commit in repo.iter_commits():
            message = commit.message.strip()
            lines = message.splitlines()
            headline = lines[0] if lines else commit.hexsha
            body = "\n".join(lines[1:]).strip()
            commits.append(
                {
                    "oid": commit.hexsha,
                    "abbreviatedOid": commit.hexsha[:7],
                    "message": message,
                    "messageHeadline": headline,
                    "messageBody": body,
                    "authoredDate": commit.authored_datetime.isoformat() if commit.authored_datetime else None,
                    "committedDate": commit.committed_datetime.isoformat() if commit.committed_datetime else None,
                    "author": {
                        "name": str(commit.author),
                        "email": commit.author.email,
                        "date": commit.authored_datetime.isoformat() if commit.authored_datetime else None,
                        "user": {"login": None, "name": str(commit.author)},
                    },
                    "committer": {
                        "name": str(commit.committer),
                        "email": commit.committer.email,
                        "date": commit.committed_datetime.isoformat() if commit.committed_datetime else None,
                        "user": {"login": None, "name": str(commit.committer)},
                    },
                    "additions": None,
                    "deletions": None,
                    "changedFiles": None,
                    "commitUrl": None,
                    "url": None,
                    "parents": {
                        "nodes": [
                            {"oid": parent.hexsha, "abbreviatedOid": parent.hexsha[:7]}
                            for parent in commit.parents
                        ]
                    },
                    "tree": {"oid": commit.tree.hexsha if commit.tree else None},
                    "status": None,
                    "statusCheckRollup": None,
                    "signature": None,
                    "associatedPullRequests": {"nodes": []},
                    "comments": {"nodes": []},
                }
            )
        return commits
