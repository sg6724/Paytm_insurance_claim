"""End-to-end API journeys. Each test is a path a user can take in the app."""

import io

from tests.conftest import advance_to_decision, start_claim


# ---------- first run, trust ----------

def test_first_run_is_empty_and_not_onboarded(api):
    assert api.get("/policies").json() == []
    assert api.get("/claims").json() == []
    assert api.get("/profile").json()["onboarded"] is False


def test_onboarding_consent_is_recorded_and_withdrawable(api):
    api.patch("/profile", json={"onboarded": True})
    api.post("/consents/all?granted=true")
    granted = {c["purpose"]: c["granted"] for c in api.get("/consents").json()}
    assert granted["read_documents"] and granted["ai_processing"] and granted["share_insurer"]
    assert not granted["share_lender"]  # lender sharing is never bundled in
    api.post("/consents", json={"purpose": "ai_processing", "granted": False})
    assert {c["purpose"]: c["granted"] for c in api.get("/consents").json()}["ai_processing"] is False
    actions = [a["action"] for a in api.get("/audit").json()]
    assert "consent_given" in actions and "consent_withdrawn" in actions


def test_delete_my_data_wipes_everything_but_keeps_a_record(api):
    start_claim(api)
    assert api.get("/claims").json()
    api.delete("/me/data")
    assert api.get("/policies").json() == [] and api.get("/claims").json() == []
    assert [a["action"] for a in api.get("/audit").json()] == ["data_deleted"]


# ---------- policy ----------

def test_paytm_policy_and_explainer_cover_the_five_topics(api):
    listed = api.get("/policies/paytm").json()
    assert listed
    pol = api.post(f"/policies/paytm/{listed[0]['id']}").json()
    ex = api.get(f"/policies/{pol['id']}/explainer").json()
    assert {t["key"] for t in ex["topics"]} == {"room_rent", "waiting", "coverage", "copay", "claims"}
    assert all(t["text"] for t in ex["topics"])


def test_unreadable_policy_upload_is_rejected_cleanly(api):
    r = api.post("/policies/upload", files={"file": ("junk.pdf", io.BytesIO(b"not a pdf"), "application/pdf")})
    assert r.status_code in (422, 502)


# ---------- hospital stay check ----------

def test_hospital_check_by_form_flags_room_rent_with_rupee_impact(api):
    pol = api.post("/samples/sunita_gallbladder/policy").json()
    out = api.post("/hospital/check", json={"policy_id": pol["id"], "facts": {
        "member_id": "m_sunita", "room_category": "single_private", "room_rent_per_day": 7500, "expected_days": 4,
        "procedure": "laparoscopic cholecystectomy", "admission_type": "emergency", "admission_date": "2026-10-12", "estimated_bill": 110000}}).json()
    titles = " ".join(f["title"] for f in out["findings"])
    assert "above your limit of ₹5,000" in titles
    assert out["estimate"]["payable"] < out["estimate"]["billed"]
    assert "intimation" in out["deadlines"] and out["documents"]


def test_hospital_check_inside_limit_is_ok(api):
    pol = api.post("/samples/sunita_gallbladder/policy").json()
    out = api.post("/hospital/check", json={"policy_id": pol["id"], "facts": {
        "member_id": "m_sunita", "room_rent_per_day": 4000, "expected_days": 3, "procedure": "dengue", "admission_type": "planned"}}).json()
    assert any(f["severity"] == "ok" for f in out["findings"])
    assert not any(f["severity"] == "high" for f in out["findings"])


# ---------- Sunita: file, get cut, appeal, bridge ----------

