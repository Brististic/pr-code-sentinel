"""End-to-end pipeline tests with the GitHub API and Gemini mocked out."""
import asyncio
import os

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")

from unittest.mock import AsyncMock, Mock, patch

from app.ai.schemas import CodeReviewResult, InlineReviewComment
import app.main as main_module
from app.analyzer.diff_parser import GitDiffParser
from app.main import execute_pr_review_pipeline

DIFF = """--- a/service.py
+++ b/service.py
@@ -1,3 +1,4 @@
 def process(orders):
+    total = 0
     return 1
"""

VALID_LINE = 2  # the single added line, after context line 1


def make_result(comments):
    return CodeReviewResult(
        summary="Looks risky.",
        overall_verdict="COMMENT",
        comments=comments,
    )


def run_pipeline(result, pr_diff=DIFF):
    """Run the pipeline with diff parsing, GitHub I/O and Gemini mocked."""
    get_diff = AsyncMock(return_value=pr_diff)
    post_review = AsyncMock(return_value={"id": 1})
    parse = Mock(side_effect=GitDiffParser.parse_patch)
    review = Mock(return_value=result)

    with patch.object(main_module.github_client, "get_pull_request_diff", get_diff), \
         patch.object(main_module.github_client, "post_pr_review", post_review), \
         patch.object(main_module.diff_parser, "parse_patch", parse), \
         patch.object(main_module.ai_reviewer, "review_code_diff", review):
        asyncio.run(execute_pr_review_pipeline("octo", "demo", 7, "abc123"))

    return {"post": post_review, "review": review, "get_diff": get_diff}


def test_skips_non_python_files():
    from app.analyzer.diff_parser import FileDiff

    lockfile = {"package-lock.json": FileDiff("package-lock.json")}
    post = AsyncMock()
    with patch.object(main_module.github_client, "get_pull_request_diff", AsyncMock(return_value=DIFF)), \
         patch.object(main_module.github_client, "post_pr_review", post), \
         patch.object(main_module.diff_parser, "parse_patch", Mock(return_value=lockfile)), \
         patch.object(main_module.ai_reviewer, "review_code_diff", Mock()) as review:
        asyncio.run(execute_pr_review_pipeline("octo", "demo", 7, "abc123"))

    review.assert_not_called()
    post.assert_not_called()


def test_no_review_posted_when_model_returns_no_comments():
    out = run_pipeline(make_result([]))
    out["post"].assert_not_called()


def test_diff_is_fetched_and_reviewer_receives_valid_lines():
    out = run_pipeline(make_result([]))
    out["get_diff"].assert_awaited_once_with("octo", "demo", 7)
    kwargs = out["review"].call_args.kwargs
    assert kwargs["filename"] == "service.py"
    assert kwargs["valid_lines"] == {VALID_LINE}


def test_comment_on_valid_line_is_posted():
    comment = InlineReviewComment(
        file_path="service.py",
        line_number=VALID_LINE,
        category="SECURITY",
        severity="WARNING",
        issue_description="Missing guard.",
        suggested_code="if not orders:\n    return 0",
    )
    out = run_pipeline(make_result([comment]))
    out["post"].assert_called_once()
    kwargs = out["post"].call_args.kwargs
    assert kwargs["event"] == "COMMENT"
    assert kwargs["commit_id"] == "abc123"
    assert kwargs["pull_number"] == 7
    assert [c["line"] for c in kwargs["comments"]] == [VALID_LINE]
    assert kwargs["comments"][0]["path"] == "service.py"
    assert "```suggestion" in kwargs["comments"][0]["body"]
    assert "Missing guard." in kwargs["comments"][0]["body"]


def test_comment_outside_valid_lines_is_dropped():
    inline = InlineReviewComment(
        file_path="service.py",
        line_number=999,  # not an added line -> GitHub would answer 422
        category="STYLE",
        severity="SUGGESTION",
        issue_description="Formatting nit.",
        suggested_code="pass",
    )
    out = run_pipeline(make_result([inline]))
    out["post"].assert_not_called()


def test_critical_comment_triggers_request_changes_verdict():
    comment = InlineReviewComment(
        file_path="service.py",
        line_number=VALID_LINE,
        category="SECURITY",
        severity="CRITICAL",
        issue_description="SQL injection via order ids.",
        suggested_code="cursor.execute(sql, params)",
    )
    out = run_pipeline(make_result([comment]))
    kwargs = out["post"].call_args.kwargs
    assert kwargs["event"] == "REQUEST_CHANGES"
    assert "Automated Code Quality" in kwargs["body_summary"]