"""Agent tools. The LLM reads and explains; money always comes from rules.engine."""

from __future__ import annotations

import json

import pymupdf

from .. import config
from . import sarvam, stay_facts
from .sarvam import SarvamError

GUARDRAIL = (
    "You are Claim-to-Cash, a health insurance claims assistant inside the Paytm app (Paytm Insurance Broking). "
    "Rules: 1) Never invent or calculate rupee amounts; only repeat amounts given to you in CONTEXT, which come from a rule engine. "
    "2) When you say what is or is not covered, cite the policy clause id and page from CONTEXT, e.g. (Clause C3.2, page 4). "
    "3) Be short, warm and practical. Use simple words a first-time claimant understands. "
    "4) You do not recommend or sell insurance products. "
    "5) If unsure, or the user is distressed or asks for a person, offer 'Talk to a human'. "
    "6) The customer is always the claimant; the insurer decides the claim; a lender decides any loan."
)


def lang_instruction(lang: str) -> str:
    name = config.LANG_NAME.get(lang, "English")
    return f"Reply in {name}." + (" Use simple everyday words; keep insurance terms like 'co-pay' or 'room rent' in English in brackets if helpful." if name != "English" else "")


def pdf_text(data: bytes, max_chars: int = 60000) -> str:
    doc = pymupdf.open(stream=data, filetype="pdf")
    parts = []
    for i, page in enumerate(doc):
        parts.append(f"\n--- page {i + 1} ---\n{page.get_text()}")
        if sum(len(p) for p in parts) > max_chars:
            break
    return "".join(parts)[:max_chars]


POLICY_SCHEMA = """{
 "insurer": str, "plan": str, "policy_number": str|null, "type": "individual"|"family_floater",
 "sum_insured": number, "start_date": "YYYY-MM-DD"|null, "end_date": "YYYY-MM-DD"|null,
 "members": [{"name": str, "relation": str, "age": number|null, "gender": "M"|"F"|null, "ped": [str]}],
 "room_rent": {"type": "percent_si"|"fixed"|"category"|"none", "value": number|null, "category": "general_ward"|"twin_sharing"|"single_private"|"deluxe"|null},
 "icu_rent": {"type": "percent_si"|"fixed"|"none", "value": number|null},
 "copay": {"percent": number, "age_threshold": number|null},
 "deductible": number, "consumables_cover": bool,
 "waiting": {"initial_days": number, "ped_months": number, "specific_months": number, "specific_list": [str]},
 "sub_limits": [{"procedure": str, "limit": number}],
 "exclusions": [{"keyword": str, "label": str}],
 "pre_hosp_days": number, "post_hosp_days": number,
 "intimation": {"emergency_hours": number, "planned_hours": number}, "submission_days": number,
 "clauses": [{"id": str, "topic": "sum_insured"|"room_rent"|"waiting_initial"|"waiting_ped"|"waiting_specific"|"exclusions"|"sub_limits"|"copay"|"non_payables"|"claim_process", "title": str, "page": number, "text": str}],
 "confidence": {"<field name>": number between 0 and 1},
 "needs_review": [str]
}"""


def parse_policy(data: bytes, mime: str) -> dict:
    """Extract a structured policy from a policy schedule / wording (PDF or image)."""
    instr = ("Extract this Indian health insurance policy into JSON with exactly this schema:\n" + POLICY_SCHEMA +
             "\nUse the clause numbering from the document for clause ids, and the page number where it appears. "
             "Quote clause text briefly (max 60 words). Put any field you could not find or are unsure about in needs_review "
             "and give it confidence below 0.6. If a value is absent use sensible IRDAI defaults (initial_days 30, ped_months 36, "
             "specific_months 24, submission_days 30, emergency_hours 24, planned_hours 48) and mark them in needs_review. Reply with JSON only.")
    if mime == "application/pdf":
        text = pdf_text(data)
        out = sarvam.chat([{"role": "system", "content": "You extract structured data from insurance documents. Reply with valid JSON only."},
                           {"role": "user", "content": f"{instr}\n\nDOCUMENT:\n{text}"}], json_mode=True, max_tokens=4000, task="parse_policy")
    else:
        out = sarvam.vision(instr, data, mime, task="parse_policy_img")
    return out


