"""Claimezy API."""

from __future__ import annotations

import copy
import mimetypes
from datetime import date

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import assistant_memory as memory
from . import claims as C
from . import config, store
from .ai import sarvam, tools
from .ai.sarvam import SarvamError
from .data.ombudsman import find_office
from .data.samples import PAYTM_POLICIES, SAMPLE_CLAIMS, SAMPLE_POLICIES
from .rules import engine

app = FastAPI(title="Claimezy API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/files", StaticFiles(directory=str(config.UPLOAD_DIR)), name="files")
DEMO_DOCS = config.BASE.parent / "demo-docs"
if DEMO_DOCS.exists():
    app.mount("/demo-docs", StaticFiles(directory=str(DEMO_DOCS), html=True), name="demo-docs")

SAMPLE_BY_ID = {p["id"]: p for p in SAMPLE_POLICIES}


def must(kind, id):
    obj = store.get(kind, id)
    if not obj:
        raise HTTPException(404, f"{kind} not found")
    return obj


def ensure_profile():
    if not store.get("profile", "me"):
        store.put("profile", {"id": "me", "name": "Sunita Kulkarni", "mobile": "9820012345", "email": "sunita.k@example.com",
                              "pincode": "400069", "language": "en-IN", "onboarded": False})


@app.on_event("startup")
def startup():
    store.conn()
    ensure_profile()


# ---------------- meta, profile, trust ----------------

@app.get("/health")
def health():
    return {"ok": True, "sarvam": sarvam.available(), "today": str(date.today())}


@app.get("/languages")
def languages():
    return config.LANGUAGES


class I18nIn(BaseModel):
    lang: str
    strings: dict


@app.post("/i18n")
def i18n(body: I18nIn):
    """Translate the app's UI strings once per language (cached on disk)."""
    if body.lang.startswith("en"):
        return body.strings
    try:
        out = sarvam.chat([
            {"role": "system", "content": "Translate the JSON values into the target language for a Paytm insurance app. Keep keys unchanged, keep it short and natural, keep ₹ and brand names (Paytm, Claimezy, UPI) as is. Reply with the JSON object only."},
            {"role": "user", "content": f"Target language: {config.LANG_NAME.get(body.lang, body.lang)}\n{__import__('json').dumps(body.strings, ensure_ascii=False)}"},
        ], json_mode=True, task="i18n", max_tokens=4000)
        return {k: out.get(k, v) for k, v in body.strings.items()}
    except Exception:
        return body.strings


@app.get("/profile")
def get_profile():
    ensure_profile()
    return store.get("profile", "me")


class ProfilePatch(BaseModel):
    language: str | None = None
    onboarded: bool | None = None
    pincode: str | None = None
    mobile: str | None = None
    email: str | None = None
    tips_seen: list[str] | None = None


@app.patch("/profile")
def patch_profile(p: ProfilePatch):
    prof = get_profile()
    prof.update({k: v for k, v in p.model_dump().items() if v is not None})
    return store.put("profile", prof)


CONSENT_PURPOSES = [
    {"purpose": "read_documents", "title": "Read my policy and hospital documents", "detail": "To pull out dates, amounts and clauses so you type less."},
    {"purpose": "ai_processing", "title": "Use AI to explain and draft", "detail": "Sarvam AI (hosted in India) explains decisions and drafts letters. AI never decides your payout."},
    {"purpose": "share_insurer", "title": "Share my claim with my insurer", "detail": "Only when you tap Submit. Sent as a standard NHCX claim bundle."},
    {"purpose": "share_lender", "title": "Share claim status with a lending partner", "detail": "Only if you ask for a bridge loan. The lender decides; you can withdraw any time."},
]


@app.get("/consents")
def consents():
    rows = {c["id"]: c for c in store.find("consent")}
    return [dict(p, granted=rows.get(p["purpose"], {}).get("granted", False), at=rows.get(p["purpose"], {}).get("updated_at")) for p in CONSENT_PURPOSES]


class ConsentIn(BaseModel):
    purpose: str
    granted: bool


@app.post("/consents")
def set_consent(c: ConsentIn):
    store.put("consent", {"id": c.purpose, "granted": c.granted})
    store.audit("you", "consent_" + ("given" if c.granted else "withdrawn"), next((p["title"] for p in CONSENT_PURPOSES if p["purpose"] == c.purpose), c.purpose))
    return consents()


@app.post("/consents/all")
def grant_all(granted: bool = True):
    for p in CONSENT_PURPOSES[:3]:
        store.put("consent", {"id": p["purpose"], "granted": granted})
    store.audit("you", "consent_given" if granted else "consent_withdrawn", "Reading documents, AI processing, sharing with insurer")
    return consents()


@app.get("/audit")
def audit():
    return store.find("audit")


@app.delete("/me/data")
def delete_my_data():
    store.wipe()
    ensure_profile()
    store.audit("you", "data_deleted", "All policies, claims, documents and chats deleted")
    return {"ok": True}


@app.post("/demo/reset")
def demo_reset():
    store.wipe()
    ensure_profile()
    return {"ok": True}


# ---------------- policies ----------------

def _add_policy(p: dict, source: str) -> dict:
    p = copy.deepcopy(p)
    p["source"] = source
    existing = store.get("policy", p["id"])
    if existing:
        return existing
    store.put("policy", p)
    store.audit("you", "policy_added", f"{p['plan']} ({p['insurer']}) added from {source}", p["id"])
    return p


