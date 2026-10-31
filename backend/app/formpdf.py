"""Claim form as a PDF the user can print, share or hand to a hospital desk.

Built from the saved form, so it shows exactly what the user reviewed. Fields filled by AI are marked.
"""

from __future__ import annotations

import pymupdf

from .claims import FORM_FIELDS

NAVY = (0, 0.18, 0.43)
GREY = (0.4, 0.4, 0.4)
M, W, H = 40, 595, 842


def _rs(text) -> str:
    # The built-in Helvetica has no rupee glyph.
    return str(text).replace("₹", "Rs ")


def _show(key: str, v, policy: dict) -> str:
    if v in (None, ""):
        return "-"
    if key == "member_id":
        m = next((m for m in policy["members"] if m["id"] == v), None)
        return f"{m['name']} ({m['relation']})" if m else str(v)
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if key in ("room_rent_per_day", "total_claimed"):
        try:
            return f"Rs {float(v):,.0f}"
        except (TypeError, ValueError):
            pass
    return _rs(v)


def build(claim: dict, policy: dict) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=W, height=H)
    page.draw_rect(pymupdf.Rect(0, 0, W, 70), color=None, fill=NAVY)
    page.insert_text((M, 34), "Health insurance claim form", fontname="hebo", fontsize=17, color=(1, 1, 1))
    page.insert_text((M, 54), _rs(f"{policy['insurer']} · {policy['plan']}"), fontname="helv", fontsize=10, color=(0.75, 0.85, 1))
    y = 96

    form = claim.get("form") or {}
    sources = claim.get("form_sources") or {}
    ref = claim.get("insurer_ref")
    page.insert_text((M, y), f"Claim type: {claim.get('claim_type', 'reimbursement').title()}" + (f"   ·   Reference: {ref}" if ref else "   ·   Not yet submitted"),
                     fontname="helv", fontsize=10, color=GREY)
    y += 26

    for key, label in FORM_FIELDS:
        if y > H - 150:
            page = doc.new_page(width=W, height=H)
            y = 60
        page.insert_text((M, y), label, fontname="helv", fontsize=9, color=GREY)
        page.insert_text((M + 190, y), _show(key, form.get(key), policy), fontname="hebo", fontsize=10.5, color=(0.1, 0.1, 0.1))
        if sources.get(key):
            page.insert_text((W - M - 120, y), f"AI-filled from {_rs(sources[key])}", fontname="helv", fontsize=7.5, color=(0.1, 0.5, 0.35))
        page.draw_line((M, y + 6), (W - M, y + 6), color=(0.88, 0.9, 0.93), width=0.6)
        y += 24

    pf = claim.get("preflight")
    if pf:
        y += 10
        page.insert_text((M, y), "Estimated payout (from your policy rules, not a promise)", fontname="hebo", fontsize=11, color=NAVY)
        y += 18
        page.insert_text((M, y), f"Billed Rs {pf['billed']:,.0f}   ·   Likely payable Rs {pf['payable']:,.0f}   ·   Risk: {pf['risk']}", fontname="helv", fontsize=10)
        y += 16

    y = H - 70
    page.insert_text((M, y), "Declaration: the details above are true to the best of my knowledge.", fontname="helv", fontsize=9, color=GREY)
    page.insert_text((M, y + 30), "Signature of claimant: ____________________", fontname="helv", fontsize=9)
    page.insert_text((W - M - 160, y + 30), "Date: ______________", fontname="helv", fontsize=9)
    page.insert_text((M, H - 16), "Prepared with Claim-to-Cash. Synthetic demo, not a real insurer form.", fontname="helv", fontsize=7, color=GREY)
    out = doc.tobytes()
    doc.close()
    return out
