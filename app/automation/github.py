"""Bounded, fail-closed GitHub API adapter for trusted workflow jobs."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping

from app.automation.issues import ExistingIssue, IssueAction, IssueInventory, IssuePlan

MAX_PAGES = 10
MAX_ITEMS = 1000
PAGE_SIZE = 100
_LINK = re.compile(r'^<([^>]+)>;\s*rel="([a-z]+)"$')


class GitHubAPIError(RuntimeError):
    """The API result is unavailable, incomplete, malformed, or unsafe."""


@dataclass(frozen=True)
class GitHubPage:
    data: Any
    headers: Mapping[str, str]


class GitHubClient:
    def __init__(self, repository: str, token: str, api_url: str = "https://api.github.com") -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or not token:
            raise GitHubAPIError("valid GitHub repository and token are required")
        self.repository = repository
        self.token = token
        self.api_url = api_url.rstrip("/")

    def request_page(self, method: str, path: str, payload: dict[str, Any] | None = None) -> GitHubPage:
        body = json.dumps(payload).encode() if payload is not None else None
        url = path if path.startswith("https://") else f"{self.api_url}{path}"
        if not url.startswith(f"{self.api_url}/"):
            raise GitHubAPIError("pagination URL left the configured GitHub API origin")
        request = urllib.request.Request(url, data=body, method=method, headers={
            "Accept": "application/vnd.github+json", "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "georisk-founder-automation",
        })
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                return GitHubPage(json.loads(raw) if raw else None, dict(response.headers.items()))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise GitHubAPIError(f"GitHub API request failed: {method} {path}") from exc

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        return self.request_page(method, path, payload).data

    def _next_link(self, header: str | None, current_url: str) -> str | None:
        if not header:
            return None
        relations: dict[str, str] = {}
        for raw in header.split(","):
            match = _LINK.fullmatch(raw.strip())
            if match is None or match.group(2) in relations:
                raise GitHubAPIError("malformed or duplicate GitHub Link relation")
            relations[match.group(2)] = match.group(1)
        nxt = relations.get("next")
        if nxt is None:
            return None
        parsed = urllib.parse.urlparse(nxt)
        current = urllib.parse.urlparse(current_url if current_url.startswith("http") else self.api_url + current_url)
        if (parsed.scheme, parsed.netloc) != (current.scheme, current.netloc):
            raise GitHubAPIError("pagination crossed GitHub API origin")
        return nxt

    def paginate(self, path: str, *, item_key: str | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        current = path
        for _ in range(MAX_PAGES):
            absolute = current if current.startswith("http") else self.api_url + current
            if absolute in seen:
                raise GitHubAPIError("repeated GitHub pagination URL")
            seen.add(absolute)
            page = self.request_page("GET", current)
            raw_items = page.data.get(item_key) if item_key and isinstance(page.data, dict) else page.data
            if not isinstance(raw_items, list) or any(not isinstance(item, dict) for item in raw_items):
                raise GitHubAPIError("malformed paginated GitHub response")
            items.extend(raw_items)
            if len(items) > MAX_ITEMS:
                raise GitHubAPIError("GitHub pagination exceeded maximum item bound")
            nxt = self._next_link(page.headers.get("Link") or page.headers.get("link"), absolute)
            if nxt is None:
                return items
            current = nxt
        raise GitHubAPIError("GitHub pagination exceeded maximum page bound")

    def list_issues(self) -> IssueInventory:
        payload = self.paginate(f"/repos/{self.repository}/issues?state=all&per_page={PAGE_SIZE}")
        issues = []
        for item in payload:
            if "pull_request" in item:
                continue
            user = item.get("user") or {}
            labels = item.get("labels")
            if not isinstance(user.get("login"), str) or not isinstance(labels, list):
                raise GitHubAPIError("issue author or label provenance is unavailable")
            issues.append(ExistingIssue(
                number=item["number"], title=item["title"], body=item.get("body") or "",
                state=item["state"], repository=self.repository, author_login=user["login"],
                labels=[label["name"] for label in labels if isinstance(label, dict) and isinstance(label.get("name"), str)],
            ))
        return IssueInventory(repository=self.repository, complete=True, issues=issues)

    def list_check_runs(self, sha: str) -> list[dict[str, Any]]:
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise GitHubAPIError("exact lowercase commit SHA is required")
        return self.paginate(
            f"/repos/{self.repository}/commits/{sha}/check-runs?per_page={PAGE_SIZE}",
            item_key="check_runs",
        )

    def apply_issue_plan(self, plan: IssuePlan) -> None:
        if plan.action == IssueAction.NOOP:
            return
        if plan.action == IssueAction.CREATE:
            self.request("POST", f"/repos/{self.repository}/issues", {"title": plan.title, "body": plan.body, "labels": plan.labels})
            return
        if plan.issue_number is None:
            raise GitHubAPIError("issue update requires an issue number")
        payload: dict[str, Any] = {"title": plan.title, "body": plan.body, "labels": plan.labels, "state": "open"}
        if plan.action == IssueAction.CLOSE:
            payload["state"] = "closed"
        self.request("PATCH", f"/repos/{self.repository}/issues/{plan.issue_number}", payload)
