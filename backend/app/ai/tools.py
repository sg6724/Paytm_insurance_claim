"""Agent tools. The LLM reads and explains; money always comes from rules.engine."""

from __future__ import annotations

import json
import re
from datetime import date

import pymupdf

from .. import config, store
from . import sarvam, stay_facts
from .sarvam import SarvamError

GUARDRAIL = (
    "You are Claimezy, a health insurance claims assistant inside the Paytm app (Paytm Insurance Broking). "
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


NUMERIC_FACTS = ("room_rent_per_day", "expected_days", "estimated_bill")


def stay_facts_for_rules(facts: dict) -> dict:
    out = {}
    for k, v in facts.items():
        if k in NUMERIC_FACTS:
            try:
                out[k] = float(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                out[k] = None
        else:
            out[k] = v
    return out


def missing_stay_facts(policy: dict, facts: dict) -> list[str]:
    """Facts still unknown, most outcome-changing first. Only facts that can change this policy's answer are listed."""
    out = []
    has_cap = (policy.get("room_rent") or {}).get("type") not in (None, "none")
    if has_cap and not (facts.get("room_rent_per_day") or facts.get("room_category")):
        out.append("room rent per day (or the room type)")
    if not (facts.get("diagnosis") or facts.get("procedure")):
        out.append("the illness or treatment")
    person_rules = any(m.get("ped") for m in policy.get("members", [])) or (policy.get("copay") or {}).get("age_threshold")
    if not facts.get("member_id") and (person_rules or len(policy.get("members", [])) > 1):
        out.append("who is in hospital")
    if not facts.get("admission_type"):
        out.append("whether it was an emergency or a planned admission")
    return out


def stay_ready(policy: dict, facts: dict) -> bool:
    """Enough for the full result card: room and treatment known, and the patient if person-specific rules exist."""
    missing = missing_stay_facts(policy, facts)
    return not any(m.startswith(("room rent", "the illness", "who is")) for m in missing)


def tidy_reply(text: str) -> str:
    """Drop sentences the model repeated word for word (it sometimes says the co-pay line twice)."""
    parts = re.split(r"(?<=[.!?।])\s+", text)
    seen, out = set(), []
    for p in parts:
        key = re.sub(r"[\W_]+", "", p.lower())
        if key and key in seen:
            continue
        seen.add(key)
        out.append(p)
    return " ".join(out).strip()


def hospital_chat(policy: dict, messages: list[dict], facts: dict, lang: str) -> dict:
    """One turn of the hospital-stay chat. Harness, in order:

    1. Read facts from the user's own words with rules (stay_facts), so nothing depends on the model.
    2. Run the rule engine on whatever is known, even if partial (room rent alone is enough for the room check).
    3. One model call: answer the user's actual question from those rule findings, ask for at most one missing fact
       (the one that changes the answer most), and pick up any extra facts.
    Returns {"reply", "facts", "ready", "check"}; check is the rule-engine result the reply was based on.
    """
    from ..rules import engine

    merged = dict(facts)
    said = " ".join(m["content"] for m in messages if m.get("role") == "user")
    for k, v in stay_facts.extract(said, policy).items():
        merged.setdefault(k, v)
    check = engine.hospital_check(policy, stay_facts_for_rules(merged))
    missing = missing_stay_facts(policy, merged)

    members = [{"id": m["id"], "name": m["name"], "relation": m["relation"]} for m in policy.get("members", [])]
    first_turn = sum(1 for m in messages if m.get("role") == "assistant") == 0
    findings = [{k: f.get(k) for k in ("severity", "title", "detail", "clause_id")} for f in check["findings"]]
    sys = (GUARDRAIL + "\nYou are on a chat with a family that is in hospital right now. How to reply:\n"
           "1. If the user asked something (e.g. 'should I take this room?'), answer it FIRST, directly, using RULE_FINDINGS: say what it "
           "means in rupees or percent as given there, and what to do. Never invent limits or amounts that are not in RULE_FINDINGS. "
           "Proportionate deduction cuts doctor, nursing, OT and procedure charges only; medicines, implants and tests are never cut by it.\n"
           "2. End with exactly ONE question, about ASK_NEXT only, in plain words (by name for people). Never ask two things. "
           "If ASK_NEXT is null, say the full check is ready below instead of asking.\n"
           "3. At most 4 short sentences, under 70 words in total. " + ("Greet briefly once. " if first_turn else "Do not greet again and do not repeat sympathy lines. ") +
           "Never mention ids, field names or date formats. A bill is NOT required; never ask for one.\n"
           "4. If the last message is unclear or cut off (like 'I think'), say you did not catch it and ask the same thing in one line.\n"
           "Also extract any new facts from the conversation: member_id (from MEMBERS), admission_type (emergency|planned), "
           "admission_date (YYYY-MM-DD), room_category (general_ward|twin_sharing|single_private|deluxe|icu), room_rent_per_day (number), "
           "expected_days (number), diagnosis and procedure (in English medical terms, e.g. 'cholelithiasis', 'knee replacement'), "
           "is_accident (bool), estimated_bill (number). " + lang_instruction(lang) +
           '\nReply as JSON: {"reply": str, "facts": {only facts stated by the user}}.')
    ctx = {"MEMBERS": members, "KNOWN_FACTS": merged, "RULE_FINDINGS": findings, "WHAT_TO_DO": check["actions"][:3],
           "ASK_NEXT": missing[0] if missing else None, "TODAY": str(__import__("datetime").date.today())}
    msgs = [{"role": "system", "content": sys}, {"role": "system", "content": json.dumps(ctx, ensure_ascii=False)}] + messages[-12:]
    try:
        out = sarvam.chat(msgs, json_mode=True, task="hospital_chat", use_cache=True, max_tokens=700, temperature=0.2)
    except SarvamError:
        out = {}  # AI unreachable: the rules still answer below
    for k, v in (out.get("facts") or {}).items():
        if k in FACT_KEYS and v not in (None, "") and k not in merged:
            merged[k] = v
    if out.get("facts"):  # the model found more: re-run the rules so the result card matches
        check = engine.hospital_check(policy, stay_facts_for_rules(merged))
    reply = tidy_reply((out.get("reply") or "").strip())
    ask_next = missing_stay_facts(policy, merged)
    if reply and ask_next and not re.search(r"[?？]", reply):  # the model forgot to ask: add the one question
        question = f"Please tell me {ask_next[0]}."
        try:
            question = sarvam.translate(question, lang)
        except SarvamError:
            pass
        reply = f"{reply} {question}"
    if not reply:  # no model: say what the rules found (only if serious), then ask
        top = next((f for f in check["findings"] if f["severity"] == "high"), None)
        ask = missing_stay_facts(policy, merged)
        if not any(merged.get(k) for k in ("member_id", "room_rent_per_day", "room_category", "diagnosis", "procedure")):
            question = "Please tell me who is in hospital, the room type and its rent per day, and the treatment."
        else:
            question = f"Please tell me {ask[0]}." if ask else "Your full check is ready below."
        reply = " ".join(filter(None, [f"{top['title']}. {top['detail']}" if top else "", question]))
    return {"reply": reply, "facts": merged, "ready": stay_ready(policy, merged), "check": check}


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
    prof = store.get("profile", "me") or {}
    ctx = {"policy_number": policy.get("policy_number"), "insurer": policy.get("insurer"), "claimant": member.get("name"),
           "claimant_contact": {k: prof.get(k) for k in ("mobile", "email", "pincode") if prof.get(k)}, "today": str(date.today()),
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
                                        f"grounds point by point, documents enclosed, and the specific relief requested. Sign off as the claimant. Use the claimant contact details and today's date from CONTEXT. "
                                        f"Never write placeholders such as [Your Name] or [Address]; if a detail is not in CONTEXT, leave that line out. "
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
           "If the user shares a screenshot or document, its extracted text is given as ATTACHMENT. "
           "You keep one running conversation with this user across visits. In CONTEXT, earlier_conversation_summary covers older messages and "
           "previous_session_ended says when they last talked to you. Build on that instead of starting over, and when the user says continue, "
           "pick up the last open point. Answer the user's actual question first, in at most 5 short sentences unless they ask for detail; "
           "greet only in your very first reply, never again. If CONTEXT has claim.next_step, that is the correct next action from the rule engine: "
           "never advise a different step, and never skip ahead on the escalation ladder. " + lang_instruction(lang))
    msgs = [{"role": "system", "content": sys}, {"role": "system", "content": "CONTEXT: " + json.dumps(context, ensure_ascii=False)[:24000]}]
    msgs += messages[-16:]
    return sarvam.chat(msgs, task="assistant", use_cache=True, max_tokens=900, temperature=0.3)


def _transcript(messages: list[dict]) -> str:
    return "\n".join(f"{m['role'].upper()}: {m['content'][:600]}" for m in messages)


def summarise_conversation(messages: list[dict], prior: str = "") -> str:
    """Rolling summary of messages that have left the model window. Internal, so always English."""
    try:
        return sarvam.chat([
            {"role": "system", "content": "You keep notes on a customer's conversation with an insurance claims assistant. Use only facts in the messages."},
            {"role": "user", "content": f"Notes so far: {prior or 'none'}\n\nNew messages:\n{_transcript(messages)}\n\n"
                                        "Write updated notes in under 120 words: what the customer asked, what was found or decided, what is still open."},
        ], task="thread_summary", max_tokens=400)
    except SarvamError:
        asked = [m["content"][:120] for m in messages if m["role"] == "user"][-3:]
        return f"{prior} Customer asked: {'; '.join(asked)}".strip()


def recap_conversation(messages: list[dict], summary: str, lang: str, next_step: str | None = None) -> str:
    """What the user sees on coming back. Says what was discussed; the next step is added by the rules, not here."""
    try:
        return sarvam.chat([
            {"role": "system", "content": GUARDRAIL + " " + lang_instruction(lang)},
            {"role": "user", "content": "The customer is back. In at most 2 short sentences, addressed to them and starting with the equivalent of "
                                        "'Last time', say what you talked about and what came out of it. Do not suggest a next step, do not say who to write to, and do not quote "
                                        "any percentage. Only use facts below.\n"
                                        f"Older notes: {summary or 'none'}\nConversation:\n{_transcript(messages[-16:])}\n\n"
                                        f"The correct next step is decided elsewhere ({next_step or 'none'}): leave out any advice in the conversation about what to do or who to contact. "
                                        "The conversation above may be in another language; your answer must not be. " + lang_instruction(lang)},
        ], task="thread_recap", max_tokens=250)
    except SarvamError:
        asked = [m["content"] for m in messages if m["role"] == "user"]
        more = f" and {len(asked) - 1} other question{'s' if len(asked) > 2 else ''}" if len(asked) > 1 else ""
        return f'Last time you asked: "{asked[-1][:140]}"{more}.' if asked else ""


def describe_attachment(data: bytes, mime: str) -> str:
    prompt = ("Read this screenshot or document shared by an Indian health insurance customer (it may be an insurer SMS/WhatsApp message, "
              "a letter, a bill or an app screen). Transcribe the important text and say in one line what it is. Plain text, max 200 words.")
    if mime == "application/pdf" or data[:5] == b"%PDF-":
        text = pdf_text(data, 8000)
        if len(text.replace("--- page", "").strip()) >= 80:
            return text
        # Scanned PDF with no text layer: read the first pages as images instead.
        doc = pymupdf.open(stream=data, filetype="pdf")
        pages = [sarvam.vision(prompt, doc[i].get_pixmap(dpi=110).tobytes("png"), "image/png", json_mode=False, task="attachment")
                 for i in range(min(2, doc.page_count))]
        return "\n\n".join(f"--- page {i + 1} ---\n{t}" for i, t in enumerate(pages))
    return sarvam.vision(prompt, data, mime, json_mode=False, task="attachment")