def test_sunita_full_journey_matches_the_pitch_numbers(api):
    cid = start_claim(api)
    filled = api.post(f"/claims/{cid}/fill-mode", json={"mode": "ai"}).json()
    assert filled["form"]["member_id"] == "m_sunita" and filled["form"]["room_rent_per_day"] == 7500
    assert filled["sources"]["total_claimed"]  # every AI-filled field says where it came from

    pf = api.post(f"/claims/{cid}/preflight", json={"form": filled["form"]}).json()
    assert pf["billed"] == 110000 and pf["payable"] == 68400
    assert all(d["reason"] for d in pf["deductions"])

    assert api.post(f"/claims/{cid}/intimate").json()["intimated"]
    sub = api.post(f"/claims/{cid}/submit").json()
    assert sub["status"] == "submitted" and sub["insurer_ref"]

    # the bridge loan is offered while the user waits, and repaid from the settlement
    offer = api.get(f"/claims/{cid}/bridge").json()
    assert offer["kind"] == "settlement_bridge" and 0 < offer["principal"] <= 0.8 * 68400 + 500
    # Key Facts Statement fields are all present
    assert {"apr", "processing_fee", "gst", "total_repayable", "tenure_days", "cooling_off_days", "lender"} <= offer.keys()

    decided = advance_to_decision(api, cid)
    assert decided["decision"]["amount_approved"] == 62400

    d = api.get(f"/claims/{cid}/decision").json()
    assert d["analysis"]["strength"] == "strong" and d["analysis"]["disputed_amount"] == 6000
    assert d["explanation"]

    # escalation ladder unlocks one rung at a time
    ladder = {s["step"]: s["status"] for s in d["ladder"]}
    assert ladder == {"insurer": "available", "gro": "locked", "bima_bharosa": "locked", "ombudsman": "locked"}
    draft = api.post(f"/claims/{cid}/appeal/draft", json={"step": "insurer"}).json()
    assert "6,000" in draft["text"]
    sent = api.post(f"/claims/{cid}/appeal/send", json={"step": "insurer", "text": draft["text"]}).json()
    assert {s["step"]: s["status"] for s in sent["ladder"]}["gro"] == "available"

    actions = {a["action"] for a in api.get("/audit").json()}
    assert {"form_filled", "claim_submitted", "decision_explained", "appeal_sent"} <= actions


def test_submit_is_blocked_until_the_form_is_valid(api):
    pol = api.post("/samples/sunita_gallbladder/policy").json()
    cid = api.post("/claims", json={"policy_id": pol["id"], "member_id": "m_sunita"}).json()["id"]
    api.post(f"/claims/{cid}/fill-mode", json={"mode": "manual"})
    r = api.post(f"/claims/{cid}/submit")
    assert r.status_code == 422 and r.json()["detail"]["corrections"]


def test_manual_form_live_corrections(api):
    pol = api.post("/samples/sunita_gallbladder/policy").json()
    cid = api.post("/claims", json={"policy_id": pol["id"], "member_id": "m_sunita"}).json()["id"]
    api.post(f"/claims/{cid}/fill-mode", json={"mode": "manual"})
    form = {"member_id": "m_sunita", "ifsc": "BAD123", "mobile": "12345", "admission_date": "2026-10-16", "discharge_date": "2026-10-12", "total_claimed": 90000}
    fields = {c["field"] for c in api.post(f"/claims/{cid}/validate", json={"form": form}).json()["corrections"]}
    assert {"ifsc", "mobile", "discharge_date"} <= fields


