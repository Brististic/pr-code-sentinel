# PR Code Sentinel 🛡️
> Automated, two-tier Pull Request quality and security review engine powered by deterministic AST static analysis and Gemini structured reasoning.

---

## 🏗️ Architecture

```text
[ GitHub Pull Request ]
          │
          ▼ (Webhook / Diff Payload)
[ FastAPI Ingestion Engine ]
          │
    ┌─────┴──────────────────────────────┐
    ▼                                    ▼
[ Tier-1: Static AST Gate ]      [ Diff Parser & Mapper ]
- Cyclomatic Complexity (Radon)  - Unified diff hunk extraction
- Anti-pattern detection         - Line-mapping validation
- Zero token latency             - Noise & lockfile stripping
    │                                    │
    └──────────────────┬─────────────────┘
                       │ (Context-enriched diff)
                       ▼
          [ Tier-2: Gemini Semantic Review ]
          - Model: gemini-3.8-flash
          - Enforced Pydantic JSON schema
          - Actionable code patches
                       │
                       ▼
          [ GitHub Review API Client ]
          - Batch inline comments
          - Automated PR review verdict (APPROVE / REQUEST_CHANGES)


✨ Key Features
Two-Tier Review Strategy: Eliminates unnecessary LLM token cost and latency by running instant local AST checks for syntax and complexity before invoking semantic reasoning.

Diff Line Mapping: Maps unified git diff lines to source files, preventing HTTP 422 errors when batch-submitting review comments.

Deterministic Complexity Checks: Computes McCabe Cyclomatic Complexity to flag functions needing refactoring.

Actionable Inline Patches: Uses GitHub-compatible suggestion blocks for one-click merge fixes.

🛠️ Tech Stack
Backend: Python 3.11+, FastAPI, Uvicorn, Pydantic v2

Static Analysis: Python ast, Radon (Cyclomatic Complexity)

AI Engine: Google GenAI SDK (gemini-3.8-flash)

Integration: GitHub REST API, Webhooks, HMAC SHA-256 Signature Verification

Testing & Deployment: Pytest, Docker (Multi-stage build)


1.Clone & Setup

git clone [https://github.com/Brististic/pr-code-sentinel.git](https://github.com/Brististic/pr-code-sentinel.git)
cd pr-code-sentinel
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

2.Configure Environment
Create a .env file in the root directory

GITHUB_WEBHOOK_SECRET=your_webhook_secret
GITHUB_TOKEN=ghp_your_github_personal_access_token
GEMINI_API_KEY=AIzaSy_your_gemini_api_key

3.Run Tests
python -m pytest tests/ -v

4.Start Server
python -m uvicorn app.main:app --reload --port 8000

