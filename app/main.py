import os
import hmac
import hashlib
from pathlib import Path
from dotenv import load_dotenv

# Explicitly find and load .env from the project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

from fastapi import FastAPI, Request, Header, HTTPException, BackgroundTasks, status
from pydantic_settings import BaseSettings

from app.analyzer.diff_parser import GitDiffParser
from app.analyzer.ast_analyzer import StaticASTAnalyzer
from app.ai.reviewer import AIReviewService
from app.github.client import GitHubClient


class Settings(BaseSettings):
    github_webhook_secret: str = os.getenv("GITHUB_WEBHOOK_SECRET", "test_secret")
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")


settings = Settings()

if not settings.gemini_api_key:
    raise ValueError(f"GEMINI_API_KEY could not be found in {BASE_DIR / '.env'}. Check the file name and variable name.")

app = FastAPI(title="PR Code Sentinel", version="1.0.0")

diff_parser = GitDiffParser()
ast_analyzer = StaticASTAnalyzer(max_complexity=10)
ai_reviewer = AIReviewService(api_key=settings.gemini_api_key)
github_client = GitHubClient(token=settings.github_token)


def verify_github_signature(payload: bytes, signature_header: str | None) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    mac = hmac.new(settings.github_webhook_secret.encode(), payload, hashlib.sha256)
    expected = f"sha256={mac.hexdigest()}"
    return hmac.compare_digest(expected, signature_header)


async def execute_pr_review_pipeline(
    owner: str, repo: str, pull_number: int, head_sha: str
):
    # 1. Fetch raw diff
    raw_diff = await github_client.get_pull_request_diff(owner, repo, pull_number)

    # 2. Parse diff & identify modified files and valid line numbers
    parsed_files = diff_parser.parse_patch(raw_diff)
    all_github_comments = []
    summaries = []

    for filename, file_diff in parsed_files.items():
        # Filter for Python files for Tier-1 AST check
        if not filename.endswith(".py"):
            continue

        # Combine added lines for AST analysis
        reconstructed_code = "\n".join(file_diff.added_lines.values())

        # Tier-1: AST & Cyclomatic Complexity
        violations = [v.to_dict() for v in ast_analyzer.analyze_source(reconstructed_code)]

        # Tier-2: Structured LLM Review
        review_result = ai_reviewer.review_code_diff(
            filename=filename,
            diff_code=raw_diff,
            ast_violations=violations,
            valid_lines=file_diff.valid_lines,
        )

        summaries.append(f"**{filename}**: {review_result.summary}")

        # Map findings to GitHub API format
        for comment in review_result.comments:
            if comment.line_number in file_diff.valid_lines:
                body_text = (
                    f"**[{comment.category}] ({comment.severity})**\n\n"
                    f"{comment.issue_description}\n\n"
                    f"```suggestion\n{comment.suggested_code}\n```"
                )
                all_github_comments.append({
                    "path": comment.file_path,
                    "line": comment.line_number,
                    "body": body_text,
                })

    # 3. Post batch review back to GitHub
    verdict = "REQUEST_CHANGES" if any("CRITICAL" in c["body"] for c in all_github_comments) else "COMMENT"
    final_body = "### 🛡️ Automated Code Quality & Security Audit\n\n" + "\n\n".join(summaries)

    if all_github_comments:
        await github_client.post_pr_review(
            owner=owner,
            repo=repo,
            pull_number=pull_number,
            commit_id=head_sha,
            body_summary=final_body,
            event=verdict,
            comments=all_github_comments,
        )


@app.post("/webhook/github")
async def github_webhook_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
):
    body = await request.body()
    if not verify_github_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid HMAC signature")

    if x_github_event != "pull_request":
        return {"status": "skipped", "message": f"Ignoring event '{x_github_event}'"}

    payload = await request.json()
    action = payload.get("action")
    if action not in ["opened", "synchronize"]:
        return {"status": "skipped", "message": f"Ignoring action '{action}'"}

    owner = payload["repository"]["owner"]["login"]
    repo = payload["repository"]["name"]
    pull_number = payload["pull_request"]["number"]
    head_sha = payload["pull_request"]["head"]["sha"]

    # Offload review to background worker to respond to GitHub webhook within 10s timeout
    background_tasks.add_task(execute_pr_review_pipeline, owner, repo, pull_number, head_sha)

    return {"status": "accepted", "pull_number": pull_number}