"""API tests run offline: temp database, empty AI cache and no Sarvam key, so every AI call takes its template fallback."""

import os
import tempfile
import uuid

_tmp = tempfile.mkdtemp(prefix="c2c_test_")
os.environ.update(SARVAM_API_KEY="", DATABASE_URL="", RESEND_API_KEY="", DB_PATH=f"{_tmp}/test.db", UPLOAD_DIR=f"{_tmp}/uploads", AI_CACHE_DIR=f"{_tmp}/cache")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import store  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def api():
    with TestClient(app) as c:
        out = c.post("/auth/signup", json={"email": f"{uuid.uuid4().hex}@test.in", "password": "testing-123", "name": "Test User"}).json()
        c.headers["Authorization"] = f"Bearer {out['token']}"
        store.set_user(store.get("account", out["user"]["email"], user=store.SYSTEM)["user_id"])  # for tests that read the store directly
        yield c


def start_claim(api, sample="sunita_gallbladder", member="m_sunita", claim_type="reimbursement"):
    """Add a sample policy, open a claim and attach the sample documents. Returns the claim id."""
    pol = api.post(f"/samples/{sample}/policy").json()
    cid = api.post("/claims", json={"policy_id": pol["id"], "member_id": member, "claim_type": claim_type}).json()["id"]
    assert api.post(f"/samples/{sample}/documents/{cid}").status_code == 200
    return cid


def advance_to_decision(api, cid):
    """Move the mock insurer forward, answering any query, until it has decided."""
    for _ in range(6):
        c = api.post(f"/claims/{cid}/advance").json()
        for t in c.get("tasks", []):
            if t["status"] == "open":
                api.post(f"/claims/{cid}/tasks/{t['id']}", json={"note": "uploaded"})
        if c["status"] in ("partially_approved", "approved", "rejected", "settled"):
            return c
    raise AssertionError("insurer never decided")
