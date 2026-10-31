"""Every outcome the mock insurer can reach, including the ones no sample claim produces, and how appeals end."""

import pytest

from app import store
from tests.conftest import start_claim
from tests.test_mocks import CASES, run_insurer, submitted


def filled(api, sample="sunita_gallbladder", member="m_sunita"):
    cid = start_claim(api, sample, member)
    api.post(f"/claims/{cid}/fill-mode", json={"mode": "ai"})
    api.post(f"/claims/{cid}/intimate")
    return cid


def change_policy(pid, **fields):
    p = store.get("policy", pid)
    p.update(fields)
    store.put("policy", p)


def change_claim(cid, **fields):
    c = store.get("claim", cid)
    c.update(fields)
    store.put("claim", c)


def initial_waiting(cid):
    change_policy("pol_shield", start_date="2026-10-01")


def pre_existing(cid):
    p = store.get("policy", "pol_shield")
    p["members"][0]["ped"] = ["cholelithiasis"]
    store.put("policy", p)


def exclusion(cid):
    change_policy("pol_shield", exclusions=[{"keyword": "cholecystectomy", "label": "Gallbladder surgery"}])


@pytest.mark.parametrize("setup,code,words", [
    (initial_waiting, "initial_waiting", "first 30 days"),
    (pre_existing, "ped_waiting", "pre-existing"),
    (exclusion, "exclusion", "Excluded: Gallbladder surgery"),
], ids=["initial_waiting", "pre_existing", "exclusion"])
def test_every_rejection_reason_runs_end_to_end(api, setup, code, words):
    cid = filled(api)
    setup(cid)
    pf = api.post(f"/claims/{cid}/preflight", json={"form": api.get(f"/claims/{cid}").json()["form"]}).json()
    assert pf["rejected"] and pf["reject_reasons"][0]["code"] == code
    assert api.post(f"/claims/{cid}/submit").status_code == 200
    assert api.get(f"/claims/{cid}/bridge").status_code == 404
    c, path = run_insurer(api, cid)
    assert path[-1] == "rejected" and c["decision"]["amount_approved"] == 0
    letter = c["decision"]["letter"]
    assert words in letter and "REPUDIATION" in letter and c["insurer_ref"] in letter
    if code != "exclusion":
        assert "specified diseases" not in letter
    assert api.get(f"/claims/{cid}/decision").json()["analysis"]["strength"] == "weak"
    assert api.get(f"/policies/pol_shield").json()["remaining_si"] == 500000


@pytest.mark.parametrize("dates", [{"start_date": "2026-11-01"}, {"end_date": "2026-10-01"}], ids=["before_start", "after_expiry"])
def test_policy_not_in_force_is_stopped_at_submit(api, dates):
    cid = filled(api)
    change_policy("pol_shield", **dates)
    r = api.post(f"/claims/{cid}/submit")
    assert r.status_code == 422 and r.json()["detail"]["corrections"][0]["field"] == "admission_date"


def test_fair_insurer_pays_what_the_rules_say(api):
    cid = filled(api)
    change_claim(cid, insurer_behaviour="fair")
    api.post(f"/claims/{cid}/submit")
    c, path = run_insurer(api, cid)
    assert path == ["under_review", "partially_approved", "settled"] and c["decision"]["amount_approved"] == 68400
    assert api.get(f"/claims/{cid}/decision").json()["analysis"]["strength"] == "none"


def test_query_with_a_fair_decision(api):
    cid = filled(api)
    change_claim(cid, insurer_behaviour="query")
    api.post(f"/claims/{cid}/submit")
    c, path = run_insurer(api, cid)
    assert "query_raised" in path and c["decision"]["amount_approved"] == 68400


def decided(api):
    cid = submitted(api, CASES["sunita"])
    for _ in range(6):
        c = api.post(f"/claims/{cid}/advance").json()
        for t in c.get("tasks", []):
            if t["status"] == "open":
                c = api.post(f"/claims/{cid}/tasks/{t['id']}", json={"note": "x"}).json()
        if c["status"] == "partially_approved":
            return cid
    raise AssertionError(c["status"])


