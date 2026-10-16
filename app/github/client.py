import logging
from typing import Any, Dict, List, Literal, Optional
import httpx

logger = logging.getLogger("pr_code_sentinel.github")


class GitHubAPIError(Exception):
    """Custom exception raised when the GitHub API returns an error response."""

    def __init__(self, status_code: int, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(f"GitHub API Error [{status_code}]: {message}")
        self.status_code = status_code
        self.details = details or {}


class GitHubClient:
    """Asynchronous HTTP client for interacting with GitHub's Pull Request and Review APIs."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str):
        if not token:
            logger.warning("GitHubClient initialized without an API token. Authenticated requests will fail.")
        
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_pull_request_diff(self, owner: str, repo: str, pull_number: int) -> str:
        """
        Fetches the raw unified git diff of a pull request.
        
        Uses the custom vendor media type header `application/vnd.github.v3.diff`
        to retrieve plain text diffs rather than the default JSON metadata.
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}"
        diff_headers = self.headers.copy()
        diff_headers["Accept"] = "application/vnd.github.v3.diff"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=diff_headers)
            
            if response.status_code != 200:
                raise GitHubAPIError(
                    status_code=response.status_code,
                    message=f"Failed to fetch diff for PR #{pull_number}",
                    details=response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                )
            
            return response.text

    async def post_pr_review(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        commit_id: str,
        body_summary: str,
        event: Literal["APPROVE", "REQUEST_CHANGES", "COMMENT"] = "COMMENT",
        comments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Submits an atomic, batched Pull Request review including an overall verdict 
        and multiple inline file-line comments in a single network round-trip.

        Each item in `comments` must match the structure:
        {
            "path": "path/to/file.py",
            "line": 42,
            "body": "Comment text (supports markdown and ```suggestion blocks)"
        }
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/reviews"
        
        payload: Dict[str, Any] = {
            "commit_id": commit_id,
            "body": body_summary,
            "event": event,
            "comments": comments or [],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=self.headers)
            
            if response.status_code not in (200, 201):
                err_body = response.json() if "application/json" in response.headers.get("content-type", "") else {}
                
                # HTTP 422 Unprocessable Entity typically means a comment targeted an invalid diff line
                if response.status_code == 422:
                    logger.error(f"GitHub rejected review comments for PR #{pull_number}: {err_body}")
                
                raise GitHubAPIError(
                    status_code=response.status_code,
                    message=f"Failed to submit review for PR #{pull_number}: {err_body.get('message', response.text)}",
                    details=err_body
                )
            
            return response.json()

    async def post_issue_comment(self, owner: str, repo: str, pull_number: int, body: str) -> Dict[str, Any]:
        """
        Fallback helper: Posts a standard top-level comment on the PR conversation thread 
        without anchoring to specific code diff lines.
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{pull_number}/comments"
        payload = {"body": body}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=self.headers)
            
            if response.status_code not in (200, 201):
                raise GitHubAPIError(
                    status_code=response.status_code,
                    message=f"Failed to post comment to PR #{pull_number}",
                    details=response.json() if "application/json" in response.headers.get("content-type", "") else {}
                )
                
            return response.json()