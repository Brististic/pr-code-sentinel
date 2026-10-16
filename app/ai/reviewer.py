import os
import json
from typing import List, Set
from google import genai
from google.genai import types
from app.ai.schemas import CodeReviewResult


class AIReviewService:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-3.8-flash"    
    def review_code_diff(
        self,
        filename: str,
        diff_code: str,
        ast_violations: list,
        valid_lines: Set[int]
    ) -> CodeReviewResult:
        """Invokes structured LLM analysis enriched with deterministic AST context."""

        violations_json = json.dumps(ast_violations, indent=2) if ast_violations else "None detected."
        valid_line_numbers = sorted(list(valid_lines))

        prompt = (
            "You are a Principal Software Engineer performing a rigorous Pull Request code review.\n\n"
            f"### Target File: {filename}\n\n"
            "### Git Diff:\n"
            f"{diff_code}\n\n"
            "### Deterministic AST & Static Analysis Flags:\n"
            f"{violations_json}\n\n"
            "### Review Instructions:\n"
            "1. Review ONLY the modified code lines.\n"
            "2. Catch security risks (OWASP Top 10, injection, hardcoded secrets), race conditions, and unhandled edge cases.\n"
            f"3. Every inline comment MUST target one of the following valid line numbers in this file: {valid_line_numbers}\n"
            "4. Do NOT leave comments on lines outside this list.\n"
            "5. Provide actionable replacement code snippets for suggestions.\n"
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CodeReviewResult,
                temperature=0.2,
            ),
        )

        result_dict = json.loads(response.text)
        return CodeReviewResult(**result_dict)