DOC_TYPES = ["final_bill", "itemised_bill", "interim_bill", "discharge_summary", "prescription", "pharmacy_bill",
             "investigation_report", "payment_receipt", "id_proof", "cancelled_cheque", "decision_letter", "policy_document", "other"]

DOC_SCHEMA = """{
 "doc_type": one of %s,
 "patient_name": str|null, "hospital": str|null, "admission_date": "YYYY-MM-DD"|null, "discharge_date": "YYYY-MM-DD"|null,
 "diagnosis": str|null, "procedure": str|null, "room_category": "general_ward"|"twin_sharing"|"single_private"|"deluxe"|"icu"|null,
 "room_rent_per_day": number|null, "room_days": number|null, "total_amount": number|null,
 "line_items": [{"name": str, "category": "room"|"icu"|"nursing"|"doctor"|"ot"|"anaesthesia"|"procedure"|"pharmacy"|"consumables"|"implants"|"diagnostics"|"misc", "amount": number}],
 "bank": {"account_name": str|null, "account_number": str|null, "ifsc": str|null}|null,
 "letter": {"decision": "approved"|"partially_approved"|"rejected"|"query"|null, "amount_approved": number|null, "reasons": [str]}|null,
 "confidence": number between 0 and 1,
 "summary": str
}""" % DOC_TYPES


def extract_document(data: bytes, mime: str, filename: str) -> dict:
    instr = ("This is a document from an Indian hospital or insurer, uploaded for a health insurance claim. "
             "Classify it and extract fields as JSON with exactly this schema:\n" + DOC_SCHEMA +
             "\nUse null for anything absent. Amounts are rupees as numbers. 'summary' is one plain sentence. Reply with JSON only.")
    if mime == "application/pdf":
        text = pdf_text(data, 30000)
        if len(text.strip()) < 40:
            raise SarvamError("Scanned PDF without text; upload a photo instead")
        return sarvam.chat([{"role": "system", "content": "You extract structured data from medical and insurance documents. Reply with valid JSON only."},
                            {"role": "user", "content": f"{instr}\n\nFILE: {filename}\n{text}"}], json_mode=True, max_tokens=3000, task="extract_doc")
    return sarvam.vision(instr, data, mime, task="extract_doc_img")


TOPIC_TITLES = {
    "room_rent": ("Room rent limit", "Can your room choice affect your claim?"),
    "waiting": ("Waiting periods", "When does your cover start?"),
    "coverage": ("Coverage & exclusions", "What will your plan pay for?"),
    "copay": ("Co-payment", "How much will you pay from your pocket?"),
    "claims": ("Claim experience", "How will your hospital bill be paid?"),
}


def _clause(p, topic):
    return next((c for c in p.get("clauses", []) if c.get("topic") == topic), None)