@app.get("/policies")
def list_policies():
    return store.find("policy")


@app.get("/policies/paytm")
def paytm_policies():
    """Mock: policies bought through Paytm Insurance Broking for this user."""
    return [{"id": pid, "plan": SAMPLE_BY_ID[pid]["plan"], "insurer": SAMPLE_BY_ID[pid]["insurer"],
             "sum_insured": SAMPLE_BY_ID[pid]["sum_insured"], "policy_number": SAMPLE_BY_ID[pid]["policy_number"]} for pid in PAYTM_POLICIES]


@app.post("/policies/paytm/{pid}")
def import_paytm(pid: str):
    if pid not in PAYTM_POLICIES:
        raise HTTPException(404, "Not found")
    return _add_policy(SAMPLE_BY_ID[pid], "paytm")


class FetchIn(BaseModel):
    insurer: str
    policy_number: str


@app.post("/policies/fetch")
def fetch_policy(f: FetchIn):
    """Mock insurer lookup by policy number."""
    for p in SAMPLE_POLICIES:
        if p["policy_number"].replace(" ", "").upper() == f.policy_number.replace(" ", "").upper():
            return _add_policy(p, "insurer_fetch")
    raise HTTPException(404, "We couldn't find this policy with the insurer. Check the number on your e-card, or upload the policy PDF.")


@app.post("/policies/upload")
async def upload_policy(file: UploadFile = File(...)):
    data = await file.read()
    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/pdf"
    try:
        parsed = tools.parse_policy(data, mime)
    except SarvamError as e:
        raise HTTPException(502, f"Couldn't read the policy: {e}")
    except Exception as e:
        raise HTTPException(422, f"Couldn't read this file: {e}")
    pid = store.new_id("pol")
    members = []
    for i, m in enumerate(parsed.get("members") or [{"name": "Policyholder", "relation": "Self"}]):
        members.append({"id": f"m{i}_{pid[-4:]}", "name": m.get("name") or "Member", "relation": m.get("relation") or "Self",
                        "age": m.get("age"), "gender": m.get("gender"), "ped": m.get("ped") or []})
    p = {
        "id": pid, "source": "upload", "filename": file.filename,
        "insurer": parsed.get("insurer") or "Unknown insurer", "plan": parsed.get("plan") or "Health policy",
        "policy_number": parsed.get("policy_number"), "type": parsed.get("type") or "individual",
        "sum_insured": float(parsed.get("sum_insured") or 0), "start_date": parsed.get("start_date"), "end_date": parsed.get("end_date"),
        "members": members, "room_rent": parsed.get("room_rent") or {"type": "none"}, "icu_rent": parsed.get("icu_rent") or {"type": "none"},
        "copay": parsed.get("copay") or {"percent": 0}, "deductible": parsed.get("deductible") or 0,
        "consumables_cover": bool(parsed.get("consumables_cover")), "waiting": parsed.get("waiting") or {},
        "sub_limits": parsed.get("sub_limits") or [], "exclusions": parsed.get("exclusions") or [],
        "pre_hosp_days": parsed.get("pre_hosp_days") or 30, "post_hosp_days": parsed.get("post_hosp_days") or 60,
        "intimation": parsed.get("intimation") or {"emergency_hours": 24, "planned_hours": 48},
        "submission_days": parsed.get("submission_days") or 30, "clauses": parsed.get("clauses") or [],
        "confidence": parsed.get("confidence") or {}, "needs_review": parsed.get("needs_review") or [],
    }
    p["remaining_si"] = p["sum_insured"]
    if len(p["needs_review"]) >= POLICY_REVIEW_FIELDS or not p["sum_insured"]:
        p["review_ticket"] = flag_for_review("Low-confidence policy read", f"{file.filename}: {len(p['needs_review'])} fields uncertain" + ("; sum insured not found" if not p["sum_insured"] else ""), None, pid)["id"]
    store.put("policy", p)
    store.audit("ai", "policy_parsed", f"Read {file.filename} and extracted {len(p['clauses'])} clauses; {len(p['needs_review'])} fields need your check", pid)
    return p


@app.get("/policies/{pid}")
def get_policy(pid: str):
    return must("policy", pid)


class PolicyPatch(BaseModel):
    updates: dict


@app.patch("/policies/{pid}")
def patch_policy(pid: str, body: PolicyPatch):
    p = must("policy", pid)
    p.update(body.updates)
    p["needs_review"] = [f for f in p.get("needs_review", []) if f not in body.updates]
    store.audit("you", "policy_corrected", f"Corrected {', '.join(body.updates)}", pid)
    return store.put("policy", p)


@app.delete("/policies/{pid}")
def delete_policy(pid: str):
    store.delete("policy", pid)
    return {"ok": True}


@app.get("/policies/{pid}/explainer")
def explainer(pid: str, lang: str = "en-IN"):
    p = must("policy", pid)
    topics = tools.explainer_template(p)
    if not lang.startswith("en"):
        topics = tools.localise_topics(topics, lang)
        store.audit("ai", "translated", f"Policy summary translated to {config.LANG_NAME.get(lang, lang)}", pid)
    cap = engine.room_cap_per_day(p)
    return {"policy_id": pid, "lang": lang, "topics": topics,
            "highlights": {"sum_insured": p["sum_insured"], "room_cap_per_day": cap, "copay_percent": (p.get("copay") or {}).get("percent", 0),
                           "members": len(p.get("members", []))}}


