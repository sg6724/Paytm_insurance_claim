"""Every mock partner, run side by side across the three sample claims, plus the ways each one can be misused."""

import pytest

from app import claims as C
from app import store
from tests.conftest import start_claim

# What each mock must do for each claim. A row reads as one journey; a column compares the claims.
CASES = {
    "sunita": {
        "sample": "sunita_gallbladder", "member": "m_sunita", "path": ["under_review", "query_raised", "under_review", "partially_approved", "settled"],
        "decision": "partially_approved", "approved": 62400, "claimed": 110000, "letter": "CLAIM SETTLEMENT (PARTIAL)", "bridge": 55000, "si": 500000,
    },
    "arjun": {
        "sample": "arjun_dengue", "member": "m_arjun", "path": ["under_review", "approved", "settled"],
        "decision": "approved", "approved": 62000, "claimed": 62000, "letter": "CLAIM SETTLEMENT\n", "bridge": 50000, "si": 1000000,
    },
    "rakesh": {
        "sample": "rakesh_knee", "member": "m_rakesh", "path": ["under_review", "rejected"],
        "decision": "rejected", "approved": 0, "claimed": 276000, "letter": "REPUDIATION OF CLAIM", "bridge": None, "si": 500000,
    },
}


def submitted(api, case):
    cid = start_claim(api, case["sample"], case["member"])
    api.post(f"/claims/{cid}/fill-mode", json={"mode": "ai"})
    api.post(f"/claims/{cid}/intimate")
    assert api.post(f"/claims/{cid}/submit").status_code == 200
    return cid


def run_insurer(api, cid):
    """Advance the insurer until it stops, answering queries. Returns the claim and every status it went through."""
    path = []
    for _ in range(8):
        c = api.post(f"/claims/{cid}/advance").json()
        path.append(c["status"])
        for t in c.get("tasks", []):
            if t["status"] == "open":
                c = api.post(f"/claims/{cid}/tasks/{t['id']}", json={"note": "uploaded"}).json()
                path.append(c["status"])
        if c["status"] in ("settled", "rejected"):
            return c, path
    raise AssertionError(path)


@pytest.fixture(params=CASES, ids=list(CASES))
def case(request):
    return CASES[request.param]


# ---------- side by side ----------

def test_insurer_review_query_decision_settlement(api, case):
    c, path = run_insurer(api, submitted(api, case))
    assert path == case["path"]
    assert c["decision"]["type"] == case["decision"]
    assert c["decision"]["amount_approved"] == case["approved"] and c["decision"]["amount_claimed"] == case["claimed"]
    assert bool(c.get("settled_on")) == (case["decision"] != "rejected")


def test_decision_letter_names_the_claim_and_the_way_out(api, case):
    c, _ = run_insurer(api, submitted(api, case))
    letter = c["decision"]["letter"]
    assert case["letter"] in letter and c["insurer_ref"] in letter and "Ombudsman" in letter


def test_settlement_reduces_the_sum_insured(api, case):
    cid = submitted(api, case)
    c, _ = run_insurer(api, cid)
    assert api.get(f"/policies/{c['policy_id']}").json()["remaining_si"] == case["si"] - case["approved"]


def test_insurer_stops_once_finished(api, case):
    cid = submitted(api, case)
    c, _ = run_insurer(api, cid)
    again = api.post(f"/claims/{cid}/advance").json()
    assert again["status"] == c["status"] and len(again["timeline"]) == len(c["timeline"])
    assert api.get(f"/policies/{c['policy_id']}").json()["remaining_si"] == case["si"] - case["approved"]  # no double payment


def test_nhcx_bundle_is_complete_and_references_resolve(api, case):
    cid = submitted(api, case)
    b = api.get(f"/claims/{cid}/fhir").json()
    full = {e["fullUrl"] for e in b["entry"]}
    res = {e["resource"]["resourceType"]: e["resource"] for e in b["entry"]}
    assert b["resourceType"] == "Bundle" and b["identifier"]["value"].startswith("CLM")
    assert {"Patient", "Organization", "Coverage", "Claim", "DocumentReference"} <= res.keys()
    claim = res["Claim"]
    for ref in (claim["patient"], claim["insurer"], claim["provider"], claim["insurance"][0]["coverage"], res["Coverage"]["beneficiary"]):
        assert ref["reference"] in full
    assert claim["total"] == {"value": case["claimed"], "currency": "INR"}
    assert sum(i["net"]["value"] for i in claim["item"]) == case["claimed"]