def explainer_template(p: dict) -> list[dict]:
    """Deterministic plain-English summary of the 5 topics Paytm shows before purchase."""
    si = p["sum_insured"]
    rr = p.get("room_rent") or {}
    if rr.get("type") == "percent_si":
        cap = si * rr["value"] / 100
        room = (f"Your room can cost up to ₹{cap:,.0f} a day ({rr['value']:g}% of your ₹{si:,.0f} cover). "
                f"If you take a costlier room, doctor, nursing, OT and surgery charges are also cut in the same ratio. "
                f"Medicines, implants and tests are not cut.")
    elif rr.get("type") == "fixed":
        room = f"Your room can cost up to ₹{rr['value']:,.0f} a day. A costlier room reduces other charges in the same ratio."
    elif rr.get("type") == "category":
        room = f"You are covered up to a {str(rr.get('category', '')).replace('_', ' ')} room. A higher room category reduces other charges in the same ratio."
    else:
        room = "Good news: there is no limit on room rent. Any room category is covered."
    icu = p.get("icu_rent") or {}
    if icu.get("type") == "percent_si":
        room += f" ICU is covered up to ₹{si * icu['value'] / 100:,.0f} a day."
    w = p.get("waiting", {})
    peds = sorted({c for m in p.get("members", []) for c in m.get("ped", [])})
    waiting = (f"Illness is covered after the first {w.get('initial_days', 30)} days from your first policy start; accidents are covered from day one. "
               f"Declared pre-existing conditions{(' (' + ', '.join(peds) + ')') if peds else ''} are covered after {w.get('ped_months', 36)} months. ")
    if w.get("specific_list"):
        waiting += f"These need {w.get('specific_months', 24)} months: {', '.join(w['specific_list'])}."
    cov = f"Hospital stays up to ₹{si:,.0f} a year, plus {p.get('pre_hosp_days', 30)} days of costs before and {p.get('post_hosp_days', 60)} days after admission. "
    if p.get("sub_limits"):
        cov += "Limits: " + "; ".join(f"{s['procedure']} up to ₹{s['limit']:,.0f}" for s in p["sub_limits"]) + ". "
    cov += ("Consumables like gloves and masks are covered by your add-on. " if p.get("consumables_cover")
            else "Consumables like gloves, masks and admission kits are not paid (IRDAI non-payable list). ")
    if p.get("exclusions"):
        cov += "Not covered: " + ", ".join(e["label"] for e in p["exclusions"]) + "."
    cp = p.get("copay") or {}
    if cp.get("percent"):
        copay = f"You pay {cp['percent']:g}% of every approved claim" + (f" if the patient is {cp['age_threshold']} or older" if cp.get("age_threshold") else "") + "."
    else:
        copay = "No co-pay. The insurer pays the full approved amount."
    if p.get("deductible"):
        copay += f" The first ₹{p['deductible']:,.0f} of each claim is yours (deductible)."
    it = p.get("intimation", {})
    claims = (f"Cashless at {p.get('network_hospitals', 'network'):,} network hospitals: the insurer must decide within 1 hour and approve discharge within 3 hours. " if isinstance(p.get("network_hospitals"), int)
              else "Cashless at network hospitals: the insurer must decide within 1 hour and approve discharge within 3 hours. ")
    claims += (f"Elsewhere, pay and claim back: tell the insurer within {it.get('emergency_hours', 24)} hours of an emergency admission "
               f"({it.get('planned_hours', 48)} hours before a planned one) and send documents within {p.get('submission_days', 30)} days of discharge.")
    topics = [("room_rent", room, "room_rent"), ("waiting", waiting, "waiting_initial"), ("coverage", cov, "exclusions"),
              ("copay", copay, "copay"), ("claims", claims, "claim_process")]
    out = []
    for key, text, ctopic in topics:
        c = _clause(p, ctopic)
        out.append({"key": key, "title": TOPIC_TITLES[key][0], "question": TOPIC_TITLES[key][1], "text": text,
                    "clause": {"id": c["id"], "page": c["page"], "title": c["title"], "text": c["text"]} if c else None})
    return out


def localise_topics(topics: list[dict], lang: str) -> list[dict]:
    if lang.startswith("en"):
        return topics
    try:
        blob = json.dumps([{"title": t["title"], "question": t["question"], "text": t["text"]} for t in topics], ensure_ascii=False)
        out = sarvam.chat([
            {"role": "system", "content": "Translate the JSON values for Indian health insurance customers. Keep keys, numbers, ₹ amounts and clause ids unchanged. Reply with the JSON array only."},
            {"role": "user", "content": f"Target language: {config.LANG_NAME.get(lang, lang)}\n{blob}"},
        ], json_mode=True, task="explainer_tr", max_tokens=3000)
        if isinstance(out, dict):
            out = next(iter(out.values()))
        return [dict(t, **{k: o.get(k, t[k]) for k in ("title", "question", "text")}) for t, o in zip(topics, out)]
    except Exception:
        return topics


def policy_context(p: dict) -> str:
    keep = {k: p.get(k) for k in ("insurer", "plan", "policy_number", "sum_insured", "remaining_si", "start_date", "end_date", "members",
                                  "room_rent", "icu_rent", "copay", "deductible", "consumables_cover", "waiting", "sub_limits",
                                  "exclusions", "pre_hosp_days", "post_hosp_days", "intimation", "submission_days")}
    keep["clauses"] = [{"id": c["id"], "page": c["page"], "title": c["title"], "text": c["text"]} for c in p.get("clauses", [])]
    return json.dumps(keep, ensure_ascii=False)


FACT_KEYS = ["member_id", "admission_type", "admission_date", "room_category", "room_rent_per_day", "expected_days",
             "diagnosis", "procedure", "is_accident", "estimated_bill", "claim_type"]