# ---------------- hospital stay check ----------------

class HospitalCheckIn(BaseModel):
    policy_id: str
    facts: dict
    lang: str = "en-IN"


@app.post("/hospital/check")
def hospital_check(body: HospitalCheckIn):
    p = must("policy", body.policy_id)
    facts = dict(body.facts)
    for k in ("room_rent_per_day", "expected_days", "estimated_bill"):
        if facts.get(k) not in (None, ""):
            try:
                facts[k] = float(facts[k])
            except (TypeError, ValueError):
                facts[k] = None
    result = engine.hospital_check(p, facts)
    result["summary"] = tools.summarise_check(p, result, body.lang) if sarvam.available() else None
    store.audit("rules", "hospital_check", "Checked hospital stay against the policy", p["id"], {"facts": facts})
    return result


class HospitalChatIn(BaseModel):
    policy_id: str
    messages: list[dict]
    facts: dict = {}
    lang: str = "en-IN"


@app.post("/hospital/chat")
def hospital_chat(body: HospitalChatIn):
    p = must("policy", body.policy_id)
    try:
        out = tools.hospital_chat(p, body.messages, body.facts, body.lang)
    except SarvamError as e:
        raise HTTPException(502, str(e))
    if out["ready"]:
        out["check"] = engine.hospital_check(p, {k: (float(v) if k in ("room_rent_per_day", "expected_days", "estimated_bill") and v not in (None, "") else v)
                                                 for k, v in out["facts"].items()})
        if out.pop("forced", False):  # the model was still asking questions, but we already know enough: lead with the result
            out["reply"] = tools.summarise_check(p, out["check"], body.lang)
        store.audit("ai", "hospital_chat", "Collected stay details by conversation and ran the policy check", p["id"], {"facts": out["facts"]})
    return out


@app.post("/hospital/bill")
async def hospital_bill(policy_id: str = Form(...), file: UploadFile = File(...)):
    """Optional: read an interim bill / estimate photo into facts."""
    p = must("policy", policy_id)
    data = await file.read()
    mime = file.content_type or "image/jpeg"
    try:
        doc = tools.extract_document(data, mime, file.filename or "bill")
    except SarvamError as e:
        raise HTTPException(502, str(e))
    facts = {k: doc.get(k) for k in ("room_category", "room_rent_per_day", "diagnosis", "procedure", "admission_date") if doc.get(k)}
    if doc.get("total_amount"):
        facts["estimated_bill"] = doc["total_amount"]
    store.audit("ai", "document_read", "Read interim bill for hospital check", p["id"])
    return {"facts": facts, "document": doc}


# ---------------- claims ----------------

class ClaimIn(BaseModel):
    policy_id: str
    member_id: str | None = None
    claim_type: str = "reimbursement"


@app.post("/claims")
def create_claim(body: ClaimIn):
    p = must("policy", body.policy_id)
    c = {"id": store.new_id("clm"), "policy_id": p["id"], "member_id": body.member_id or p["members"][0]["id"],
         "claim_type": body.claim_type, "status": "draft", "form": {}, "fill_mode": None, "timeline": [], "tasks": [], "appeals": []}
    C.timeline_add(c, "draft", "Claim started")
    store.put("claim", c)
    return c


def claim_view(c: dict) -> dict:
    p = store.get("policy", c["policy_id"])
    out = dict(c)
    out["policy"] = {k: p.get(k) for k in ("id", "insurer", "plan", "policy_number", "sum_insured", "members")} if p else None
    out["documents"] = store.find("document", claim_id=c["id"])
    out["checklist"] = C.checklist(c)
    out["appeal_pending"] = bool(C.pending_appeal(c))
    if p:
        out["deadlines"] = C.deadlines(c, p)
        out["bridge_offer"] = C.bridge_offer(c, p) if not c.get("bridge") else None
    return out


@app.get("/claims")
def list_claims():
    return [claim_view(c) for c in store.find("claim")]


@app.get("/claims/{cid}")
def get_claim(cid: str):
    return claim_view(must("claim", cid))


@app.delete("/claims/{cid}")
def delete_claim(cid: str):
    c = store.get("claim", cid)
    if c and c.get("settled_on") and c.get("decision"):
        p = store.get("policy", c["policy_id"])
        if p:  # give back the cover this claim used up
            p["remaining_si"] = min(float(p["sum_insured"]), float(p.get("remaining_si", p["sum_insured"])) + float(c["decision"]["amount_approved"] or 0))
            store.put("policy", p)
    store.delete("claim", cid)
    store.delete("thread", memory.thread_id(cid, None))
    return {"ok": True}