def test_form_pdf_export(api):
    cid = start_claim(api)
    api.post(f"/claims/{cid}/fill-mode", json={"mode": "ai"})
    r = api.get(f"/claims/{cid}/form.pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    assert "form_exported" in [a["action"] for a in api.get("/audit").json()]


def test_form_pdf_for_an_empty_manual_form_still_renders(api):
    pol = api.post("/samples/sunita_gallbladder/policy").json()
    cid = api.post("/claims", json={"policy_id": pol["id"]}).json()["id"]
    assert api.get(f"/claims/{cid}/form.pdf").content.startswith(b"%PDF")


def test_fhir_claim_pack(api):
    cid = start_claim(api)
    api.post(f"/claims/{cid}/fill-mode", json={"mode": "ai"})
    b = api.get(f"/claims/{cid}/fhir").json()
    kinds = {e["resource"]["resourceType"] for e in b["entry"]}
    assert b["resourceType"] == "Bundle" and {"Patient", "Claim", "Coverage"} <= kinds


# ---------- Arjun: clean claim ----------

def test_arjun_clean_claim_is_paid_in_full(api):
    cid = start_claim(api, "arjun_dengue", "m_arjun")
    form = api.post(f"/claims/{cid}/fill-mode", json={"mode": "ai"}).json()["form"]
    pf = api.post(f"/claims/{cid}/preflight", json={"form": form}).json()
    assert pf["payable"] == pf["billed"] == 62000 and pf["risk"] == "low"


# ---------- Rakesh: rejection, honest odds, appeal first then EMI ----------

def test_rakesh_rejection_is_explained_and_appeal_is_weak(api):
    cid = start_claim(api, "rakesh_knee", "m_rakesh")
    form = api.post(f"/claims/{cid}/fill-mode", json={"mode": "ai"}).json()["form"]
    pf = api.post(f"/claims/{cid}/preflight", json={"form": form}).json()
    assert pf["rejected"] and pf["payable"] == 0 and pf["reject_reasons"][0]["clause_id"] == "C4.3"
    api.post(f"/claims/{cid}/intimate")
    api.post(f"/claims/{cid}/submit")
    advance_to_decision(api, cid)
    d = api.get(f"/claims/{cid}/decision").json()
    assert d["decision"]["type"] == "rejected" and d["analysis"]["strength"] == "weak"
    # appeal path is shown first; only after dismissing it is a medical EMI offered
    assert api.get(f"/claims/{cid}/bridge").status_code == 404
    api.post(f"/claims/{cid}/appeal/dismiss")
    assert api.get(f"/claims/{cid}/bridge").json()["kind"] == "medical_emi"


# ---------- bridge loan, UPI ----------

def test_bridge_loan_accept_requires_consent_and_repays_on_settlement(api):
    cid = start_claim(api)
    form = api.post(f"/claims/{cid}/fill-mode", json={"mode": "ai"}).json()["form"]
    api.post(f"/claims/{cid}/intimate")
    api.post(f"/claims/{cid}/submit")
    assert api.post(f"/claims/{cid}/bridge/accept", json={"consent": False}).status_code == 422
    assert api.post(f"/claims/{cid}/bridge/accept", json={}).status_code == 422
    assert not api.get(f"/claims/{cid}").json().get("bridge")
    ok = api.post(f"/claims/{cid}/bridge/accept", json={"consent": True})
    assert ok.status_code == 200
    assert api.post(f"/claims/{cid}/bridge/accept", json={"consent": True}).status_code == 409  # no second loan
    for _ in range(6):
        c = api.post(f"/claims/{cid}/advance").json()
        for t in c.get("tasks", []):
            if t["status"] == "open":
                api.post(f"/claims/{cid}/tasks/{t['id']}", json={"note": "x"})
    assert api.get(f"/claims/{cid}").json()["bridge"]["status"] == "repaid"
    assert form  # silence unused


def test_mock_upi_payment(api):
    r = api.post("/mock/upi/pay", json={"amount": 5000, "payee": "Shree Sai Hospital"})
    assert r.status_code == 200


# ---------- trust: human review ----------

def test_unreadable_document_is_sent_for_human_review(api):
    pol = api.post("/samples/sunita_gallbladder/policy").json()
    cid = api.post("/claims", json={"policy_id": pol["id"], "member_id": "m_sunita"}).json()["id"]
    d = api.post(f"/claims/{cid}/documents", files={"file": ("blurry.jpg", io.BytesIO(b"\xff\xd8\xff blurry"), "image/jpeg")}).json()
    assert d["confidence"] == 0 and d["review_ticket"]
    assert "human_review_flagged" in [a["action"] for a in api.get("/audit").json()]


def test_confident_sample_documents_are_not_flagged(api):
    cid = start_claim(api)
    assert not any(d.get("review_ticket") for d in api.get(f"/claims/{cid}").json()["documents"])


def test_human_handoff_ticket_carries_the_conversation(api):
    t = api.post("/support/ticket", json={"topic": "claim_form", "messages": [{"role": "user", "content": "help"}]}).json()
    assert t["id"] and t["messages"] and "expert" in t["eta"]


# ---------- ABHA, ombudsman, assistant ----------

def test_abha_fetch_adds_clinical_records_only(api):
    pol = api.post("/samples/sunita_gallbladder/policy").json()
    cid = api.post("/claims", json={"policy_id": pol["id"], "member_id": "m_sunita"}).json()["id"]
    r = api.post(f"/mock/abha/fetch/{cid}").json()
    assert len(r["added"]) == 3
    types = {d["doc_type"] for d in api.get(f"/claims/{cid}").json()["documents"]}
    assert types == {"discharge_summary", "prescription", "investigation_report"}  # no bills, no bank papers
    assert api.post(f"/mock/abha/fetch/{cid}").json()["added"] == []  # idempotent


def test_ombudsman_office_by_pincode(api):
    assert api.get("/ombudsman?pincode=400069").json()["city"] == "Mumbai"


def test_assistant_degrades_gracefully_without_ai(api):
    r = api.post("/assistant/chat", json={"messages": [{"role": "user", "content": "What is co-pay?"}], "lang": "en-IN"})
    assert r.status_code in (200, 502)


def test_first_visit_tips_are_remembered_and_reset(api):
    assert api.get("/profile").json().get("tips_seen", []) == []
    api.patch("/profile", json={"tips_seen": ["policy"]})
    api.patch("/profile", json={"tips_seen": ["policy", "form"]})
    assert api.get("/profile").json()["tips_seen"] == ["policy", "form"]
    api.post("/demo/reset")
    assert api.get("/profile").json().get("tips_seen", []) == []


def test_hospital_chat_still_runs_the_check_when_the_ai_is_unreachable(api):
    pol = api.post("/samples/sunita_gallbladder/policy").json()
    line = "मेरी माँ सुनीता भर्ती हैं, सिंगल रूम 7500 रुपये रोज़, पित्ताशय की सर्जरी"
    r = api.post("/hospital/chat", json={"policy_id": pol["id"], "messages": [{"role": "user", "content": line}], "lang": "hi-IN"})
    assert r.status_code == 200
    out = r.json()
    assert out["ready"] and any("5,000" in f["title"] for f in out["check"]["findings"]) and out["reply"]


def test_hospital_chat_asks_for_what_is_missing_when_the_ai_is_unreachable(api):
    pol = api.post("/samples/sunita_gallbladder/policy").json()
    r = api.post("/hospital/chat", json={"policy_id": pol["id"], "messages": [{"role": "user", "content": "hello"}], "lang": "en-IN"}).json()
    assert not r["ready"] and "who is in hospital" in r["reply"]


def test_assistant_reads_a_shared_pdf(api):
    from pathlib import Path
    pdf = Path(__file__).resolve().parents[2] / "demo-docs" / "Sunita_Settlement_Letter.pdf"
    r = api.post("/assistant/attach", files={"file": ("letter.pdf", pdf.read_bytes(), "application/octet-stream")})
    assert r.status_code == 200 and r.json()["kind"] == "pdf"
    assert "62,400" in r.json()["text"]


def test_assistant_rejects_an_empty_file(api):
    assert api.post("/assistant/attach", files={"file": ("x.pdf", b"", "application/pdf")}).status_code == 422


def test_recordings_are_sent_to_sarvam_with_a_type_it_accepts():
    from app.ai.sarvam import audio_type
    assert audio_type("voice.m4a") == "audio/x-m4a"  # Python's own guess, audio/mp4a-latm, is rejected
    assert audio_type("recording-1.MP4") == "audio/mp4"
    assert audio_type("x.wav") == "audio/wav" and audio_type("x.unknown") == "application/octet-stream"


def test_each_language_gets_a_v4_persona_or_the_v3_fallback():
    from app.ai.sarvam import tts_voice
    assert tts_voice("hi-IN") == ("bulbul:v4-flash", "simran_enhi_customer")
    assert tts_voice("ta-IN") == ("bulbul:v4-flash", "vijay_ta_narration")
    assert tts_voice("ml-IN") == ("bulbul:v3", "priya")  # no v4 persona yet; a v4 call with priya is a 400
    from app import config
    for lang in config.LANGUAGES:
        if lang["tts"]:
            model, speaker = tts_voice(lang["code"])
            assert model == "bulbul:v3" or speaker.count("_") >= 2, (lang["code"], speaker)


def test_rupee_amounts_are_spoken_with_the_local_word():
    from app.ai.sarvam import speakable
    assert speakable("உங்கள் ₹45,000 க்ளெய்ம், ₹3,200.", "ta-IN") == "உங்கள் 45,000 ரூபாய் க்ளெய்ம், 3,200 ரூபாய்."
    assert speakable("আপনার ₹45,000 টাকার দাবি", "bn-IN") == "আপনার 45,000 টাকার দাবি"  # not "টাকা টাকার"
    assert speakable("आपका ₹45,000 का claim", "hi-IN") == "आपका ₹45,000 का claim"  # already read well


def test_an_empty_answer_is_an_error_and_is_not_saved(api, monkeypatch):
    from app.ai import tools
    monkeypatch.setattr(tools, "assistant", lambda m, lang, ctx: "  ")
    assert api.post("/assistant/chat", json={"message": "Let us continue"}).status_code == 502
    assert api.get("/assistant/thread").json()["messages"] == []


def test_speaking_the_same_text_twice_replays_from_cache(monkeypatch):
    import base64 as b64
    from app.ai import sarvam
    calls = []

    class Resp:
        status_code, headers = 200, {"content-type": "application/json"}
        def json(self):
            return {"audios": [b64.b64encode(b"RIFFfake").decode()]}

    monkeypatch.setattr(sarvam.config, "SARVAM_API_KEY", "test")
    monkeypatch.setattr(sarvam.httpx, "post", lambda *a, **k: calls.append(k["json"]) or Resp())
    first = sarvam.tts("Your claim is approved, test replay.", "en-IN")
    assert sarvam.tts("Your claim is approved, test replay.", "en-IN") == first  # used to raise KeyError: 'value'
    assert len(calls) == 1 and calls[0]["model"] == "bulbul:v4-flash" and calls[0]["enable_preprocessing"] is True


def test_stay_chat_answers_the_question_from_the_rules_before_asking(api, monkeypatch):
    """'Room rent is 10000, should I go ahead?' must get the room-limit answer, not just 'who is in hospital?'."""
    from app.ai import sarvam
    seen = {}

    def fake_chat(msgs, **kw):
        seen["ctx"] = __import__("json").loads(msgs[1]["content"])
        seen["sys"] = msgs[0]["content"]
        return {"reply": "ok", "facts": {}}

    monkeypatch.setattr(sarvam, "chat", fake_chat)
    pol = api.post("/samples/sunita_gallbladder/policy").json()
    msgs = [{"role": "user", "content": "My room rent is 10000 per day, should I go ahead with it?"}]
    out = api.post("/hospital/chat", json={"policy_id": pol["id"], "messages": msgs, "lang": "en-IN"}).json()
    assert out["facts"]["room_rent_per_day"] == 10000
    titles = " ".join(f["title"] for f in seen["ctx"]["RULE_FINDINGS"])
    assert "above your limit of ₹5,000" in titles  # the model is handed the answer, computed by rules
    assert seen["ctx"]["ASK_NEXT"] == "the illness or treatment"  # one question, the one that matters most
    assert "answer it FIRST" in seen["sys"] and "Greet briefly once" in seen["sys"]


def test_stay_chat_does_not_greet_again(api, monkeypatch):
    from app.ai import sarvam
    seen = {}
    monkeypatch.setattr(sarvam, "chat", lambda msgs, **kw: seen.update(sys=msgs[0]["content"]) or {"reply": "ok", "facts": {}})
    pol = api.post("/samples/sunita_gallbladder/policy").json()
    msgs = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hello"}, {"role": "user", "content": "I think"}]
    api.post("/hospital/chat", json={"policy_id": pol["id"], "messages": msgs, "lang": "en-IN"})
    assert "Do not greet again" in seen["sys"] and "did not catch it" in seen["sys"]


def test_repeated_sentences_are_dropped():
    from app.ai.tools import tidy_reply
    assert tidy_reply("10% co-pay भी लगेगा। कमरा बदलें। 10% co-pay भी लगेगा।") == "10% co-pay भी लगेगा। कमरा बदलें।"


def test_nhcx_claim_pack_is_valid_fhir_r4(api):
    """Checked against the FHIR R4 schema (fhir.resources). The NRCeS profile itself needs the HL7 validator and real ids."""
    from fhir.resources.R4B.bundle import Bundle
    from tests.conftest import start_claim
    cid = start_claim(api)
    api.post(f"/claims/{cid}/fill-mode", json={"mode": "ai"})
    b = api.get(f"/claims/{cid}/fhir").json()
    Bundle.model_validate(b)
    kinds = [e["resource"]["resourceType"] for e in b["entry"]]
    assert kinds[0] == "Claim" and {"Patient", "Coverage", "Organization", "DocumentReference"} <= set(kinds)
    assert all(e["fullUrl"].startswith("urn:uuid:") for e in b["entry"])
    claim = b["entry"][0]["resource"]
    assert claim["total"]["value"] == 110000 and len(claim["item"]) == 14