def appeal(api, cid, step="insurer"):
    assert api.post(f"/claims/{cid}/appeal/send", json={"step": step, "text": "x"}).status_code == 200


def test_winning_appeal_before_settlement_pays_the_right_amount(api):
    cid = decided(api)
    appeal(api, cid)
    assert api.get(f"/claims/{cid}").json()["appeal_pending"] is True
    c = api.post(f"/claims/{cid}/advance").json()
    assert c["appeal_pending"] is False and c["status"] == "partially_approved"
    assert c["decision"]["amount_approved"] == 68400 and c["decision"]["revised"]
    assert not any(d["kind"] == "insurer_proportionate" for d in c["decision"]["deductions"])
    assert "68,400" in c["decision"]["letter"]
    c = api.post(f"/claims/{cid}/advance").json()
    assert c["status"] == "settled" and c["net_credited"] == 68400
    assert api.get(f"/policies/{c['policy_id']}").json()["remaining_si"] == 500000 - 68400


def test_winning_appeal_after_settlement_tops_up_once(api):
    cid = decided(api)
    c = api.post(f"/claims/{cid}/advance").json()
    assert c["status"] == "settled" and c["net_credited"] == 62400
    appeal(api, cid)
    c = api.post(f"/claims/{cid}/advance").json()
    assert c["status"] == "settled" and c["net_credited"] == 68400 and c["decision"]["amount_approved"] == 68400
    assert "credited to your bank account" in c["appeals"][0]["reply"]["text"]
    pid = c["policy_id"]
    assert api.get(f"/policies/{pid}").json()["remaining_si"] == 500000 - 68400
    api.post(f"/claims/{cid}/advance")  # nothing further happens
    assert api.get(f"/claims/{cid}").json()["net_credited"] == 68400


def test_a_won_appeal_closes_the_ladder(api):
    cid = decided(api)
    appeal(api, cid)
    api.post(f"/claims/{cid}/advance")
    d = api.get(f"/claims/{cid}/decision").json()
    assert d["ladder"][0]["reply"]["outcome"] == "reversed"
    assert [r["status"] for r in d["ladder"]] == ["sent", "locked", "locked", "locked"]
    assert d["analysis"]["strength"] == "none" and not d["review_ticket"]
    assert api.post(f"/claims/{cid}/appeal/send", json={"step": "gro", "text": "x"}).status_code == 409


def test_losing_appeal_stands_and_can_still_escalate(api):
    cid = submitted(api, CASES["rakesh"])
    run_insurer(api, cid)
    appeal(api, cid)
    c = api.post(f"/claims/{cid}/advance").json()
    assert c["status"] == "rejected" and c["decision"]["amount_approved"] == 0
    assert c["appeals"][0]["reply"]["outcome"] == "upheld" and "waiting period" in c["appeals"][0]["reply"]["text"]
    assert api.get(f"/claims/{cid}/decision").json()["ladder"][1]["status"] == "available"
    appeal(api, cid, "gro")
    assert api.post(f"/claims/{cid}/advance").json()["appeals"][1]["reply"]["outcome"] == "upheld"


def test_appeal_with_no_wrong_deduction_changes_nothing(api):
    cid = filled(api)
    change_claim(cid, insurer_behaviour="fair")
    api.post(f"/claims/{cid}/submit")
    run_insurer(api, cid)
    appeal(api, cid)
    c = api.post(f"/claims/{cid}/advance").json()
    assert c["appeals"][0]["reply"]["outcome"] == "closed" and c["decision"]["amount_approved"] == 68400


def test_two_open_appeals_cannot_pay_twice(api):
    cid = decided(api)
    appeal(api, cid)
    appeal(api, cid, "gro")
    api.post(f"/claims/{cid}/advance")
    c = api.post(f"/claims/{cid}/advance").json()
    assert c["decision"]["amount_approved"] == 68400
    assert c["appeals"][1]["reply"]["outcome"] == "closed"
