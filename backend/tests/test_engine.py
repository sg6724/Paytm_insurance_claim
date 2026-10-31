from app.data.ombudsman import find_office
from app.data.samples import SAMPLE_CLAIMS, SAMPLE_POLICIES
from app.rules.engine import compute, deadlines, hospital_check
from app.rules.non_payables import match_non_payable

POL = {p["id"]: p for p in SAMPLE_POLICIES}


def run(key):
    c = SAMPLE_CLAIMS[key]
    return compute(POL[c["policy_id"]], c)


def test_room_rent_breach_matches_pitch_number():
    r = run("sunita_gallbladder")
    assert r["billed"] == 110000
    assert r["payable"] == 68400
    kinds = {d["kind"] for d in r["deductions"]}
    assert {"non_payable", "proportionate", "room_excess", "copay"} <= kinds
    # proportionate cut never touches pharmacy or diagnostics
    assert not any(d["category"] in ("pharmacy", "diagnostics") for d in r["deductions"] if d["kind"] == "proportionate")
    assert abs(r["proportion"] - 5000 / 7500) < 1e-4


def test_clean_claim_paid_in_full_with_consumables_rider():
    r = run("arjun_dengue")
    assert r["payable"] == r["billed"] == 62000
    assert r["risk"] == "low"


def test_specific_disease_waiting_rejects():
    r = run("rakesh_knee")
    assert r["rejected"] and r["payable"] == 0
    assert r["reject_reasons"][0]["code"] == "specific_waiting"
    assert r["reject_reasons"][0]["clause_id"] == "C4.3"


def test_non_payable_word_boundaries():
    assert match_non_payable("Gloves and masks")
    assert match_non_payable("Combiflam tablets") is None
    assert match_non_payable("Pantoprazole 40mg caps") is None


def test_hospital_check_without_bill():
    out = hospital_check(POL["pol_shield"], {"member_id": "m_sunita", "room_rent_per_day": 7500, "expected_days": 4,
                                              "procedure": "laparoscopic cholecystectomy", "admission_type": "emergency",
                                              "admission_date": "2026-10-12"})
    titles = " ".join(f["title"] for f in out["findings"])
    assert "above your limit of ₹5,000" in titles
    assert out["estimate"] is None
    assert "intimation" in out["deadlines"]


def test_interest_when_insurer_late():
    d = deadlines(POL["pol_shield"], {"discharge_date": "2026-09-01", "last_document_date": "2026-09-05",
                                      "today": "2026-10-15", "amount_due": 68400}, bank_rate=5.75)
    assert d["settlement_due"] == "2026-10-05"
    assert d["late_days"] == 10
    assert d["interest_due"] == round(68400 * 0.0775 * 10 / 365, 2)


def test_ombudsman_mapping():
    assert find_office("400069")["city"] == "Mumbai"
    assert find_office("400703")["city"] == "Pune"   # Navi Mumbai
    assert find_office("560001")["city"] == "Bengaluru"
    assert find_office("110001")["city"] == "Delhi"
