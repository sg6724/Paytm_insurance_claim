"""Deterministic claim rule engine. All money in this product comes from here.

The LLM never computes payouts. It only extracts facts (bill lines, dates,
diagnosis) and explains the result this module returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta

from .non_payables import match_non_payable

# Cost heads on which room-rent proportionate deduction applies ("associated
# medical expenses"). IRDAI: not applied to pharmacy & consumables, implants &
# medical devices, and diagnostics.
PROPORTIONATE_HEADS = {"room", "nursing", "doctor", "ot", "anaesthesia", "procedure", "misc"}
EXEMPT_HEADS = {"pharmacy", "consumables", "implants", "diagnostics"}

ROOM_CATEGORY_RANK = {"general_ward": 0, "twin_sharing": 1, "single_private": 2, "deluxe": 3, "suite": 4}


def _d(v) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, date):
        return v
    return datetime.fromisoformat(str(v)[:10]).date()


def _months_between(a: date, b: date) -> float:
    return (b - a).days / 30.4375


@dataclass
class Deduction:
    item: str
    category: str
    amount: float
    reason: str
    clause_id: str | None = None
    kind: str = "deduction"  # non_payable | proportionate | room_excess | sub_limit | copay | deductible | si_cap | waiting


@dataclass
class Result:
    billed: float = 0.0
    payable: float = 0.0
    deductions: list[Deduction] = field(default_factory=list)
    rejected: bool = False
    reject_reasons: list[dict] = field(default_factory=list)
    flags: list[dict] = field(default_factory=list)
    risk: str = "low"
    proportion: float | None = None
    room_cap_per_day: float | None = None

    def to_dict(self):
        d = asdict(self)
        d["total_deducted"] = round(self.billed - self.payable, 2)
        d["billed"] = round(self.billed, 2)
        d["payable"] = round(self.payable, 2)
        return d


def room_cap_per_day(policy: dict, icu: bool = False) -> float | None:
    """Daily room-rent limit in rupees, or None if no cap."""
    si = policy["sum_insured"]
    rr = policy.get("icu_rent" if icu else "room_rent") or {}
    t = rr.get("type", "none")
    if t == "percent_si":
        return si * rr["value"] / 100.0
    if t == "fixed":
        return float(rr["value"])
    return None


def room_category_allowed(policy: dict) -> str | None:
    rr = policy.get("room_rent") or {}
    return rr.get("category") if rr.get("type") == "category" else None


def clause(policy: dict, topic: str) -> str | None:
    for c in policy.get("clauses", []):
        if c.get("topic") == topic:
            return c["id"]
    return None


def check_waiting_periods(policy: dict, member: dict, admission: date, diagnosis: str, is_accident: bool) -> list[dict]:
    """Return list of rejection reasons from waiting periods."""
    out = []
    start = _d(policy.get("start_date"))
    if not start or not admission:
        return out
    w = policy.get("waiting", {})
    days_in = (admission - start).days
    diag = (diagnosis or "").lower()
    if not is_accident and days_in < w.get("initial_days", 30):
        out.append({
            "code": "initial_waiting",
            "reason": f"Admitted {days_in} days after the policy started. Illness claims are not covered in the first {w.get('initial_days', 30)} days (accidents are).",
            "clause_id": clause(policy, "waiting_initial"),
        })
    for cond in member.get("ped", []):
        if cond.lower() in diag and _months_between(start, admission) < w.get("ped_months", 36):
            out.append({
                "code": "ped_waiting",
                "reason": f"'{cond}' was declared as a pre-existing condition. It is covered only after {w.get('ped_months', 36)} months; the policy is {_months_between(start, admission):.0f} months old.",
                "clause_id": clause(policy, "waiting_ped"),
            })
    for cond in w.get("specific_list", []):
        if cond.lower() in diag and _months_between(start, admission) < w.get("specific_months", 24):
            out.append({
                "code": "specific_waiting",
                "reason": f"'{cond}' has a {w.get('specific_months', 24)}-month waiting period; the policy is {_months_between(start, admission):.0f} months old.",
                "clause_id": clause(policy, "waiting_specific"),
            })
    for ex in policy.get("exclusions", []):
        kw = ex.get("keyword", "").lower()
        if kw and kw in diag:
            out.append({"code": "exclusion", "reason": f"Excluded: {ex['label']}.", "clause_id": clause(policy, "exclusions")})
    return out


def compute(policy: dict, claim: dict) -> dict:
    """Compute admissible amount for a claim.

    claim: {
      member_id, admission_date, discharge_date, diagnosis, procedure,
      is_accident, room_category, room_days, icu_days,
      line_items: [{name, category, amount, days?}]
    }
    """
    r = Result()
    member = next((m for m in policy.get("members", []) if m["id"] == claim.get("member_id")), None) or (policy.get("members") or [{}])[0]
    items = claim.get("line_items", [])
    r.billed = sum(float(i["amount"]) for i in items)

    admission = _d(claim.get("admission_date"))
    discharge = _d(claim.get("discharge_date"))

    # 0. Policy validity
    start, end = _d(policy.get("start_date")), _d(policy.get("end_date"))
    if admission and start and admission < start:
        r.rejected = True
        r.reject_reasons.append({"code": "not_in_force", "reason": "Admission date is before the policy start date.", "clause_id": None})
    if admission and end and admission > end:
        r.rejected = True
        r.reject_reasons.append({"code": "not_in_force", "reason": "Admission date is after the policy expired.", "clause_id": None})

    # 1. Waiting periods & exclusions
    condition = f"{claim.get('diagnosis', '')} {claim.get('procedure', '')}"
    wp = check_waiting_periods(policy, member, admission, condition, bool(claim.get("is_accident")))
    if wp:
        r.rejected = True
        r.reject_reasons.extend(wp)

    if r.rejected:
        r.payable = 0.0
        r.risk = "high"
        r.deductions.append(Deduction("Entire claim", "all", r.billed, r.reject_reasons[0]["reason"], r.reject_reasons[0].get("clause_id"), "waiting"))
        return r.to_dict()

    # 2. Non-payable items
    admissible = []
    for it in items:
        amt = float(it["amount"])
        np = match_non_payable(it["name"])
        consumables_rider = policy.get("consumables_cover", False)
        if np and not (consumables_rider and np[0] == "list_i"):
            r.deductions.append(Deduction(it["name"], it.get("category", "misc"), amt, f"Non-payable as per IRDAI list: {np[1]}.", clause(policy, "non_payables"), "non_payable"))
            continue
        admissible.append(dict(it, amount=amt))

    # 3. Room rent cap and proportionate deduction
    room_days = claim.get("room_days") or 0
    room_lines = [i for i in admissible if i.get("category") == "room"]
    room_total = sum(i["amount"] for i in room_lines)
    cap = room_cap_per_day(policy)
    ratio = 1.0
    if cap and room_days:
        actual_per_day = room_total / room_days
        r.room_cap_per_day = cap
        if actual_per_day > cap + 0.5:
            ratio = cap / actual_per_day
    allowed_cat = room_category_allowed(policy)
    if allowed_cat and claim.get("room_category"):
        if ROOM_CATEGORY_RANK.get(claim["room_category"], 0) > ROOM_CATEGORY_RANK.get(allowed_cat, 0):
            # category-capped policies: ratio from the typical tariff difference supplied on claim, or flag
            tariff_allowed = claim.get("allowed_category_tariff")
            if tariff_allowed and room_days:
                ratio = min(ratio, tariff_allowed / (room_total / room_days))
            r.flags.append({"code": "room_category", "message": f"Room category above the eligible '{allowed_cat.replace('_', ' ')}'. Associated charges may be reduced proportionately."})

    if ratio < 0.999:
        r.proportion = ratio
        cl = clause(policy, "room_rent")
        for it in admissible:
            head = it.get("category", "misc")
            if head in PROPORTIONATE_HEADS:
                cut = it["amount"] * (1 - ratio)
                if cut > 0.5:
                    kind = "room_excess" if head == "room" else "proportionate"
                    reason = (f"Room rent above the limit of ₹{cap:,.0f}/day; only ₹{cap:,.0f}/day is paid."
                              if head == "room" else
                              f"Room rent exceeded the limit, so this charge is paid in the same proportion ({ratio * 100:.1f}%).")
                    r.deductions.append(Deduction(it["name"], head, cut, reason, cl, kind))
                    it["amount"] -= cut

    # 4. ICU cap
    icu_cap = room_cap_per_day(policy, icu=True)
    icu_days = claim.get("icu_days") or 0
    if icu_cap and icu_days:
        icu_lines = [i for i in admissible if i.get("category") == "icu"]
        icu_total = sum(i["amount"] for i in icu_lines)
        allowed = icu_cap * icu_days
        if icu_total > allowed + 0.5:
            excess = icu_total - allowed
            r.deductions.append(Deduction("ICU charges", "icu", excess, f"ICU rent above ₹{icu_cap:,.0f}/day limit.", clause(policy, "room_rent"), "room_excess"))
            for it in icu_lines:
                it["amount"] -= excess * it["amount"] / icu_total

    subtotal = sum(i["amount"] for i in admissible)

    # 5. Sub-limits by procedure
    proc = (claim.get("procedure") or claim.get("diagnosis") or "").lower()
    for sl in policy.get("sub_limits", []):
        if sl["procedure"].lower() in proc and subtotal > sl["limit"]:
            excess = subtotal - sl["limit"]
            r.deductions.append(Deduction(f"Sub-limit: {sl['procedure']}", "all", excess, f"Your policy pays up to ₹{sl['limit']:,.0f} for {sl['procedure']}.", clause(policy, "sub_limits"), "sub_limit"))
            subtotal = sl["limit"]

    # 6. Deductible
    ded = float(policy.get("deductible") or 0)
    if ded:
        cut = min(ded, subtotal)
        r.deductions.append(Deduction("Deductible", "all", cut, f"First ₹{ded:,.0f} of each claim is paid by you (deductible).", clause(policy, "copay"), "deductible"))
        subtotal -= cut

    # 7. Co-pay
    cp = policy.get("copay") or {}
    pct = float(cp.get("percent") or 0)
    if cp.get("age_threshold") and (member.get("age") or 0) < cp["age_threshold"]:
        pct = 0
    if claim.get("non_network") and cp.get("non_network_percent"):
        pct += float(cp["non_network_percent"])
    if pct:
        cut = subtotal * pct / 100.0
        r.deductions.append(Deduction("Co-payment", "all", cut, f"You pay {pct:.0f}% of the admissible amount (co-pay).", clause(policy, "copay"), "copay"))
        subtotal -= cut

    # 8. Remaining sum insured
    remaining = float(policy.get("remaining_si", policy["sum_insured"]))
    if subtotal > remaining:
        r.deductions.append(Deduction("Sum insured exhausted", "all", subtotal - remaining, f"Only ₹{remaining:,.0f} of your sum insured is left this year.", clause(policy, "sum_insured"), "si_cap"))
        subtotal = remaining

    r.payable = round(max(subtotal, 0.0), 2)
    for d in r.deductions:
        d.amount = round(d.amount, 2)

    # Risk flags
    if admission and discharge and discharge < admission:
        r.flags.append({"code": "dates", "message": "Discharge date is before admission date."})
    if admission and discharge and (discharge - admission).days < 1 and not claim.get("day_care"):
        r.flags.append({"code": "short_stay", "message": "Stay under 24 hours. Covered only if it is a listed day-care procedure."})
    share = (r.billed - r.payable) / r.billed if r.billed else 0
    r.risk = "high" if share > 0.35 else "medium" if share > 0.15 or r.flags else "low"
    return r.to_dict()


def hospital_check(policy: dict, facts: dict) -> dict:
    """Before-discharge check from facts told by the user (no bill required).

    facts: {member_id, room_category, room_rent_per_day, expected_days, icu_days,
            diagnosis, procedure, admission_date, admission_type, is_accident,
            estimated_bill}
    """
    out = {"findings": [], "actions": [], "documents": [], "deadlines": {}, "estimate": None}
    member = next((m for m in policy.get("members", []) if m["id"] == facts.get("member_id")), None) or policy["members"][0]
    admission = _d(facts.get("admission_date")) or date.today()

    wp = check_waiting_periods(policy, member, admission, facts.get("diagnosis") or facts.get("procedure") or "", bool(facts.get("is_accident")))
    for w in wp:
        out["findings"].append({"severity": "high", "title": "Claim may be rejected", "detail": w["reason"], "clause_id": w.get("clause_id")})
        out["actions"].append("Talk to the insurer's helpline before major expenses; ask the hospital for an estimate you can pay yourself.")

    cap = room_cap_per_day(policy)
    rent = facts.get("room_rent_per_day")
    if cap and rent:
        if rent > cap + 0.5:
            ratio = cap / rent
            out["findings"].append({
                "severity": "high",
                "title": f"Room rent is above your limit of ₹{cap:,.0f}/day",
                "detail": (f"Your room costs ₹{rent:,.0f}/day. Because of proportionate deduction, doctor, nursing, OT and "
                           f"procedure charges will be paid at {ratio * 100:.0f}%. For every ₹100 of these charges you will pay ₹{(1 - ratio) * 100:.0f} yourself. "
                           "Medicines, implants and diagnostics are not affected."),
                "clause_id": clause(policy, "room_rent"),
                "ratio": round(ratio, 4),
            })
            out["actions"].append(f"Ask the hospital to move you to a room within ₹{cap:,.0f}/day. This is the single biggest saving.")
        else:
            out["findings"].append({"severity": "ok", "title": "Room rent is within your limit", "detail": f"₹{rent:,.0f}/day is within ₹{cap:,.0f}/day.", "clause_id": clause(policy, "room_rent")})
    elif room_category_allowed(policy) and facts.get("room_category"):
        allowed = room_category_allowed(policy)
        if ROOM_CATEGORY_RANK.get(facts["room_category"], 0) > ROOM_CATEGORY_RANK.get(allowed, 0):
            out["findings"].append({"severity": "high", "title": "Room category above your eligibility", "detail": f"Your policy covers up to a {allowed.replace('_', ' ')} room. A higher room reduces other charges proportionately.", "clause_id": clause(policy, "room_rent")})
            out["actions"].append(f"Ask for a {allowed.replace('_', ' ')} room.")
    elif not cap:
        out["findings"].append({"severity": "ok", "title": "No room rent limit", "detail": "Your policy has no cap on room rent.", "clause_id": clause(policy, "room_rent")})

    proc = (facts.get("procedure") or facts.get("diagnosis") or "").lower()
    for sl in policy.get("sub_limits", []):
        if proc and sl["procedure"].lower() in proc:
            out["findings"].append({"severity": "medium", "title": f"{sl['procedure'].title()} has a limit of ₹{sl['limit']:,.0f}", "detail": "Anything above this is paid by you.", "clause_id": clause(policy, "sub_limits")})

    cp = policy.get("copay") or {}
    if cp.get("percent") and not (cp.get("age_threshold") and (member.get("age") or 0) < cp["age_threshold"]):
        out["findings"].append({"severity": "medium", "title": f"{cp['percent']:.0f}% co-pay applies", "detail": f"You pay {cp['percent']:.0f}% of the admissible amount.", "clause_id": clause(policy, "copay")})

    if not policy.get("consumables_cover"):
        out["findings"].append({"severity": "medium", "title": "Consumables are not covered", "detail": "Gloves, masks, admission kits, toiletries and similar items (IRDAI non-payable list) will be deducted. Ask the hospital to keep these to a minimum and itemise the bill.", "clause_id": clause(policy, "non_payables")})
        out["actions"].append("Ask for an itemised bill, not a package total, so payable items are not lost.")

    est = facts.get("estimated_bill")
    if est:
        days = facts.get("expected_days") or 3
        room = (rent or 0) * days
        lines = [
            {"name": "Room charges", "category": "room", "amount": room},
            {"name": "Doctor, nursing, OT and procedure", "category": "procedure", "amount": max(est * 0.55 - room, 0)},
            {"name": "Medicines and consumables", "category": "pharmacy", "amount": est * 0.3},
            {"name": "Diagnostics", "category": "diagnostics", "amount": est * 0.15},
        ]
        out["estimate"] = compute(policy, {"member_id": member["id"], "admission_date": str(admission), "diagnosis": facts.get("diagnosis", ""),
                                           "procedure": facts.get("procedure", ""), "room_days": days, "line_items": lines,
                                           "is_accident": facts.get("is_accident")})

    intim = policy.get("intimation", {"emergency_hours": 24, "planned_hours": 48})
    if facts.get("admission_type") == "planned":
        out["deadlines"]["intimation"] = f"Inform the insurer at least {intim.get('planned_hours', 48)} hours before admission."
    else:
        due = datetime.combine(admission, datetime.min.time()) + timedelta(hours=intim.get("emergency_hours", 24))
        out["deadlines"]["intimation"] = f"Inform the insurer within {intim.get('emergency_hours', 24)} hours of admission (by {due:%d %b, %I:%M %p})."
    out["deadlines"]["cashless"] = "Cashless: the insurer must decide pre-authorisation within 1 hour and final discharge approval within 3 hours (IRDAI Master Circular, May 2024)."
    out["deadlines"]["submission"] = f"Reimbursement: submit documents within {policy.get('submission_days', 30)} days of discharge."
    out["documents"] = [
        "Discharge summary (signed, with diagnosis and treatment)",
        "Final itemised bill and payment receipts",
        "All prescriptions and pharmacy bills",
        "Investigation reports (lab, imaging) with doctor's requisition",
        "Implant sticker / invoice, if any",
        "FIR or MLC copy, if an accident",
    ]
    out["actions"].append("Collect every item in the document list before you leave the hospital.")
    return out


def deadlines(policy: dict, claim: dict, bank_rate: float = 5.75) -> dict:
    """Claim timelines and interest due if the insurer is late (PPI Regulations 2017:
    interest at 2% above bank rate for delay beyond the settlement deadline)."""
    out = {}
    adm, dis = _d(claim.get("admission_date")), _d(claim.get("discharge_date"))
    if adm:
        out["intimation_due"] = str(adm + timedelta(days=1))
    if dis:
        out["submission_due"] = str(dis + timedelta(days=policy.get("submission_days", 30)))
    last_doc = _d(claim.get("last_document_date"))
    if last_doc:
        due = last_doc + timedelta(days=30)
        out["settlement_due"] = str(due)
        today = _d(claim.get("today")) or date.today()
        settled = _d(claim.get("settled_date"))
        ref = settled or today
        if ref > due and claim.get("amount_due"):
            late_days = (ref - due).days
            rate = bank_rate + 2.0
            out["interest_due"] = round(claim["amount_due"] * rate / 100 * late_days / 365, 2)
            out["late_days"] = late_days
            out["interest_rate"] = rate
    return out