@app.post("/claims/{cid}/documents")
async def upload_document(cid: str, file: UploadFile = File(...)):
    c = must("claim", cid)
    data = await file.read()
    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "image/jpeg"
    did = store.new_id("doc")
    ext = mimetypes.guess_extension(mime) or ""
    path = config.UPLOAD_DIR / f"{did}{ext}"
    path.write_bytes(data)
    try:
        fields = tools.extract_document(data, mime, file.filename or "document")
        error = None
    except Exception as e:
        fields, error = {"doc_type": "other", "confidence": 0, "summary": "We couldn't read this file automatically."}, str(e)
    d = {"id": did, "claim_id": cid, "filename": file.filename, "mime": mime, "url": f"/files/{path.name}",
         "doc_type": fields.get("doc_type", "other"), "fields": fields, "confidence": fields.get("confidence", 0), "error": error}
    if error or float(d["confidence"] or 0) < REVIEW_BELOW:
        d["review_ticket"] = flag_for_review("Low-confidence document read", f"{file.filename} was read at {int(float(d['confidence'] or 0) * 100)}% confidence", cid, did)["id"]
    store.put("document", d)
    store.audit("ai", "document_read", f"Read {file.filename}: {d['doc_type'].replace('_', ' ')} ({int(float(d['confidence'] or 0) * 100)}% confidence)", cid)
    if c["status"] == "draft":
        C.timeline_add(c, "documents_pending", "Documents being added")
        store.put("claim", c)
    return d


class DocTypeIn(BaseModel):
    doc_type: str


@app.patch("/documents/{did}")
def set_doc_type(did: str, body: DocTypeIn):
    d = must("document", did)
    d["doc_type"] = body.doc_type
    return store.put("document", d)


@app.delete("/documents/{did}")
def delete_document(did: str):
    store.delete("document", did)
    return {"ok": True}


class FillModeIn(BaseModel):
    mode: str  # "ai" | "manual"


@app.post("/claims/{cid}/fill-mode")
def set_fill_mode(cid: str, body: FillModeIn):
    c = must("claim", cid)
    p = must("policy", c["policy_id"])
    c["fill_mode"] = body.mode
    if body.mode == "ai":
        filled = C.autofill(c, p)
        c["form"] = {**c.get("form", {}), **filled["values"]}
        c["form_sources"] = filled["sources"]
        store.audit("you", "consent_given", "Allowed Claimezy to fill the claim form from your documents", cid)
        store.audit("ai", "form_filled", f"Filled {len(filled['values'])} fields from your documents and policy", cid, {"fields": list(filled["values"])})
    else:
        c["form_sources"] = {}
        store.audit("you", "fill_manual", "Chose to fill the claim form yourself", cid)
    store.put("claim", c)
    return {"form": c["form"], "sources": c.get("form_sources", {}), "corrections": C.validate(c, p, c["form"])}


class FormIn(BaseModel):
    form: dict