def test_lender_offer_matches_the_expected_payout(api, case):
    cid = submitted(api, case)
    r = api.get(f"/claims/{cid}/bridge")
    if case["bridge"] is None:
        assert r.status_code == 404  # no loan against a claim that will pay nothing
    else:
        o = r.json()
        assert o["principal"] == case["bridge"]
        assert o["total_repayable"] == o["principal"] + o["interest"] + o["processing_fee"] + o["gst"]


def test_support_ticket_attaches_to_the_claim(api, case):
    cid = submitted(api, case)
    t = api.post("/support/ticket", json={"topic": "claim_tracker", "claim_id": cid, "messages": [{"role": "user", "content": "help"}]}).json()
    assert t["claim_id"] == cid and t["status"] == "open"


def test_upi_receipt_lands_on_the_claim_timeline(api, case):
    cid = submitted(api, case)
    txn = api.post("/mock/upi/pay", json={"amount": 5000, "payee": "Hospital", "claim_id": cid}).json()
    assert txn["status"] == "SUCCESS" and txn["utr"]
    assert any(txn["utr"] in e["detail"] for e in api.get(f"/claims/{cid}").json()["timeline"])


# ---------- lender and settlement together ----------

def test_bridge_loan_comes_out_of_the_settlement(api):
    cid = submitted(api, CASES["sunita"])
    owed = api.get(f"/claims/{cid}/bridge").json()["total_repayable"]
    api.post(f"/claims/{cid}/bridge/accept", json={"consent": True})
    c, _ = run_insurer(api, cid)
    assert c["bridge"]["status"] == "repaid" and c["bridge"]["repaid_amount"] == owed
    assert c["net_credited"] == 62400 - owed
    assert f"₹{62400 - owed:,.0f} credited" in c["timeline"][-1]["title"]


def test_no_loan_means_the_full_amount_is_credited(api):
    c, _ = run_insurer(api, submitted(api, CASES["arjun"]))
    assert c["net_credited"] == 62000


def test_settlement_smaller_than_the_loan_leaves_a_balance(api):
    cid = submitted(api, CASES["sunita"])
    owed = api.get(f"/claims/{cid}/bridge").json()["total_repayable"]
    api.post(f"/claims/{cid}/bridge/accept", json={"consent": True})
    for _ in range(8):
        c = api.post(f"/claims/{cid}/advance").json()
        for t in c.get("tasks", []):
            if t["status"] == "open":
                c = api.post(f"/claims/{cid}/tasks/{t['id']}", json={"note": "x"}).json()
        if c["status"] == "partially_approved":
            break
    stored = store.get("claim", cid)
    stored["decision"]["amount_approved"] = 10000
    store.put("claim", stored)
    c = api.post(f"/claims/{cid}/advance").json()
    assert c["bridge"]["status"] == "part_repaid" and c["bridge"]["balance_due"] == owed - 10000
    assert c["net_credited"] == 0


def test_rejection_letter_gives_the_real_reason():
    policy = {"insurer": "X", "policy_number": "P1", "members": [{"id": "m", "name": "A"}]}
    letter = C._letter({"member_id": "m", "insurer_ref": "CLM1"}, policy, "rejected", 100, 0, [],
                       {"reason": "Admission date is before the policy start date.", "clause_id": None})
    assert "before the policy start date" in letter and "specified diseases" not in letter and "Clause" not in letter


def test_query_quotes_the_real_pharmacy_total(api):
    cid = submitted(api, CASES["sunita"])
    api.post(f"/claims/{cid}/advance")
    task = api.post(f"/claims/{cid}/advance").json()["tasks"][0]
    assert "₹12,500" in task["detail"]


# ---------- misuse ----------

def test_paytm_policies_add_once_and_404_when_unknown(api):
    pid = api.get("/policies/paytm").json()[0]["id"]
    assert api.post(f"/policies/paytm/{pid}").json()["id"] == pid
    api.post(f"/policies/paytm/{pid}")
    assert len(api.get("/policies").json()) == 1
    assert api.post("/policies/paytm/nope").status_code == 404


def test_readding_a_policy_keeps_the_used_sum_insured(api):
    c, _ = run_insurer(api, submitted(api, CASES["sunita"]))
    api.post("/samples/sunita_gallbladder/policy")
    assert api.get(f"/policies/{c['policy_id']}").json()["remaining_si"] == 437600


