"""End-to-end browser smoke. Requires the docker stack to be up:
    docker compose up --build -d

Run:
    uv run pytest tests/e2e -v -s
"""
import os
import subprocess
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_BASE_URL", "http://localhost:8000")
DEMO_PDF = Path(__file__).resolve().parents[3] / "data" / "set1" / "01_bill_of_lading.pdf"


@pytest.fixture(scope="session", autouse=True)
def _seed_admin():
    subprocess.run(
        [
            "docker", "compose", "exec", "-T", "api",
            "uv", "run", "python", "scripts/seed_admin.py",
            "admin", "admin@example.com", "StrongPass!1",
        ],
        check=True,
    )


def test_customer_upload_to_success_flow():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context()
        page = ctx.new_page()

        page.goto(f"{BASE}/login.html")
        page.fill("input[name=username]", "admin")
        page.fill("input[name=password]", "StrongPass!1")
        page.click("button:has-text('Sign in')")
        page.wait_for_url(f"{BASE}/admin/index.html")

        # Demonstrate admin nav
        for label, fragment in [("Users", "users.html"), ("Jobs", "jobs.html"), ("Audit", "audit.html")]:
            page.click(f"a:has-text('{label}')")
            page.wait_for_url(f"{BASE}/admin/{fragment}")

        # Switch to customer flow by going directly there
        page.goto(f"{BASE}/customer/index.html")
        page.set_input_files("input[type=file]", str(DEMO_PDF))

        # Wait for queued row to appear
        page.wait_for_selector("tr[data-id]", timeout=10_000)
        page.click("tr[data-id]")
        page.wait_for_url("**/customer/job.html?id=*")

        # Poll up to 3 minutes for success
        deadline = time.time() + 180
        while time.time() < deadline:
            txt = page.text_content("#header") or ""
            if "success" in txt:
                break
            time.sleep(3)
            page.reload()
        assert "success" in (page.text_content("#header") or "").lower()
        assert "bol_number" in (page.text_content("#fields") or "")

        browser.close()
