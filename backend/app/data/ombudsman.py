"""Insurance Ombudsman offices and jurisdiction (Insurance Ombudsman Rules, 2017).

Jurisdictions follow the Council for Insurance Ombudsmen list (cioins.co.in).
Contact emails follow the official bimalokpal.<city>@cioins.co.in pattern;
the user is pointed to cioins.co.in for the full postal address.
"""

OFFICES = {
    "Ahmedabad": ["Gujarat", "Dadra and Nagar Haveli and Daman and Diu"],
    "Bengaluru": ["Karnataka"],
    "Bhopal": ["Madhya Pradesh", "Chhattisgarh"],
    "Bhubaneswar": ["Odisha"],
    "Chandigarh": ["Punjab", "Haryana", "Himachal Pradesh", "Jammu and Kashmir", "Ladakh", "Chandigarh"],
    "Chennai": ["Tamil Nadu", "Puducherry"],
    "Delhi": ["Delhi"],
    "Guwahati": ["Assam", "Meghalaya", "Manipur", "Mizoram", "Arunachal Pradesh", "Nagaland", "Tripura"],
    "Hyderabad": ["Telangana", "Andhra Pradesh"],
    "Jaipur": ["Rajasthan"],
    "Kochi": ["Kerala", "Lakshadweep"],
    "Kolkata": ["West Bengal", "Sikkim", "Andaman and Nicobar Islands"],
    "Lucknow": ["Uttar Pradesh (east and central)"],
    "Mumbai": ["Goa", "Mumbai Metropolitan Region (excluding Navi Mumbai and Thane)"],
    "Noida": ["Uttarakhand", "Uttar Pradesh (west)"],
    "Patna": ["Bihar", "Jharkhand"],
    "Pune": ["Maharashtra (excluding Mumbai region)", "Navi Mumbai", "Thane"],
}

# First two digits of PIN code -> state (India Post postal circles)
PIN_PREFIX_STATE = {
    "11": "Delhi", "12": "Haryana", "13": "Haryana", "14": "Punjab", "15": "Punjab", "16": "Punjab",
    "17": "Himachal Pradesh", "18": "Jammu and Kashmir", "19": "Jammu and Kashmir",
    "20": "Uttar Pradesh", "21": "Uttar Pradesh", "22": "Uttar Pradesh", "23": "Uttar Pradesh", "24": "Uttarakhand",
    "25": "Uttar Pradesh", "26": "Uttarakhand", "27": "Uttar Pradesh", "28": "Uttar Pradesh",
    "30": "Rajasthan", "31": "Rajasthan", "32": "Rajasthan", "33": "Rajasthan", "34": "Rajasthan",
    "36": "Gujarat", "37": "Gujarat", "38": "Gujarat", "39": "Gujarat",
    "40": "Maharashtra", "41": "Maharashtra", "42": "Maharashtra", "43": "Maharashtra", "44": "Maharashtra",
    "45": "Madhya Pradesh", "46": "Madhya Pradesh", "47": "Madhya Pradesh", "48": "Madhya Pradesh", "49": "Chhattisgarh",
    "50": "Telangana", "51": "Andhra Pradesh", "52": "Andhra Pradesh", "53": "Andhra Pradesh",
    "56": "Karnataka", "57": "Karnataka", "58": "Karnataka", "59": "Karnataka",
    "60": "Tamil Nadu", "61": "Tamil Nadu", "62": "Tamil Nadu", "63": "Tamil Nadu", "64": "Tamil Nadu",
    "67": "Kerala", "68": "Kerala", "69": "Kerala",
    "70": "West Bengal", "71": "West Bengal", "72": "West Bengal", "73": "West Bengal", "74": "West Bengal",
    "75": "Odisha", "76": "Odisha", "77": "Odisha", "78": "Assam", "79": "Assam",
    "80": "Bihar", "81": "Bihar", "82": "Jharkhand", "83": "Jharkhand", "84": "Bihar", "85": "Bihar",
}

UP_WEST_PREFIXES = ("20", "24", "25")  # western UP districts fall under Noida


def find_office(pincode: str) -> dict:
    pin = (pincode or "").strip()
    city = None
    state = PIN_PREFIX_STATE.get(pin[:2])
    if pin.startswith("403"):
        state, city = "Goa", "Mumbai"
    elif pin.startswith("400"):
        # Thane 4006xx and Navi Mumbai 4007xx fall under Pune
        city = "Pune" if pin[:4] in ("4006", "4007") else "Mumbai"
    elif pin.startswith(("401", "421")):
        city = "Pune"
    elif state == "Uttar Pradesh":
        city = "Noida" if pin.startswith(UP_WEST_PREFIXES) else "Lucknow"
    elif state == "Maharashtra":
        city = "Pune"
    elif state:
        city = next((c for c, states in OFFICES.items() if state in states), None)
    if not city:
        return {"found": False, "message": "We couldn't map this PIN code. Find your office at cioins.co.in."}
    return {
        "found": True,
        "office": f"Insurance Ombudsman, {city}",
        "city": city,
        "state": state,
        "jurisdiction": OFFICES[city],
        "email": f"bimalokpal.{city.lower()}@cioins.co.in",
        "portal": "https://www.cioins.co.in",
        "rules": [
            "Complain to the insurer first. Go to the Ombudsman if the insurer rejects your complaint, does not reply within 30 days, or you are not satisfied.",
            "File within 1 year of the insurer's final reply.",
            "Claims up to ₹50 lakh. The service is free.",
        ],
    }
