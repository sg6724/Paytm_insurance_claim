"""Deterministic reading of what a patient says about the hospital stay (English, Hindi, Marathi).

The LLM does the talking, but it sometimes returns no facts at all, and the stay check must never depend on that.
Anything found here only fills gaps: facts the LLM or the user already gave are never overridden.
"""

from __future__ import annotations

import difflib
import re

_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

_CONS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n", "प": "p", "फ": "f", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r",
    "ल": "l", "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h", "ळ": "l",
}
_MATRA = {"ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ं": "n", "ँ": "n"}
_VOWEL = {"अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u", "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au"}


def translit(word: str) -> str:
    """Rough Devanagari to Latin, good enough to fuzzy-match a first name against the policy."""
    out, i = [], 0
    while i < len(word):
        ch = word[i]
        if ch in _CONS:
            nxt = word[i + 1] if i + 1 < len(word) else ""
            out.append(_CONS[ch])
            if nxt in _MATRA:
                out.append(_MATRA[nxt])
                i += 1
            elif nxt == "्":
                i += 1
            elif i + 1 < len(word):  # inherent "a" is dropped at the end of a word
                out.append("a")
        elif ch in _VOWEL:
            out.append(_VOWEL[ch])
        i += 1
    return "".join(out)


ROOMS = [
    (r"\bicu\b|आईसीयू|आई\.?सी\.?यू", "icu"),
    (r"single|private|सिंगल|प्राइवेट|निजी", "single_private"),
    (r"twin|sharing|double|शेयरिंग|ट्विन", "twin_sharing"),
    (r"general ward|\bgeneral\b|जनरल", "general_ward"),
    (r"deluxe|डीलक्स", "deluxe"),
    (r"suite|सूट", "suite"),
]

# (pattern, diagnosis, procedure), the terms are English so the policy keyword rules can match them
CONDITIONS = [
    (r"gall ?bladder|cholecyst|gallstone|पित्ताशय|गॉलब्लैडर|पित्त", "cholelithiasis (gallstones)", "laparoscopic cholecystectomy"),
    (r"knee replacement|knee surgery|घुटना|घुटने|गुडघा|गुडघ्याची", "osteoarthritis of the knee", "knee replacement"),
    (r"cataract|मोतियाबिंद|मोतिया|मोतीबिंदू", "cataract", "cataract surgery"),
    (r"dengue|डेंगू|डेंग्यू", "dengue fever", ""),
    (r"appendi|अपेंडिक्स", "appendicitis", "appendectomy"),
    (r"hernia|हर्निया", "hernia", "hernia repair"),
    (r"caesarean|c-section|cesarean|सिजेरियन|सिझेरियन", "pregnancy", "caesarean section"),
    (r"angioplasty|एंजियोप्लास्टी|stent", "coronary artery disease", "angioplasty"),
    (r"fracture|फ्रैक्चर|हड्डी टूट|फ्रॅक्चर", "fracture", "fracture fixation"),
    (r"typhoid|टाइफाइड", "typhoid fever", ""),
    (r"malaria|मलेरिया", "malaria", ""),
    (r"pneumonia|निमोनिया", "pneumonia", ""),
]

RELATIONS = [
    (r"mother|mom|मां|माँ|मम्मी|आई\b", {"mother"}),
    (r"father|dad|पिता|पापा|वडील", {"father"}),
    (r"wife|पत्नी|बीवी|बायको", {"spouse", "wife"}),
    (r"husband|पति|नवरा", {"spouse", "husband"}),
    (r"\bson\b|बेटा|मुलगा", {"son"}),
    (r"daughter|बेटी|मुलगी", {"daughter"}),
]

_DAY = r"(?:per day|a day|/ ?day|daily|each day|per night|a night|रोज़|रोज|रोजाना|प्रतिदिन|प्रति दिन|हर दिन|दिवसाला)"
_BILL = r"(?:bill|estimate|total|expected cost|बिल|अनुमान|एस्टीमेट|कुल|खर्च)"
_NUM = r"(\d[\d,]*(?:\.\d+)?)"


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def extract(text: str, policy: dict) -> dict:
    """Facts found in what the user typed or said. Only keys we are confident about are returned."""
    t = text.translate(_DIGITS)
    low = t.lower()
    facts: dict = {}

    for pat, cat in ROOMS:
        if re.search(pat, low):
            facts["room_category"] = cat
            break

    rent = bill = None
    for m in re.finditer(_NUM, t):
        v = _num(m.group(1))
        around = low[max(0, m.start() - 28): m.end() + 28]
        after = low[m.end(): m.end() + 28]
        if re.search(_DAY, after) or re.search(r"(?:rent|room|रूम|कमरा|किराया)[^\d]{0,20}$", low[max(0, m.start() - 22): m.start()]):
            if 300 <= v <= 200000 and rent is None:
                rent = v
        elif re.search(_BILL, around) and v >= 10000 and bill is None:
            bill = v
    if rent is None and "room_category" in facts:  # one stray money amount next to a room word
        money = [_num(m.group(1)) for m in re.finditer(_NUM, t) if 300 <= _num(m.group(1)) <= 200000]
        if len(money) == 1 and money[0] != bill:
            rent = money[0]
    if rent:
        facts["room_rent_per_day"] = rent
    if bill:
        facts["estimated_bill"] = bill

    for pat, diag, proc in CONDITIONS:
        if re.search(pat, low):
            facts["diagnosis"] = diag
            if proc:
                facts["procedure"] = proc
            break

    if re.search(r"emergency|इमरजेंसी|आपातकाल|ambulance|एम्बुलेंस|आणीबाणी", low):
        facts["admission_type"] = "emergency"
    elif re.search(r"planned|scheduled|elective|नियोजित|ठरलेली|पहले से तय", low):
        facts["admission_type"] = "planned"

    member = _member(t, low, policy.get("members", []))
    if member:
        facts["member_id"] = member["id"]
    return facts


def _member(text: str, low: str, members: list[dict]) -> dict | None:
    if len(members) == 1:
        return members[0]
    firsts = {m["id"]: m["name"].split()[0].lower() for m in members}
    for m in members:
        if re.search(r"\b" + re.escape(firsts[m["id"]]) + r"\b", low):
            return m
    # Devanagari first names, matched by sound
    words = [translit(w) for w in re.findall(r"[ऀ-ॿ]+", text)]
    best, best_score = None, 0.0
    for m in members:
        for w in words:
            score = difflib.SequenceMatcher(None, w, firsts[m["id"]]).ratio()
            if score > best_score:
                best, best_score = m, score
    if best and best_score >= 0.8:
        return best
    for pat, rels in RELATIONS:
        if re.search(pat, low):
            hit = [m for m in members if m.get("relation", "").lower() in rels]
            if len(hit) == 1:
                return hit[0]
    return None