def hospital_chat(policy: dict, messages: list[dict], facts: dict, lang: str) -> dict:
    """Talk with the user about their hospital stay; pull out facts for the rule engine.

    Returns {"reply": str, "facts": {...}, "ready": bool}.
    """
    members = [{"id": m["id"], "name": m["name"], "relation": m["relation"]} for m in policy.get("members", [])]
    sys = (GUARDRAIL + "\nYou are helping a family that is in hospital right now. Collect, in a friendly conversational way, "
           "the facts needed to check the stay against the policy. Ask at most one or two short questions at a time. "
           "Never mention internal ids, field names or date formats to the user: ask who is in hospital by name, and for dates ask in plain words. "
           "Facts: member_id (choose from MEMBERS), admission_type (emergency|planned), admission_date (YYYY-MM-DD), room_category "
           "(general_ward|twin_sharing|single_private|deluxe|icu), room_rent_per_day (number, rupees), expected_days (number), "
           "diagnosis and procedure (always written in English medical terms, e.g. 'cholelithiasis', 'laparoscopic cholecystectomy', 'knee replacement'), is_accident (bool), estimated_bill (number, optional), claim_type (cashless|reimbursement). "
           "A bill is NOT required; never insist on one. Once you know at least the member, room rent or category, and the "
           "illness or procedure, set ready=true and say you are checking the policy. " + lang_instruction(lang) +
           "\nReply as JSON: {\"reply\": str, \"facts\": {only facts known so far}, \"ready\": bool}.")
    ctx = f"MEMBERS: {json.dumps(members, ensure_ascii=False)}\nKNOWN FACTS: {json.dumps(facts, ensure_ascii=False)}\nTODAY: {__import__('datetime').date.today()}"
    msgs = [{"role": "system", "content": sys}, {"role": "system", "content": ctx}] + messages[-12:]
    out = sarvam.chat(msgs, json_mode=True, task="hospital_chat", use_cache=True, max_tokens=800)
    merged = dict(facts)
    merged.update({k: v for k, v in (out.get("facts") or {}).items() if k in FACT_KEYS and v not in (None, "")})
    # The model sometimes returns no facts. Fill the gaps from the user's own words; never override what is already known.
    said = " ".join(m["content"] for m in messages if m.get("role") == "user")
    for k, v in stay_facts.extract(said, policy).items():
        merged.setdefault(k, v)
    enough = bool(merged.get("member_id") and (merged.get("room_rent_per_day") or merged.get("room_category")) and (merged.get("diagnosis") or merged.get("procedure")))
    return {"reply": out.get("reply", ""), "facts": merged, "ready": bool(out.get("ready")) or enough, "forced": enough and not out.get("ready")}


def summarise_check(policy: dict, check: dict, lang: str) -> str:
    try:
        return sarvam.chat([
            {"role": "system", "content": GUARDRAIL + " " + lang_instruction(lang)},
            {"role": "user", "content": "Summarise this hospital-stay check for the family in 3 short sentences, most important first, "
                                        f"citing clause ids. CONTEXT (rule engine output): {json.dumps(check, ensure_ascii=False)}"},
        ], task="check_summary", max_tokens=500)
    except SarvamError:
        top = [f for f in check["findings"] if f["severity"] == "high"] or check["findings"]
        return " ".join(f"{f['title']}. {f['detail']}" for f in top[:2])


def explain_decision(policy: dict, claim: dict, analysis: dict, lang: str) -> str:
    ctx = {"decision": claim.get("decision"), "analysis": analysis,
           "clauses": [{"id": c["id"], "page": c["page"], "title": c["title"], "text": c["text"]} for c in policy.get("clauses", [])]}
    try:
        return sarvam.chat([
            {"role": "system", "content": GUARDRAIL + " " + lang_instruction(lang)},
            {"role": "user", "content": "Explain the insurer's decision to the customer in plain language: what was paid, what was cut and why "
                                        "(with clause ids), which cuts look wrong according to the rule engine, and the next step. "
                                        "Max 120 words, short paragraphs or bullets. CONTEXT: " + json.dumps(ctx, ensure_ascii=False)},
        ], task="explain_decision", max_tokens=900)
    except SarvamError:
        return analysis.get("plain_english", "")


