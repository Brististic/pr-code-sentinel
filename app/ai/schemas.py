from pydantic import BaseModel, Field
from typing import List, Literal


class InlineReviewComment(BaseModel):
    file_path: str = Field(description="The relative path to the file.")
    line_number: int = Field(description="The exact new line number in the diff that this comment applies to.")
    category: Literal["SECURITY", "BUG", "PERFORMANCE", "STYLE", "BEST_PRACTICE"] = Field(
        description="The categorization of the finding."
    )
    severity: Literal["CRITICAL", "WARNING", "SUGGESTION"] = Field(
        description="Severity level of the issue."
    )
    issue_description: str = Field(description="Precise technical explanation of the issue.")
    suggested_code: str = Field(description="Actionable replacement code snippet or patch.")


class CodeReviewResult(BaseModel):
    summary: str = Field(description="High-level markdown summary of the PR quality.")
    overall_verdict: Literal["APPROVE", "REQUEST_CHANGES", "COMMENT"] = Field(
        description="The review verdict."
    )
    comments: List[InlineReviewComment] = Field(default_factory=list, description="List of inline findings.")