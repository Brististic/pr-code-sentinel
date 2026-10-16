import asyncio
from app.analyzer.diff_parser import GitDiffParser
from app.analyzer.ast_analyzer import StaticASTAnalyzer
from app.ai.reviewer import AIReviewService
from dotenv import load_dotenv

load_dotenv()  # Automatically loads variables from .env into os.environ

from app.analyzer.diff_parser import GitDiffParser
from app.analyzer.ast_analyzer import StaticASTAnalyzer
from app.ai.reviewer import AIReviewService

# Simulated git diff with deliberate anti-patterns
SAMPLE_DIFF = """--- a/service.py
+++ b/service.py
@@ -1,5 +1,15 @@
+def process_orders(user, orders=[]):
+    try:
+        total = 0
+        for order in orders:
+            if order.is_valid:
+                total += order.price
+        return total
+    except:
+        return None
"""

async def run_local_test():
    print("🚀 Running Tier-1 AST Analysis...")
    diff_parser = GitDiffParser()
    ast_analyzer = StaticASTAnalyzer(max_complexity=10)
    ai_reviewer = AIReviewService()

    parsed_files = diff_parser.parse_patch(SAMPLE_DIFF)
    for filename, file_diff in parsed_files.items():
        reconstructed_code = "\n".join(file_diff.added_lines.values())
        violations = [v.to_dict() for v in ast_analyzer.analyze_source(reconstructed_code)]
        
        print(f"✅ AST Violations Found: {violations}")

        print("\n🤖 Running Tier-2 Gemini Semantic Review...")
        review = ai_reviewer.review_code_diff(
            filename=filename,
            diff_code=SAMPLE_DIFF,
            ast_violations=violations,
            valid_lines=file_diff.valid_lines
        )

        print("\n=== Review Summary ===")
        print(review.summary)
        print(f"Verdict: {review.overall_verdict}")
        print("\n=== Inline Comments Generated ===")
        for c in review.comments:
            print(f"- Line {c.line_number} [{c.category} - {c.severity}]: {c.issue_description}")
            print(f"  Fix: {c.suggested_code}")

if __name__ == "__main__":
    asyncio.run(run_local_test())