def draft_appeal(policy: dict, claim: dict, analysis: dict, step: str, lang: str, member: dict) -> str:
    who = {"insurer": "the insurer's claims department (reconsideration request)",
           "gro": "the insurer's Grievance Redressal Officer (formal grievance)",
           "bima_bharosa": "IRDAI Bima Bharosa portal (complaint description)",
           "ombudsman": "the Insurance Ombudsman (complaint under Insurance Ombudsman Rules, 2017)"}[step]
    ctx = {"policy_number": policy.get("policy_number"), "insurer": policy.get("insurer"), "claimant": member.get("name"),
           "claim_ref": claim.get("insurer_ref"), "hospital": claim.get("form", {}).get("hospital_name") or claim.get("hospital"),
           "admission": claim.get("form", {}).get("admission_date"), "discharge": claim.get("form", {}).get("discharge_date"),
           "decision": claim.get("decision"), "analysis": analysis,
           "clauses": [{"id": c["id"], "page": c["page"], "text": c["text"]} for c in policy.get("clauses", [])]}
    try:
        return sarvam.chat([
            {"role": "system", "content": "You draft formal, polite, factual letters for Indian health insurance policyholders. "
                                          "Use only facts and amounts from CONTEXT. Cite clause ids and the IRDAI rule that proportionate deduction "
                                          "does not apply to pharmacy, consumables, implants and diagnostics when relevant. " + lang_instruction(lang)},
            {"role": "user", "content": f"Write a letter to {who}. Include subject line, reference numbers, the disputed amount, "
                                        f"grounds point by point, documents enclosed, and the specific relief requested. Sign off as the claimant. "
                                        f"Under 250 words. CONTEXT: {json.dumps(ctx, ensure_ascii=False)}"},
        ], task=f"appeal_{step}", max_tokens=1500)
    except SarvamError:
        return appeal_template(policy, claim, analysis, step, member)


def appeal_template(policy, claim, analysis, step, member) -> str:
    disputed = analysis.get("disputed_amount", 0)
    lines = "\n".join(f"{i + 1}. {g}" for i, g in enumerate(analysis.get("grounds", []))) or "1. I request a review of the decision."
    to = {"insurer": "The Claims Department", "gro": "The Grievance Redressal Officer", "bima_bharosa": "IRDAI Bima Bharosa",
          "ombudsman": "The Insurance Ombudsman"}[step]
    return (f"To: {to}, {policy.get('insurer')}\n\nSubject: Request to review claim {claim.get('insurer_ref', '')} under policy {policy.get('policy_number')}\n\n"
            f"I, {member.get('name')}, request a review of the settlement of my claim. An amount of ₹{disputed:,.0f} has been deducted "
            f"contrary to the policy terms:\n\n{lines}\n\nI request that ₹{disputed:,.0f} be paid along with applicable interest.\n\n"
            f"Enclosed: settlement letter, final bill, discharge summary, policy schedule.\n\nRegards,\n{member.get('name')}")


def assistant(messages: list[dict], lang: str, context: dict) -> str:
    sys = (GUARDRAIL + " You can help with: understanding the policy, what to do in hospital, which documents are needed, filling the claim "
           "form, tracking the claim, insurer queries, deductions and rejections, appeals and the escalation ladder (insurer, GRO, Bima "
           "Bharosa, Insurance Ombudsman), and bridge loans offered by partner lenders (the lender decides; show Key Facts first). "
           "If the user shares a screenshot or document, its extracted text is given as ATTACHMENT. " + lang_instruction(lang))
    msgs = [{"role": "system", "content": sys}, {"role": "system", "content": "CONTEXT: " + json.dumps(context, ensure_ascii=False)[:24000]}]
    msgs += messages[-16:]
    return sarvam.chat(msgs, task="assistant", use_cache=True, max_tokens=900, temperature=0.3)


def describe_attachment(data: bytes, mime: str) -> str:
    prompt = ("Read this screenshot or document shared by an Indian health insurance customer (it may be an insurer SMS/WhatsApp message, "
              "a letter, a bill or an app screen). Transcribe the important text and say in one line what it is. Plain text, max 200 words.")
    if mime == "application/pdf":
        return pdf_text(data, 6000)
    return sarvam.vision(prompt, data, mime, json_mode=False, task="attachment")