@app.get("/claims/{cid}/form.pdf")
def form_pdf(cid: str):
    """The claim form as a PDF, built from the saved form."""
    from fastapi import Response
    from . import formpdf
    c = must("claim", cid)
    p = must("policy", c["policy_id"])
    store.audit("you", "form_exported", "Exported the claim form as PDF", cid)
    return Response(formpdf.build(c, p), media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="claim-form-{cid}.pdf"'})


@app.post("/claims/{cid}/validate")
def validate_form(cid: str, body: FormIn):
    c = must("claim", cid)
    p = must("policy", c["policy_id"])
    c["form"] = body.form
    store.put("claim", c)
    return {"corrections": C.validate(c, p, body.form)}


@app.post("/claims/{cid}/preflight")
def preflight(cid: str, body: FormIn | None = None):
    c = must("claim", cid)
    p = must("policy", c["policy_id"])
    if body:
        c["form"] = body.form
    c["preflight"] = C.preflight(c, p)
    if c["status"] in ("draft", "documents_pending"):
        C.timeline_add(c, "ready", "Ready to submit", f"Estimated payout ₹{c['preflight']['payable']:,.0f}")
    store.put("claim", c)
    store.audit("rules", "preflight", f"Estimated payout ₹{c['preflight']['payable']:,.0f} of ₹{c['preflight']['billed']:,.0f}", cid)
    return c["preflight"]


@app.post("/claims/{cid}/submit")
def submit(cid: str):
    c = must("claim", cid)
    p = must("policy", c["policy_id"])
    if c.get("insurer_ref"):
        raise HTTPException(409, "This claim has already been submitted.")
    errs = [x for x in C.validate(c, p, c.get("form", {})) if x["severity"] in ("error", "required")]
    if errs:
        raise HTTPException(422, {"message": "Fix the highlighted fields first.", "corrections": errs})
    if not any(x["granted"] for x in consents() if x["purpose"] == "share_insurer"):
        store.put("consent", {"id": "share_insurer", "granted": True})
        store.audit("you", "consent_given", "Share my claim with my insurer", cid)
    C.submit(c, p)
    store.put("claim", c)
    return claim_view(c)


@app.post("/claims/{cid}/advance")
def advance(cid: str):
    """Demo control: move the mock insurer to its next step."""
    c = must("claim", cid)
    p = must("policy", c["policy_id"])
    C.advance(c, p)
    store.put("claim", c)
    return claim_view(c)


class TaskReply(BaseModel):
    note: str = "Documents uploaded"


@app.post("/claims/{cid}/tasks/{tid}")
def reply_task(cid: str, tid: str, body: TaskReply):
    c = must("claim", cid)
    task = next((t for t in c.get("tasks", []) if t["id"] == tid), None)
    if not task:
        raise HTTPException(404, "task not found")
    if task["status"] != "open":
        raise HTTPException(409, "This query has already been answered.")
    C.respond_task(c, tid, body.note)
    store.put("claim", c)
    store.audit("you", "query_answered", body.note, cid)
    return claim_view(c)


@app.post("/claims/{cid}/intimate")
def intimate(cid: str):
    c = must("claim", cid)
    p = must("policy", c["policy_id"])
    c["intimated"] = True
    c["intimation_ref"] = f"INT{c['id'][-6:].upper()}"
    c.setdefault("form", {})["intimation_done"] = True
    C.timeline_add(c, c["status"] if c["status"] != "draft" else "intimated", "Insurer informed", f"Intimation reference {c['intimation_ref']} (mock)")
    store.put("claim", c)
    store.audit("you", "intimation_sent", f"Informed {p['insurer']} about the hospitalisation", cid)
    return claim_view(c)


def _localise(text: str, lang: str) -> str:
    """Rule-written text in the user's language. If translation is down they still get it in English."""
    try:
        return sarvam.translate(text, lang)
    except SarvamError:
        return text


@app.get("/claims/{cid}/decision")
def decision(cid: str, lang: str = "en-IN"):
    c = must("claim", cid)
    p = must("policy", c["policy_id"])
    if not c.get("decision"):
        raise HTTPException(404, "No decision yet")
    analysis = C.analyse_decision(c, p)
    text = tools.explain_decision(p, c, analysis, lang)
    store.audit("ai", "decision_explained", f"Explained the insurer's decision in {config.LANG_NAME.get(lang, lang)}", cid)
    unexplained = analysis["strength"] == "none" and abs((c["decision"].get("amount_approved") or 0) - analysis["expected_payable"]) > 1
    if unexplained and not c.get("explain_review_ticket"):
        c["explain_review_ticket"] = flag_for_review("Decision we could not fully explain", "The insurer's amount differs from the rule engine and no cause was found", cid)["id"]
        store.put("claim", c)
    ladder = C.ladder(c)
    for rung in ladder:
        if rung["reply"]:
            rung["reply"] = {**rung["reply"], "text": _localise(rung["reply"]["text"], lang)}
    return {"decision": c["decision"], "analysis": analysis, "explanation": text, "ladder": ladder, "lang": lang, "review_ticket": c.get("explain_review_ticket")}


class AppealIn(BaseModel):
    step: str
    lang: str = "en-IN"
    text: str | None = None


def _appeal_claim(cid: str, step: str) -> dict:
    c = must("claim", cid)
    if step not in ("insurer", "gro", "bima_bharosa", "ombudsman"):
        raise HTTPException(422, "Unknown escalation step.")
    if not c.get("decision"):
        raise HTTPException(409, "There is no insurer decision to appeal yet.")
    return c


@app.post("/claims/{cid}/appeal/draft")
def appeal_draft(cid: str, body: AppealIn):
    c = _appeal_claim(cid, body.step)
    p = must("policy", c["policy_id"])
    analysis = C.analyse_decision(c, p)
    member = next((m for m in p["members"] if m["id"] == c.get("form", {}).get("member_id", c["member_id"])), p["members"][0])
    text = tools.draft_appeal(p, c, analysis, body.step, body.lang, member)
    store.audit("ai", "appeal_drafted", f"Drafted {body.step.replace('_', ' ')} letter", cid)
    prof = store.get("profile", "me") or {}
    return {"step": body.step, "text": text, "ombudsman": find_office(prof.get("pincode", "")) if body.step == "ombudsman" else None}


@app.post("/claims/{cid}/appeal/send")
def appeal_send(cid: str, body: AppealIn):
    c = _appeal_claim(cid, body.step)
    rung = next(r for r in C.ladder(c) if r["step"] == body.step)
    if rung["status"] != "available":
        raise HTTPException(409, "Already sent." if rung["status"] == "sent" else "Finish the earlier step first.")
    c.setdefault("appeals", []).append({"step": body.step, "text": body.text, "sent_at": store.now(), "ref": store.new_id("grv")})
    C.timeline_add(c, c["status"], {"insurer": "Review request sent to insurer", "gro": "Grievance filed with insurer",
                                     "bima_bharosa": "Complaint filed on Bima Bharosa", "ombudsman": "Complaint sent to Insurance Ombudsman"}[body.step],
                   "Sent (mock). You'll be notified of the reply.")
    store.put("claim", c)
    store.audit("you", "appeal_sent", f"Sent {body.step.replace('_', ' ')} letter", cid)
    return {"ladder": C.ladder(c)}


@app.post("/claims/{cid}/appeal/dismiss")
def appeal_dismiss(cid: str):
    c = must("claim", cid)
    c["appeal_dismissed"] = True
    store.put("claim", c)
    return claim_view(c)


@app.get("/ombudsman")
def ombudsman(pincode: str):
    return find_office(pincode)


@app.get("/claims/{cid}/fhir")
def fhir(cid: str):
    c = must("claim", cid)
    p = must("policy", c["policy_id"])
    if not c.get("form"):
        raise HTTPException(409, "Fill the claim form before exporting the claim pack.")
    store.audit("you", "fhir_exported", "Exported NHCX claim bundle", cid)
    return C.fhir_bundle(c, p)


# ---------------- bridge + UPI (mock partners) ----------------

@app.get("/claims/{cid}/bridge")
def bridge(cid: str):
    c = must("claim", cid)
    p = must("policy", c["policy_id"])
    offer = C.bridge_offer(c, p)
    if not offer:
        raise HTTPException(404, "No offer available right now")
    return offer


class BridgeAcceptIn(BaseModel):
    consent: bool = False  # explicit consent to share claim status with the lender (RBI Digital Lending Directions)


@app.post("/claims/{cid}/bridge/accept")
def bridge_accept(cid: str, body: BridgeAcceptIn):
    if not body.consent:
        raise HTTPException(422, "Please confirm you have read the Key Facts and agree to share your claim status with the lender.")
    c = must("claim", cid)
    if c.get("bridge"):
        raise HTTPException(409, "You already have a loan on this claim.")
    p = must("policy", c["policy_id"])
    offer = C.bridge_offer(c, p)
    if not offer:
        raise HTTPException(404, "No offer available")
    store.put("consent", {"id": "share_lender", "granted": True})
    store.audit("you", "consent_given", f"Shared claim status with {C.LENDER} for a loan", cid)
    decision = {"approved": True, "loan_id": store.new_id("loan"), "decided_by": C.LENDER, "decided_at": store.now()}
    c["bridge"] = {**offer, **decision, "status": "active", "cooling_off_until": str(date.today().fromordinal(date.today().toordinal() + offer["cooling_off_days"]))}
    C.timeline_add(c, c["status"], f"Bridge loan of ₹{offer['principal']:,.0f} credited", f"Lender: {C.LENDER}. Cancel free until {c['bridge']['cooling_off_until']}.")
    store.put("claim", c)
    return claim_view(c)


class UpiIn(BaseModel):
    amount: float
    payee: str
    note: str = ""
    claim_id: str | None = None


@app.post("/mock/upi/pay")
def upi_pay(body: UpiIn):
    if body.amount <= 0:
        raise HTTPException(422, "Enter an amount above ₹0.")
    if body.claim_id:
        must("claim", body.claim_id)
    txn = {"id": store.new_id("upi"), "amount": body.amount, "payee": body.payee, "note": body.note, "status": "SUCCESS",
           "utr": f"6{store.new_id('x')[-11:].upper()}", "claim_id": body.claim_id}
    store.put("payment", txn)
    if body.claim_id and store.get("claim", body.claim_id):
        c = store.get("claim", body.claim_id)
        C.timeline_add(c, c["status"], f"Paid ₹{body.amount:,.0f} to {body.payee} via UPI", f"UTR {txn['utr']}. Receipt attached to this claim.")
        store.put("claim", c)
    return txn


# ---------------- assistant ----------------

class AssistantIn(BaseModel):
    message: str | None = None        # the new message; history comes from the saved thread
    attachment: str | None = None     # text read from a screenshot or PDF, for the model only
    attachment_name: str | None = None  # PDF file name, shown on the saved message
    messages: list[dict] = []         # older clients send the whole history instead
    lang: str = "en-IN"
    screen: str | None = None
    policy_id: str | None = None
    claim_id: str | None = None


@app.post("/assistant/chat")
def assistant_chat(body: AssistantIn):
    ctx = {"screen": body.screen, "today": str(date.today())}
    thread = memory.load(memory.thread_id(body.claim_id, body.policy_id))
    if thread["summary"]:
        ctx["earlier_conversation_summary"] = thread["summary"]
    back = memory.returning_since(thread)
    if back:
        ctx["previous_session_ended"] = back
    policies = store.find("policy")
    p = store.get("policy", body.policy_id) if body.policy_id else (policies[0] if policies else None)
    if body.claim_id:
        c = store.get("claim", body.claim_id)
        if c:
            p = store.get("policy", c["policy_id"]) or p
            ctx["claim"] = {k: c.get(k) for k in ("status", "claim_type", "form", "insurer_ref", "timeline", "tasks", "decision", "bridge")}
            ctx["claim"]["preflight"] = c.get("preflight")
            if c.get("decision") and p:
                ctx["claim"]["rule_engine_review"] = C.analyse_decision(c, p)
            if p:
                ctx["claim"]["next_step"] = C.next_step(c, p)
    if p:
        ctx["policy"] = tools.policy_context(p)
    else:
        ctx["policy"] = "No policy added yet. Guide the user to add one from My Policies."
    if body.message is not None:
        said = body.message
        ask = f"{said}\n\nATTACHMENT (text read from the screenshot/document):\n{body.attachment}" if body.attachment else said
        history = memory.history_for_model(thread, ask)
    else:
        history = body.messages
        said = next((m["content"] for m in reversed(history) if m.get("role") == "user"), "")
    try:
        reply = tools.assistant(history, body.lang, ctx)
    except SarvamError as e:
        raise HTTPException(502, str(e))  # nothing is saved, so the user can simply ask again
    memory.append(thread, "user", said, image=bool(body.attachment) and not body.attachment_name, file=body.attachment_name, attachment=body.attachment)
    memory.append(thread, "assistant", reply)
    older = memory.pending_summary(thread)
    if older:
        thread["summary"] = tools.summarise_conversation(older[thread.get("summary_n", 0):], thread["summary"])
        thread["summary_n"] = len(older)
    memory.save(thread)
    store.audit("ai", "assistant_reply", f"Answered a question on {body.screen or 'the app'}", body.claim_id or body.policy_id)
    return {"reply": reply}


def _recap_fresh(t: dict, lang: str) -> bool:
    return t.get("recap_n") == len(t["messages"]) and t.get("recap_lang") == lang


@app.get("/assistant/thread")
def assistant_thread(claim_id: str | None = None, policy_id: str | None = None, lang: str = "en-IN"):
    """The saved conversation and the next step from the claim's state. Fast: no AI call here.

    The recap is returned only if one is already cached; otherwise recap_pending tells the app to fetch it
    from /assistant/thread/recap, so the chat shows at once and the recap fills in after.
    """
    t = memory.load(memory.thread_id(claim_id, policy_id))
    c = store.get("claim", claim_id) if claim_id else None
    p = store.get("policy", c["policy_id"]) if c else None
    next_step_en = C.next_step(c, p) if c and p else None
    next_step = _localise(next_step_en, lang) if next_step_en else None
    if not t["messages"]:
        return {"id": t["id"], "messages": [], "recap": None, "recap_pending": False, "next_step": next_step, "last_at": None}
    fresh = _recap_fresh(t, lang)
    return {"id": t["id"], "messages": t["messages"], "recap": t["recap"] if fresh else None, "recap_pending": not fresh,
            "next_step": next_step, "last_at": t["messages"][-1]["at"]}


@app.get("/assistant/thread/recap")
def assistant_recap(claim_id: str | None = None, policy_id: str | None = None, lang: str = "en-IN"):
    """AI-written "where we left off", cached until the conversation moves or the language changes."""
    t = memory.load(memory.thread_id(claim_id, policy_id))
    if not t["messages"]:
        return {"recap": None}
    if not _recap_fresh(t, lang):
        c = store.get("claim", claim_id) if claim_id else None
        p = store.get("policy", c["policy_id"]) if c else None
        next_step_en = C.next_step(c, p) if c and p else None
        t.update(recap=tools.recap_conversation(t["messages"], t["summary"], lang, next_step_en), recap_n=len(t["messages"]), recap_lang=lang)
        memory.save(t)
    return {"recap": t["recap"]}


@app.delete("/assistant/thread")
def clear_thread(claim_id: str | None = None, policy_id: str | None = None):
    store.delete("thread", memory.thread_id(claim_id, policy_id))
    store.audit("you", "chat_cleared", "Cleared a saved assistant conversation", claim_id or policy_id)
    return {"ok": True}


@app.post("/assistant/attach")
async def assistant_attach(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(422, "The file is empty.")
    name = file.filename or ""
    is_pdf = data[:5] == b"%PDF-" or name.lower().endswith(".pdf") or file.content_type == "application/pdf"
    mime = "application/pdf" if is_pdf else (file.content_type if (file.content_type or "").startswith("image/") else "image/jpeg")
    try:
        text = tools.describe_attachment(data, mime)
    except SarvamError as e:
        raise HTTPException(502, str(e))
    except Exception as e:
        raise HTTPException(422, f"Couldn't open this file: {e}")
    store.audit("ai", "attachment_read", f"Read shared {'PDF' if is_pdf else 'screenshot'} {name}")
    return {"text": text, "kind": "pdf" if is_pdf else "image", "filename": name}


@app.post("/assistant/stt")
async def assistant_stt(file: UploadFile = File(...), lang: str = Form("auto")):
    data = await file.read()
    try:
        out = sarvam.stt(data, file.filename or "audio.m4a", None if lang == "auto" else lang)
    except SarvamError as e:
        raise HTTPException(502, str(e))
    return out


class TtsIn(BaseModel):
    text: str
    lang: str = "hi-IN"


@app.post("/assistant/tts")
def assistant_tts(body: TtsIn):
    lang = body.lang if any(l["code"] == body.lang and l["tts"] for l in config.LANGUAGES) else "en-IN"
    try:
        return sarvam.tts(body.text, lang)
    except SarvamError as e:
        raise HTTPException(502, str(e))


@app.get("/assistant/tts.wav")
def assistant_tts_wav(text: str, lang: str = "hi-IN"):
    """Audio as a plain URL so the app can stream it straight into an audio player."""
    import base64
    from fastapi import Response
    out = assistant_tts(TtsIn(text=text, lang=lang))
    return Response(base64.b64decode(out["audio_base64"]), media_type="audio/wav")


REVIEW_BELOW = 0.6  # extraction confidence under this goes to a person
POLICY_REVIEW_FIELDS = 6  # a clean policy read still leaves a few uncertain fields (5 in testing); this many means the read is poor


def flag_for_review(topic: str, reason: str, claim_id: str | None = None, ref: str | None = None) -> dict:
    """Low-confidence AI output is never left to the user alone: open a human-review ticket and log it."""
    t = {"id": store.new_id("tkt"), "topic": topic, "messages": [], "claim_id": claim_id, "status": "open", "auto": True,
         "reason": reason, "ref": ref, "eta": "A claims expert will check this and call you within 2 hours (mock)."}
    store.put("ticket", t)
    store.audit("ai", "human_review_flagged", reason, claim_id or ref)
    return t


class TicketIn(BaseModel):
    topic: str
    messages: list[dict] = []
    claim_id: str | None = None


@app.post("/support/ticket")
def support_ticket(body: TicketIn):
    if body.claim_id:
        must("claim", body.claim_id)
    t = {"id": store.new_id("tkt"), "topic": body.topic, "messages": body.messages[-20:], "claim_id": body.claim_id, "status": "open",
         "eta": "A claims expert from Paytm Insurance will call you within 2 hours (mock)."}
    store.put("ticket", t)
    store.audit("you", "human_handoff", f"Asked for a human: {body.topic}", body.claim_id)
    return t


# ---------------- guided sample claims ----------------

@app.get("/samples")
def samples():
    return [{"key": k, "title": v["title"], "policy_id": v["policy_id"], "member": next(m["name"] for m in SAMPLE_BY_ID[v["policy_id"]]["members"] if m["id"] == v["member_id"])}
            for k, v in SAMPLE_CLAIMS.items()]


@app.post("/samples/{key}/policy")
def sample_policy(key: str):
    s = SAMPLE_CLAIMS.get(key)
    if not s:
        raise HTTPException(404, "Unknown sample")
    return _add_policy(SAMPLE_BY_ID[s["policy_id"]], "sample")


@app.post("/mock/abha/fetch/{cid}")
def abha_fetch(cid: str):
    """Mock ABHA record fetch: clinical records only (discharge summary, prescriptions, lab reports). Bills and bank papers are not in ABHA."""
    c = must("claim", cid)
    key = next((k for k, v in SAMPLE_CLAIMS.items() if v["member_id"] == c["member_id"] and v["policy_id"] == c["policy_id"]), None)
    if not key:
        raise HTTPException(404, "No health records are linked to this ABHA address yet (demo). Upload the papers instead.")
    s = SAMPLE_CLAIMS[key]
    p = must("policy", c["policy_id"])
    member = next(m for m in p["members"] if m["id"] == s["member_id"])
    common = {"patient_name": member["name"], "hospital": s["hospital"], "admission_date": s["admission_date"], "discharge_date": s["discharge_date"]}
    have = {d["doc_type"] for d in store.find("document", claim_id=cid)}
    docs = [
        ("discharge_summary", "ABHA_Discharge_summary.pdf", {**common, "diagnosis": s["diagnosis"], "procedure": s["procedure"], "room_category": s["room_category"],
                                                           "summary": f"Discharge summary for {member['name']}: {s['diagnosis']}, {s['procedure']}."}),
        ("prescription", "ABHA_Prescriptions.pdf", {**common, "summary": "Prescriptions from your ABHA records."}),
        ("investigation_report", "ABHA_Lab_reports.pdf", {**common, "summary": "Lab and imaging reports from your ABHA records."}),
    ]
    added = []
    for dt, fn, fields in docs:
        if dt in have:
            continue
        d = {"id": store.new_id("doc"), "claim_id": cid, "filename": fn, "mime": "application/pdf", "url": None, "source": "ABHA",
             "doc_type": dt, "fields": {"doc_type": dt, "confidence": 0.95, **fields}, "confidence": 0.95}
        store.put("document", d)
        added.append(fn)
    store.audit("you", "abha_fetch", f"Fetched {len(added)} records from ABHA with your consent (mock)", cid)
    return {"added": added, "message": f"Fetched {len(added)} records from your ABHA." if added else "Everything in your ABHA is already attached."}


@app.post("/samples/{key}/documents/{cid}")
def sample_documents(key: str, cid: str):
    """Attach synthetic, pre-read documents for a sample claim (instead of photographing real ones)."""
    s = SAMPLE_CLAIMS[key]
    c = must("claim", cid)
    p = must("policy", c["policy_id"])
    member = next(m for m in p["members"] if m["id"] == s["member_id"])
    c["member_id"] = s["member_id"]
    c["insurer_behaviour"] = s["insurer_behaviour"]
    days = s["room_days"]
    room_line = next((i for i in s["line_items"] if i["category"] == "room"), None)
    common = {"patient_name": member["name"], "hospital": s["hospital"], "admission_date": s["admission_date"], "discharge_date": s["discharge_date"]}
    docs = [
        ("discharge_summary", "Discharge_summary.pdf", {**common, "diagnosis": s["diagnosis"], "procedure": s["procedure"], "room_category": s["room_category"],
                                                        "summary": f"Discharge summary for {member['name']}: {s['diagnosis']}, {s['procedure']}."}),
        ("final_bill", "Final_bill.pdf", {**common, "room_category": s["room_category"], "room_days": days,
                                          "room_rent_per_day": room_line["amount"] / days if room_line else None,
                                          "line_items": s["line_items"], "total_amount": sum(i["amount"] for i in s["line_items"]),
                                          "summary": f"Itemised final bill with {len(s['line_items'])} lines."}),
        ("payment_receipt", "Payment_receipt.jpg", {**common, "total_amount": sum(i["amount"] for i in s["line_items"]), "summary": "Hospital payment receipt."}),
        ("prescription", "Prescriptions.pdf", {**common, "summary": "Prescriptions and pharmacy bills."}),
        ("investigation_report", "Lab_reports.pdf", {**common, "summary": "Lab and imaging reports."}),
        ("cancelled_cheque", "Cancelled_cheque.jpg", {"bank": {**s["bank"]}, "summary": "Cancelled cheque."}),
        ("id_proof", "Aadhaar_masked.jpg", {"patient_name": member["name"], "summary": "Masked Aadhaar card."}),
    ]
    for dt, fn, fields in docs:
        store.put("document", {"id": store.new_id("doc"), "claim_id": cid, "filename": fn, "mime": "application/pdf", "url": None, "sample": True,
                               "doc_type": dt, "fields": {"doc_type": dt, "confidence": 0.96, **fields}, "confidence": 0.96})
    prof = store.get("profile", "me")
    prof.update({"mobile": s["mobile"], "email": s["email"]})
    store.put("profile", prof)
    if c["status"] == "draft":
        C.timeline_add(c, "documents_pending", "Documents added")
    store.put("claim", c)
    store.audit("ai", "document_read", f"Read {len(docs)} sample documents for {member['name']}", cid)
    return claim_view(c)
