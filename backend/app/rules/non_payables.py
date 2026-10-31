"""IRDAI list of non-medical / non-payable items.

Source: IRDAI Guidelines on Standardization of Exclusions / product filing
(Annexure "List I - Items for which coverage is not available in the policy"
and Lists II-IV of items subsumed into room, procedure or treatment costs).
Keywords are matched case-insensitively against hospital bill line items.
"""

import re

# List I: not payable at all (unless a consumables rider is bought)
LIST_I = {
    "baby food": "Baby food",
    "baby utilities": "Baby utility charges",
    "beauty": "Beauty services",
    "belt": "Belts / braces",
    "buds": "Buds",
    "cold pack": "Cold pack / hot pack",
    "hot pack": "Cold pack / hot pack",
    "carry bag": "Carry bags",
    "email": "Email / internet charges",
    "internet": "Email / internet charges",
    "food for attendant": "Food charges for attendant",
    "attendant food": "Food charges for attendant",
    "leggings": "Leggings",
    "laundry": "Laundry charges",
    "mineral water": "Mineral water",
    "sanitary pad": "Sanitary pads",
    "telephone": "Telephone charges",
    "guest services": "Guest services",
    "crepe bandage": "Crepe bandage",
    "diaper": "Diapers",
    "eyelet collar": "Eyelet collar",
    "slings": "Slings",
    "blood grouping": "Blood grouping and cross-matching of donors",
    "service charge": "Service charges where nursing charge is also charged",
    "television": "Television charges",
    "tv charges": "Television charges",
    "surcharge": "Surcharges",
    "attendant charges": "Attendant charges",
    "extra diet": "Extra diet of patient (other than diet in room charges)",
    "birth certificate": "Birth certificate",
    "certificate charges": "Certificate charges",
    "courier": "Courier charges",
    "conveyance": "Conveyance charges",
    "medical certificate": "Medical certificate",
    "medical records": "Medical records",
    "photocopies": "Photocopies charges",
    "photocopy": "Photocopies charges",
    "mortuary": "Mortuary charges",
    "walking aid": "Walking aids charges",
    "oxygen cylinder (for usage outside": "Oxygen cylinder for use outside hospital",
    "spacer": "Spacer",
    "spirometre": "Spirometer",
    "nebulizer kit": "Nebulizer kit",
    "steam inhaler": "Steam inhaler",
    "armsling": "Armsling",
    "thermometer": "Thermometer",
    "cervical collar": "Cervical collar",
    "splint": "Splint",
    "diabetic footwear": "Diabetic footwear",
    "knee brace": "Knee braces",
    "lumbo sacral belt": "Lumbo sacral belt",
    "nimbus bed": "Nimbus bed or water / air bed charges",
    "ambulance collar": "Ambulance collar",
    "ambulance equipment": "Ambulance equipment",
    "abdominal binder": "Abdominal binder",
    "private nurse": "Private nurses charges / special nursing charges",
    "special nursing": "Private nurses charges / special nursing charges",
    "sugar free tablets": "Sugar free tablets",
    "creams powders lotions": "Creams, powders, lotions (toiletries)",
    "toiletries": "Creams, powders, lotions (toiletries)",
    "ecg electrodes": "ECG electrodes",
    "gloves": "Gloves",
    "nebulisation kit": "Nebulisation kit",
    "kidney tray": "Kidney tray",
    "mask": "Mask",
    "ounce glass": "Ounce glass",
    "oxygen mask": "Oxygen mask",
    "pelvic traction belt": "Pelvic traction belt",
    "pan can": "Pan can",
    "trolly cover": "Trolley cover",
    "trolley cover": "Trolley cover",
    "urometer": "Urometer, urine jug",
    "urine jug": "Urometer, urine jug",
    "vasofix safety": "Vasofix safety",
    "admission kit": "Admission / discharge kit",
    "discharge kit": "Admission / discharge kit",
    "registration": "Registration / admission charges",
    "admission charges": "Registration / admission charges",
    "documentation": "Documentation charges / administrative expenses",
    "administrative": "Documentation charges / administrative expenses",
    "visitor pass": "Visitors pass charges",
    "expenses related to discharge": "Expenses related to prescription on discharge",
    "file opening": "File opening charges",
    "incidental": "Incidental expenses / misc. charges (not explained)",
    "patient identification band": "Patient identification band / name tag",
    "pulseoxymeter": "Pulse oximeter charges",
    "pulse oximeter": "Pulse oximeter charges",
}

# Lists II-IV: not paid separately, subsumed into room / procedure / treatment costs
SUBSUMED = {
    "bed side table": "room",
    "housekeeping": "room",
    "hand wash": "room",
    "shoe cover": "procedure",
    "surgical cap": "procedure",
    "cradle charges": "procedure",
    "comb": "room",
    "eau-de-cologne": "room",
    "foot cover": "procedure",
    "gown": "procedure",
    "slippers": "room",
    "tissue paper": "room",
    "toothpaste": "room",
    "toothbrush": "room",
    "bed pan": "room",
    "face mask": "procedure",
    "flexi mask": "procedure",
    "hand holder": "procedure",
    "sputum cup": "room",
    "disinfectant": "room",
    "lotion": "room",
    "air conditioner": "room",
    "ac charges": "room",
    "blanket": "room",
    "warmer blanket": "room",
    "attendant bed": "room",
    "camera cover": "procedure",
    "cotton": "procedure",
    "surgical tape": "procedure",
    "apron": "procedure",
    "dressing material": "treatment",
    "microscope cover": "procedure",
    "surgical blades": "procedure",
    "harmonic scalpel": "procedure",
    "drapes": "procedure",
    "surgical drill": "procedure",
    "eye kit": "procedure",
    "eye drape": "procedure",
    "x-ray film": "treatment",
    "boyles apparatus": "procedure",
    "sutures": "procedure",
    "ortho bundle": "procedure",
    "gynaec bundle": "procedure",
    "admission/discharge kit": "room",
    "nursing charges": "room",
    "rmo charges": "room",
    "hospitalisation for evaluation": "treatment",
    "urine container": "treatment",
    "syringe": "treatment",
}


def _hit(kw: str, text: str) -> bool:
    return re.search(r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])", text) is not None


def match_non_payable(name: str):
    """Return (kind, label) if the line item is non-payable, else None.

    kind is "list_i" (never payable) or "subsumed_<cost head>".
    """
    n = name.lower()
    for kw, label in LIST_I.items():
        if _hit(kw, n):
            return "list_i", label
    for kw, head in SUBSUMED.items():
        if _hit(kw, n):
            return f"subsumed_{head}", f"Included in {head} charges, not paid separately"
    return None
