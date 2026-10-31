"""Claim workflow: checklist, form fill + live checks, mock insurer, decision analysis, bridge, FHIR."""

from __future__ import annotations

import difflib
import re
from datetime import date, datetime, timedelta

from . import store
from .config import BANK_RATE
from .rules import engine

STATUSES = ["draft", "intimated", "documents_pending", "ready", "submitted", "query_raised", "under_review",
            "approved", "partially_approved", "rejected", "settled"]

REQUIRED_DOCS = {
    "reimbursement": [
        ("discharge_summary", "Discharge summary"),
        ("final_bill", "Final itemised hospital bill"),
        ("payment_receipt", "Payment receipts"),
        ("prescription", "Prescriptions and pharmacy bills"),
        ("investigation_report", "Investigation reports"),
        ("cancelled_cheque", "Cancelled cheque or bank details"),
        ("id_proof", "Photo ID of the patient"),
    ],
    "cashless": [
        ("id_proof", "Photo ID and policy e-card"),
        ("discharge_summary", "Discharge summary"),
        ("final_bill", "Final itemised bill"),
    ],
}
DOC_ALIASES = {"itemised_bill": "final_bill", "pharmacy_bill": "prescription", "interim_bill": "final_bill"}

FORM_FIELDS = [
    ("policy_number", "Policy number"), ("member_id", "Patient (insured member)"), ("mobile", "Mobile number"),
    ("email", "Email"), ("pincode", "PIN code"), ("hospital_name", "Hospital name"), ("admission_date", "Date of admission"),
    ("discharge_date", "Date of discharge"), ("diagnosis", "Diagnosis"), ("procedure", "Treatment / procedure"),
    ("is_accident", "Was it an accident?"), ("room_category", "Room category"), ("room_rent_per_day", "Room rent per day (₹)"),
    ("room_days", "Days in room"), ("total_claimed", "Total amount claimed (₹)"), ("intimation_done", "Insurer informed?"),
    ("account_name", "Account holder name"), ("account_number", "Bank account number"), ("ifsc", "IFSC code"),
]


def checklist(claim: dict) -> list[dict]:
    docs = store.find("document", claim_id=claim["id"])
    have = {DOC_ALIASES.get(d.get("doc_type"), d.get("doc_type")) for d in docs}
    return [{"type": t, "label": label, "done": t in have} for t, label in REQUIRED_DOCS.get(claim["claim_type"], REQUIRED_DOCS["reimbursement"])]


def _first(docs, *types, key):
    for t in types:
        for d in docs:
            if d.get("doc_type") == t and (d.get("fields") or {}).get(key) not in (None, "", []):
                return d["fields"][key], d
    return None, None


def autofill(claim: dict, policy: dict) -> dict:
    """Build the claim form from extracted documents + policy. Each value carries its source."""
    docs = store.find("document", claim_id=claim["id"])
    vals, src = {}, {}

    def setv(k, v, s):
        if v not in (None, "", []):
            vals[k], src[k] = v, s

    setv("policy_number", policy.get("policy_number"), "Policy")
    member = next((m for m in policy["members"] if m["id"] == claim.get("member_id")), None)
    name, d = _first(docs, "discharge_summary", "final_bill", "itemised_bill", key="patient_name")
    if not member and name:
        member = _match_member(policy, name)
    if member:
        setv("member_id", member["id"], "Discharge summary" if d else "Policy")
    for key in ("hospital", "admission_date", "discharge_date", "diagnosis", "procedure", "room_category", "room_rent_per_day", "room_days"):
        v, d = _first(docs, "discharge_summary", "final_bill", "itemised_bill", "interim_bill", key=key)
        setv("hospital_name" if key == "hospital" else key, v, _label(d))
    total, d = _first(docs, "final_bill", "itemised_bill", key="total_amount")
    if total is None:
        items = bill_items(claim)
        if items:
            total, d = sum(i["amount"] for i in items), {"doc_type": "final_bill"}
    setv("total_claimed", total, _label(d))
    bank, d = _first(docs, "cancelled_cheque", key="bank")
    if bank:
        setv("account_name", bank.get("account_name"), "Cancelled cheque")
        setv("account_number", bank.get("account_number"), "Cancelled cheque")
        setv("ifsc", bank.get("ifsc"), "Cancelled cheque")
    prof = store.get("profile", "me") or {}
    setv("mobile", prof.get("mobile"), "Paytm profile")
    setv("email", prof.get("email"), "Paytm profile")
    setv("pincode", prof.get("pincode"), "Paytm profile")
    vals.setdefault("is_accident", False)
    vals.setdefault("intimation_done", claim.get("intimated", False))
    return {"values": vals, "sources": src}