def test_insurer_fetch_by_number(api):
    assert api.post("/policies/fetch", json={"insurer": "x", "policy_number": "nope"}).status_code == 404
    assert api.post("/policies/fetch", json={"insurer": "Suraksha", "policy_number": "SGI/HFS/2025/0048213"}).json()["id"] == "pol_shield"


@pytest.mark.parametrize("amount", [0, -5000])
def test_upi_refuses_a_non_positive_amount(api, amount):
    assert api.post("/mock/upi/pay", json={"amount": amount, "payee": "H"}).status_code == 422


def test_upi_and_support_refuse_an_unknown_claim(api):
    assert api.post("/mock/upi/pay", json={"amount": 10, "payee": "H", "claim_id": "nope"}).status_code == 404
    assert api.post("/support/ticket", json={"topic": "x", "claim_id": "nope"}).status_code == 404


def test_a_claim_cannot_be_submitted_twice(api):
    cid = submitted(api, CASES["arjun"])
    assert api.post(f"/claims/{cid}/submit").status_code == 409
    run_insurer(api, cid)
    assert api.post(f"/claims/{cid}/submit").status_code == 409
    assert api.get(f"/claims/{cid}").json()["status"] == "settled"


def test_a_draft_ignores_the_insurer_and_an_unknown_task(api):
    pol = api.post("/samples/sunita_gallbladder/policy").json()
    cid = api.post("/claims", json={"policy_id": pol["id"]}).json()["id"]
    assert api.post(f"/claims/{cid}/advance").json()["status"] == "draft"
    assert api.post(f"/claims/{cid}/tasks/nope", json={"note": "x"}).status_code == 404
    assert api.get(f"/claims/{cid}").json()["status"] == "draft"


def test_a_query_cannot_be_answered_twice(api):
    cid = submitted(api, CASES["sunita"])
    api.post(f"/claims/{cid}/advance")
    tid = api.post(f"/claims/{cid}/advance").json()["tasks"][0]["id"]
    assert api.post(f"/claims/{cid}/tasks/{tid}", json={"note": "x"}).status_code == 200
    assert api.post(f"/claims/{cid}/tasks/{tid}", json={"note": "x"}).status_code == 409


def test_no_appeal_without_a_decision_or_with_a_bad_step(api):
    cid = submitted(api, CASES["sunita"])
    assert api.post(f"/claims/{cid}/appeal/draft", json={"step": "insurer"}).status_code == 409
    assert api.post(f"/claims/{cid}/appeal/send", json={"step": "insurer", "text": "x"}).status_code == 409
    assert api.post(f"/claims/{cid}/appeal/draft", json={"step": "nope"}).status_code == 422
    assert api.post(f"/claims/{cid}/appeal/send", json={"step": "nope", "text": "x"}).status_code == 422


def test_the_escalation_ladder_cannot_be_skipped_or_repeated(api):
    cid = submitted(api, CASES["sunita"])
    run_insurer(api, cid)
    assert api.post(f"/claims/{cid}/appeal/send", json={"step": "ombudsman", "text": "x"}).status_code == 409
    assert api.post(f"/claims/{cid}/appeal/send", json={"step": "insurer", "text": "x"}).status_code == 200
    assert api.post(f"/claims/{cid}/appeal/send", json={"step": "insurer", "text": "x"}).status_code == 409
    assert api.post(f"/claims/{cid}/appeal/send", json={"step": "gro", "text": "x"}).status_code == 200


def test_nhcx_refuses_an_empty_claim(api):
    pol = api.post("/samples/sunita_gallbladder/policy").json()
    cid = api.post("/claims", json={"policy_id": pol["id"]}).json()["id"]
    assert api.get(f"/claims/{cid}/fhir").status_code == 409


def test_deleting_a_settled_claim_gives_the_cover_back(api):
    from tests.conftest import advance_to_decision, start_claim
    cid = start_claim(api)
    api.post(f"/claims/{cid}/fill-mode", json={"mode": "ai"})
    api.post(f"/claims/{cid}/intimate")
    api.post(f"/claims/{cid}/submit")
    c = advance_to_decision(api, cid)
    c = api.post(f"/claims/{cid}/advance").json()
    assert c["status"] == "settled"
    pid = c["policy_id"]
    assert api.get(f"/policies/{pid}").json()["remaining_si"] < 500000
    api.delete(f"/claims/{cid}")
    assert api.get(f"/policies/{pid}").json()["remaining_si"] == 500000
