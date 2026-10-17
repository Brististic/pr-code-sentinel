"""Smoke test: boot the app, verify signature check, non-PR events, and the
accepted path for a validly signed pull_request webhook (pipeline mocked)."""
import hashlib
import hmac
import json
import os

import httpx
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
SECRET = os.environ["GITHUB_WEBHOOK_SECRET"]

from app.main import app, execute_pr_review_pipeline  # noqa: E402

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"{'PASS' if cond else 'FAIL'}: {name} {detail}")


def sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


async def run():
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # 1. app imported and settings loaded
        from app.main import settings
        check("GEMINI_API_KEY loaded from .env", bool(settings.gemini_api_key))

        # 2. missing signature -> 401
        r = await c.post("/webhook/github", content=b"{}")
        check("missing signature rejected 401", r.status_code == 401, str(r.status_code))

        # 3. wrong signature -> 401
        r = await c.post(
            "/webhook/github",
            content=b"{}",
            headers={"X-Hub-Signature-256": "sha256=" + "0" * 64},
        )
        check("bad signature rejected 401", r.status_code == 401, str(r.status_code))

        # 4. valid signature, non-PR event -> skipped
        body = json.dumps({"zen": "hi"}).encode()
        r = await c.post(
            "/webhook/github",
            content=body,
            headers={"X-Hub-Signature-256": sign(body), "X-GitHub-Event": "push"},
        )
        check(
            "non-PR event skipped",
            r.status_code == 200 and r.json().get("status") == "skipped",
            r.text,
        )

        # 5. valid signature, PR opened -> accepted (pipeline mocked)
        payload = {
            "action": "opened",
            "repository": {"owner": {"login": "octo"}, "name": "demo"},
            "pull_request": {"number": 7, "head": {"sha": "abc123"}},
        }
        b = json.dumps(payload).encode()
        captured = []

        async def fake_pipeline(*args, **kwargs):
            captured.append(args)

        import app.main as m
        original = m.execute_pr_review_pipeline
        m.execute_pr_review_pipeline = fake_pipeline

        # background task object was already bound? re-register via endpoint uses module global
        from starlette.background import BackgroundTask  # noqa: F401

        # Patch the endpoint's referenced global before calling
        r = await c.post(
            "/webhook/github",
            content=b,
            headers={"X-Hub-Signature-256": sign(b), "X-GitHub-Event": "pull_request"},
        )
        m.execute_pr_review_pipeline = original
        check(
            "valid PR webhook accepted",
            r.status_code == 200 and r.json().get("status") == "accepted",
            r.text,
        )

        # 6. docs / openapi available
        r = await c.get("/openapi.json")
        check("openapi served", r.status_code == 200, str(r.status_code))

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        raise SystemExit(f"FAILED: {failed}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run())