def _label(d):
    if not d:
        return None
    return {"discharge_summary": "Discharge summary", "final_bill": "Hospital bill", "itemised_bill": "Hospital bill",
            "interim_bill": "Interim bill"}.get(d.get("doc_type"), "Document")


def _match_member(policy, name):
    names = {m["name"].lower(): m for m in policy["members"]}
    best = difflib.get_close_matches(name.lower(), list(names), n=1, cutoff=0.6)
    return names[best[0]] if best else None


def bill_items(claim: dict) -> list[dict]:
    for t in ("final_bill", "itemised_bill"):
        for d in store.find("document", claim_id=claim["id"], doc_type=t):
            items = (d.get("fields") or {}).get("line_items") or []
            if items:
                return items
    return claim.get("line_items") or []


def _date(v):
    try:
        return datetime.fromisoformat(str(v)[:10]).date()
    except Exception:
        return None


def validate(claim: dict, policy: dict, form: dict) -> list[dict]:
    """Live corrections. Deterministic: rules + cross-check with extracted documents and policy."""
    out = []

    def add(field, severity, message, suggestion=None):
        out.append({"field": field, "severity": severity, "message": message, "suggestion": suggestion})

    docs = store.find("document", claim_id=claim["id"])
    today = date.today()
    adm, dis = _date(form.get("admission_date")), _date(form.get("discharge_date"))
    start, end = _date(policy.get("start_date")), _date(policy.get("end_date"))

    if form.get("policy_number") and policy.get("policy_number") and form["policy_number"].strip().upper() != policy["policy_number"].upper():
        add("policy_number", "error", "This does not match your policy number.", policy["policy_number"])
    if form.get("member_id") and not any(m["id"] == form["member_id"] for m in policy["members"]):
        add("member_id", "error", "This person is not insured under this policy.")
    for k, v in (("admission_date", adm), ("discharge_date", dis)):
        if form.get(k) and not v:
            add(k, "error", "Use the format YYYY-MM-DD.")
        elif v and v > today:
            add(k, "error", "This date is in the future.")
    if adm and dis and dis < adm:
        add("discharge_date", "error", "Discharge cannot be before admission.")
    if adm and start and adm < start:
        add("admission_date", "error", f"Your policy started on {start:%d %b %Y}. Admissions before that are not covered.")
    if adm and end and adm > end:
        add("admission_date", "error", f"Your policy ended on {end:%d %b %Y}.")

    # Cross-check with documents
    for key, label in (("admission_date", "admission date"), ("discharge_date", "discharge date"), ("hospital_name", "hospital name")):
        dv, d = _first(docs, "discharge_summary", "final_bill", "itemised_bill", key="hospital" if key == "hospital_name" else key)
        fv = form.get(key)
        if dv and fv and str(dv).strip().lower() != str(fv).strip().lower():
            if key == "hospital_name" and difflib.SequenceMatcher(None, str(dv).lower(), str(fv).lower()).ratio() > 0.8:
                continue
            add(key, "warning", f"Your {_label(d).lower()} says the {label} is {dv}.", dv)
    items = bill_items(claim)
    if items and form.get("total_claimed") not in (None, ""):
        bill_total = round(sum(float(i["amount"]) for i in items))
        try:
            claimed = float(form["total_claimed"])
            if abs(claimed - bill_total) > 1:
                add("total_claimed", "warning", f"Your bill adds up to ₹{bill_total:,.0f}.", bill_total)
            if claimed > float(policy.get("remaining_si", policy["sum_insured"])):
                add("total_claimed", "warning", f"This is more than the ₹{policy.get('remaining_si', policy['sum_insured']):,.0f} cover left this year.")
        except ValueError:
            add("total_claimed", "error", "Enter the amount as a number.")

    # Formats
    if form.get("mobile") and not re.fullmatch(r"[6-9]\d{9}", str(form["mobile"]).strip()):
        add("mobile", "error", "Enter a 10-digit Indian mobile number.")
    if form.get("email") and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(form["email"]).strip()):
        add("email", "error", "This email address looks incomplete.")
    if form.get("pincode") and not re.fullmatch(r"[1-9]\d{5}", str(form["pincode"]).strip()):
        add("pincode", "error", "PIN code has 6 digits.")
    if form.get("ifsc"):
        ifsc = str(form["ifsc"]).strip().upper()
        if not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", ifsc):
            fixed = ifsc.replace("O", "0") if len(ifsc) == 11 else None
            add("ifsc", "error", "IFSC is 11 characters: 4 letters, a zero, then 6 letters or digits.",
                fixed if fixed and re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", fixed) else None)
    if form.get("account_number") and not re.fullmatch(r"\d{9,18}", str(form["account_number"]).strip()):
        add("account_number", "error", "Account numbers have 9 to 18 digits.")
    if form.get("account_name") and form.get("member_id"):
        holder = str(form["account_name"]).lower()
        proposer = policy["members"][0]["name"].lower()
        m = next((m for m in policy["members"] if m["id"] == form["member_id"]), None)
        if m and holder not in (m["name"].lower(), proposer):
            add("account_name", "info", "Payouts usually go to the patient's or proposer's own account. Keep a cancelled cheque handy.")

    # Risk hints from the rule engine
    cap = engine.room_cap_per_day(policy)
    try:
        rent = float(form.get("room_rent_per_day") or 0)
    except ValueError:
        rent = 0
    if cap and rent > cap:
        add("room_rent_per_day", "warning", f"Above your limit of ₹{cap:,.0f}/day. Related charges will be cut to {cap / rent * 100:.0f}% (Clause {engine.clause(policy, 'room_rent')}).")
    if adm and not form.get("intimation_done") and (today - adm).days >= 1:
        add("intimation_done", "warning", "Insurers expect to be told within 24 hours of an emergency admission. Inform them now and keep the reference number.")
    if form.get("member_id") and adm:
        member = next((m for m in policy["members"] if m["id"] == form["member_id"]), None)
        if member:
            cond = f"{form.get('diagnosis', '')} {form.get('procedure', '')}"
            for w in engine.check_waiting_periods(policy, member, adm, cond, bool(form.get("is_accident"))):
                add("diagnosis", "warning", w["reason"] + (f" (Clause {w['clause_id']})" if w.get("clause_id") else ""))
    required = ["policy_number", "member_id", "hospital_name", "admission_date", "discharge_date", "diagnosis", "total_claimed",
                "account_number", "ifsc", "mobile"]
    for k in required:
        if form.get(k) in (None, ""):
            add(k, "required", "Required to submit.")
    return out


def claim_input(claim: dict, policy: dict) -> dict:
    f = claim.get("form") or {}
    items = bill_items(claim)
    if not items and f.get("total_claimed"):
        items = [{"name": "Hospitalisation (total, not itemised)", "category": "misc", "amount": float(f["total_claimed"])}]
    days = f.get("room_days")
    if not days and f.get("admission_date") and f.get("discharge_date"):
        a, b = _date(f["admission_date"]), _date(f["discharge_date"])
        days = (b - a).days if a and b else None
    return {
        "member_id": f.get("member_id") or claim.get("member_id"),
        "admission_date": f.get("admission_date"), "discharge_date": f.get("discharge_date"),
        "diagnosis": f.get("diagnosis", ""), "procedure": f.get("procedure", ""),
        "is_accident": bool(f.get("is_accident")), "room_category": f.get("room_category"),
        "room_days": float(days or 0), "icu_days": float(f.get("icu_days") or 0), "line_items": items,
    }


def preflight(claim: dict, policy: dict) -> dict:
    return engine.compute(policy, claim_input(claim, policy))


# ---------------- Mock insurer ----------------

def timeline_add(claim, status, title, detail=""):
    claim.setdefault("timeline", []).append({"status": status, "title": title, "detail": detail, "at": store.now()})
    claim["status"] = status


def submit(claim: dict, policy: dict) -> dict:
    claim["preflight"] = preflight(claim, policy)
    claim["insurer_ref"] = f"CLM{datetime.now():%y%m%d}{claim['id'][-4:].upper()}"
    claim["submitted_on"] = str(date.today())
    claim["last_document_date"] = str(date.today())
    timeline_add(claim, "submitted", "Claim submitted to insurer", f"Reference {claim['insurer_ref']}. Sent as an NHCX claim bundle (mock).")
    store.audit("you", "claim_submitted", f"Claim {claim['insurer_ref']} submitted to {policy['insurer']}", claim["id"])
    return claim


def advance(claim: dict, policy: dict) -> dict:
    """Move the mock insurer one step: review -> query (once) -> decision -> settlement."""
    st = claim.get("status")
    behaviour = claim.get("insurer_behaviour", "fair")
    if st == "submitted":
        timeline_add(claim, "under_review", "Insurer is reviewing your claim", "The TPA has opened your file.")
    elif st == "under_review" and not claim.get("query_done") and behaviour in ("over_deduct", "query"):
        task = {"id": store.new_id("tsk"), "type": "insurer_query", "status": "open",
                "title": "Insurer needs pharmacy bills with prescriptions",
                "detail": "Please submit pharmacy bills along with the doctor's prescriptions for all medicines billed (₹12,500).",
                "due": str(date.today() + timedelta(days=7))}
        claim.setdefault("tasks", []).append(task)
        timeline_add(claim, "query_raised", "Insurer raised a query", task["title"])
    elif st in ("under_review",) or (st == "query_raised" and claim.get("query_done")):
        _decide(claim, policy, behaviour)
    elif st in ("approved", "partially_approved"):
        amt = claim["decision"]["amount_approved"]
        claim["settled_on"] = str(date.today())
        timeline_add(claim, "settled", f"₹{amt:,.0f} credited to your bank account", "NEFT credit to the account on the claim form.")
        bridge = claim.get("bridge")
        if bridge and bridge.get("status") == "active":
            bridge["status"] = "repaid"
            bridge["repaid_on"] = str(date.today())
            timeline_add(claim, "settled", f"Bridge loan of ₹{bridge['principal']:,.0f} repaid automatically from the settlement")
    return claim


def respond_task(claim: dict, task_id: str, note: str) -> dict:
    for t in claim.get("tasks", []):
        if t["id"] == task_id:
            t["status"] = "done"
            t["response"] = note
    claim["query_done"] = True
    claim["last_document_date"] = str(date.today())
    timeline_add(claim, "under_review", "Query answered", "Documents sent. The settlement clock restarts from today.")
    return claim


def _decide(claim, policy, behaviour):
    pf = preflight(claim, policy)
    deductions = [dict(d) for d in pf["deductions"]]
    if pf["rejected"]:
        claim["decision"] = {"type": "rejected", "amount_claimed": pf["billed"], "amount_approved": 0, "deductions": deductions,
                             "reasons": [r["reason"] for r in pf["reject_reasons"]], "letter": _letter(claim, policy, "rejected", pf["billed"], 0, deductions)}
        timeline_add(claim, "rejected", "Claim rejected by insurer", pf["reject_reasons"][0]["reason"])
        return
    approved = pf["payable"]
    if behaviour == "over_deduct" and pf.get("proportion"):
        ratio = pf["proportion"]
        items = claim_input(claim, policy)["line_items"]
        wrong = [i for i in items if i.get("category") in ("pharmacy", "diagnostics")]
        cut_pre_copay = sum(float(i["amount"]) * (1 - ratio) for i in wrong)
        copay = (policy.get("copay") or {}).get("percent", 0) / 100
        cut = round(cut_pre_copay * (1 - copay))
        for i in wrong:
            deductions.append({"item": i["name"], "category": i["category"], "amount": round(float(i["amount"]) * (1 - ratio) * (1 - copay), 2),
                               "reason": "Proportionate deduction due to higher room category.", "clause_id": engine.clause(policy, "room_rent"),
                               "kind": "insurer_proportionate"})
        approved = round(approved - cut)
    typ = "approved" if approved >= pf["billed"] - 1 else "partially_approved"
    claim["decision"] = {"type": typ, "amount_claimed": pf["billed"], "amount_approved": approved, "deductions": deductions,
                         "letter": _letter(claim, policy, typ, pf["billed"], approved, deductions)}
    timeline_add(claim, typ, f"Claim {'approved' if typ == 'approved' else 'partly approved'}: ₹{approved:,.0f} of ₹{pf['billed']:,.0f}",
                 "Settlement letter received.")


def _letter(claim, policy, typ, claimed, approved, deductions):
    member = next((m for m in policy["members"] if m["id"] == (claim.get("form") or {}).get("member_id", claim.get("member_id"))), policy["members"][0])
    rows = "\n".join(f"  - {d['item']}: ₹{d['amount']:,.0f} ({d['reason']})" for d in deductions if d["kind"] != "waiting")
    head = {"rejected": "REPUDIATION OF CLAIM", "approved": "CLAIM SETTLEMENT", "partially_approved": "CLAIM SETTLEMENT (PARTIAL)"}[typ]
    body = (f"{policy['insurer']}\n{head}\n\nClaim No: {claim.get('insurer_ref')}   Policy No: {policy.get('policy_number')}\n"
            f"Patient: {member['name']}\nAmount claimed: ₹{claimed:,.0f}\nAmount approved: ₹{approved:,.0f}\n\n")
    if typ == "rejected":
        c = engine.clause(policy, "waiting_specific")
        body += f"Your claim is not payable under Clause {c} of the policy: treatment falls within the waiting period for specified diseases.\n"
    else:
        body += f"Deductions:\n{rows}\n"
    body += "\nIf you are not satisfied, you may write to our Grievance Redressal Officer, use IRDAI Bima Bharosa, or approach the Insurance Ombudsman."
    return body


def analyse_decision(claim: dict, policy: dict) -> dict:
    """Compare the insurer's decision with the rule engine. Finds deductions the policy does not allow."""
    dec = claim.get("decision") or {}
    pf = preflight(claim, policy)
    disputed_items = [d for d in dec.get("deductions", []) if d.get("kind") == "insurer_proportionate"]
    disputed = round(sum(d["amount"] for d in disputed_items))
    grounds = []
    if disputed_items:
        cl = engine.clause(policy, "room_rent")
        grounds.append(f"Proportionate deduction of ₹{disputed:,.0f} was applied to pharmacy and diagnostics. Clause {cl} and IRDAI guidelines exclude "
                       "pharmacy, consumables, implants and diagnostics from proportionate deduction.")
    if dec.get("type") == "rejected":
        strength = "weak" if pf["rejected"] else "strong"
        summary = ("The rejection matches your policy's waiting period. An appeal is unlikely to succeed unless the condition started after "
                   "the waiting period or was caused by an accident.") if pf["rejected"] else "The rule engine finds this claim payable. Appeal."
    elif disputed:
        strength = "strong"
        summary = f"₹{disputed:,.0f} looks wrongly deducted. You have a strong case to get it back."
    else:
        strength = "none"
        summary = "All deductions follow your policy terms."
    expected = pf["payable"]
    plain = (f"The insurer approved ₹{dec.get('amount_approved', 0):,.0f} of ₹{dec.get('amount_claimed', 0):,.0f}. "
             f"By your policy rules you should get ₹{expected:,.0f}. " + summary)
    return {"strength": strength, "disputed_amount": disputed, "expected_payable": expected, "grounds": grounds,
            "summary": summary, "plain_english": plain, "rule_deductions": pf["deductions"]}


def ladder(claim: dict) -> list[dict]:
    dec_day = next((_date(t["at"]) for t in claim.get("timeline", []) if t["status"] in ("partially_approved", "rejected")), date.today())
    sent = {a["step"]: a for a in claim.get("appeals", [])}
    steps = [
        ("insurer", "Ask the insurer to review", "Reply to the claims team with the grounds. Most fixes happen here.", "Send within 15 days", dec_day + timedelta(days=15)),
        ("gro", "Raise a grievance with the insurer", "Formal complaint to the Grievance Redressal Officer. They must reply within 14 days.", "If no fix in 15 days", None),
        ("bima_bharosa", "Complain on IRDAI Bima Bharosa", "IRDAI's grievance portal tracks the insurer's response.", "If the insurer does not resolve it", None),
        ("ombudsman", "Go to the Insurance Ombudsman", "Free, for claims up to ₹50 lakh. After the insurer's final reply or 30 days of silence.", "Within 1 year of the insurer's final reply", dec_day + timedelta(days=365)),
    ]
    out = []
    unlocked = True
    for key, title, detail, when, due in steps:
        s = sent.get(key)
        out.append({"step": key, "title": title, "detail": detail, "when": when, "due": str(due) if due else None,
                    "status": "sent" if s else ("available" if unlocked else "locked"), "sent_at": s and s.get("sent_at")})
        unlocked = bool(s)
    return out


# ---------------- Bridge (mock lender) ----------------

LENDER = "Demo Finance Ltd (partner NBFC, mock)"


def bridge_offer(claim: dict, policy: dict) -> dict | None:
    st = claim.get("status")
    if st in ("submitted", "under_review", "query_raised"):
        expected = (claim.get("preflight") or preflight(claim, policy))["payable"]
        if expected <= 0:
            return None
        principal = round(expected * 0.8 / 1000) * 1000
        days = 30
        apr = 16.0
        fee = round(principal * 0.01)
        gst = round(fee * 0.18)
        interest = round(principal * apr / 100 * days / 365)
        return {"kind": "settlement_bridge", "lender": LENDER, "principal": principal, "tenure_days": days, "apr": apr,
                "interest": interest, "processing_fee": fee, "gst": gst, "total_repayable": principal + interest + fee + gst,
                "repayment": "Repaid automatically from your claim settlement. If the insurer pays less, the balance is due in 3 EMIs.",
                "cooling_off_days": 3, "disbursal": "To your bank account within minutes (mock).",
                "why": f"Your claim should settle within 30 days of the last document. Expected payout ₹{expected:,.0f}; up to 80% bridged."}
    if st == "rejected" and claim.get("appeal_dismissed"):
        amt = (claim.get("decision") or {}).get("amount_claimed", 0)
        principal = round(min(amt, 300000) / 1000) * 1000
        months = 12
        apr = 14.0
        r = apr / 1200
        emi = round(principal * r * (1 + r) ** months / ((1 + r) ** months - 1))
        fee = round(principal * 0.015)
        return {"kind": "medical_emi", "lender": LENDER, "principal": principal, "tenure_months": months, "apr": apr, "emi": emi,
                "processing_fee": fee, "gst": round(fee * 0.18), "total_repayable": emi * months + fee + round(fee * 0.18),
                "repayment": f"{months} monthly EMIs of ₹{emi:,.0f}.", "cooling_off_days": 3,
                "why": "Your appeal options are shown first. If you need funds for the hospital bill, a medical EMI is available."}
    return None


# ---------------- NHCX FHIR export ----------------

def fhir_bundle(claim: dict, policy: dict) -> dict:
    f = claim.get("form") or {}
    member = next((m for m in policy["members"] if m["id"] == f.get("member_id", claim.get("member_id"))), policy["members"][0])
    items = bill_items(claim)
    pid, cid, oid, iid = "Patient/1", "Coverage/1", "Organization/hospital", "Organization/insurer"
    entries = [
        {"fullUrl": pid, "resource": {"resourceType": "Patient", "id": "1", "name": [{"text": member["name"]}],
                                      "gender": {"M": "male", "F": "female"}.get(member.get("gender"), "unknown")}},
        {"fullUrl": oid, "resource": {"resourceType": "Organization", "id": "hospital", "name": f.get("hospital_name") or claim.get("hospital")}},
        {"fullUrl": iid, "resource": {"resourceType": "Organization", "id": "insurer", "name": policy["insurer"]}},
        {"fullUrl": cid, "resource": {"resourceType": "Coverage", "id": "1", "status": "active", "subscriberId": policy.get("policy_number"),
                                      "beneficiary": {"reference": pid}, "payor": [{"reference": iid}],
                                      "period": {"start": policy.get("start_date"), "end": policy.get("end_date")}}},
        {"fullUrl": "Claim/1", "resource": {
            "resourceType": "Claim", "id": "1", "status": "active", "use": "claim",
            "meta": {"profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/Claim"]},
            "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/claim-type", "code": "institutional"}]},
            "subType": {"text": claim["claim_type"]},
            "patient": {"reference": pid}, "created": store.now(), "insurer": {"reference": iid}, "provider": {"reference": oid},
            "priority": {"coding": [{"code": "normal"}]},
            "insurance": [{"sequence": 1, "focal": True, "coverage": {"reference": cid}}],
            "diagnosis": [{"sequence": 1, "diagnosisCodeableConcept": {"text": f.get("diagnosis")}}],
            "procedure": [{"sequence": 1, "procedureCodeableConcept": {"text": f.get("procedure")}}] if f.get("procedure") else [],
            "billablePeriod": {"start": f.get("admission_date"), "end": f.get("discharge_date")},
            "item": [{"sequence": i + 1, "productOrService": {"text": it["name"]}, "category": {"text": it.get("category")},
                      "net": {"value": float(it["amount"]), "currency": "INR"}} for i, it in enumerate(items)],
            "total": {"value": float(f.get("total_claimed") or sum(float(i["amount"]) for i in items)), "currency": "INR"},
        }},
    ]
    for d in store.find("document", claim_id=claim["id"]):
        entries.append({"fullUrl": f"DocumentReference/{d['id']}", "resource": {
            "resourceType": "DocumentReference", "id": d["id"], "status": "current", "type": {"text": d.get("doc_type")},
            "description": d.get("filename"), "subject": {"reference": pid}}})
    return {"resourceType": "Bundle", "id": claim["id"], "type": "collection", "timestamp": store.now(),
            "meta": {"profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/ClaimBundle"]},
            "identifier": {"system": "https://hcx.example/claims", "value": claim.get("insurer_ref") or claim["id"]},
            "entry": entries}


def deadlines(claim: dict, policy: dict) -> dict:
    f = claim.get("form") or {}
    amt = (claim.get("decision") or {}).get("amount_approved") or (claim.get("preflight") or {}).get("payable")
    return engine.deadlines(policy, {"admission_date": f.get("admission_date"), "discharge_date": f.get("discharge_date"),
                                     "last_document_date": claim.get("last_document_date"), "settled_date": claim.get("settled_on"),
                                     "amount_due": amt}, bank_rate=BANK_RATE)
