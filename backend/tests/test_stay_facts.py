"""What the patient says must be understood without the LLM. These are the demo lines."""

import pytest

from app.ai.stay_facts import extract, translit
from app.data.samples import SAMPLE_POLICIES

POL = {p["id"]: p for p in SAMPLE_POLICIES}["pol_shield"]


def test_hindi_demo_line():
    f = extract("मेरी माँ सुनीता भर्ती हैं, सिंगल रूम 7500 रुपये रोज़, पित्ताशय की सर्जरी", POL)
    assert f["member_id"] == "m_sunita"
    assert f["room_category"] == "single_private" and f["room_rent_per_day"] == 7500
    assert f["procedure"] == "laparoscopic cholecystectomy"


def test_english_demo_line():
    f = extract("My mother Sunita is admitted in a single private room at Rs 7,500 a day, gallbladder surgery tomorrow", POL)
    assert (f["member_id"], f["room_rent_per_day"], f["room_category"]) == ("m_sunita", 7500, "single_private")
    assert f["diagnosis"].startswith("cholelithiasis")


def test_marathi_with_devanagari_digits():
    f = extract("माझी आई सुनीता दाखल आहे, सिंगल रूम रोज ७५०० रुपये, पित्ताशयाची शस्त्रक्रिया", POL)
    assert f["member_id"] == "m_sunita" and f["room_rent_per_day"] == 7500 and f["room_category"] == "single_private"


def test_other_member_by_name():
    f = extract("Rakesh is in a twin sharing room, knee replacement", POL)
    assert f["member_id"] == "m_rakesh" and f["room_category"] == "twin_sharing" and f["procedure"] == "knee replacement"


def test_bill_amount_is_not_mistaken_for_room_rent():
    f = extract("single room 6000 per day, hospital estimate is 150000 in total", POL)
    assert f["room_rent_per_day"] == 6000 and f["estimated_bill"] == 150000


def test_unknown_member_is_left_unset_when_ambiguous():
    assert "member_id" not in extract("someone is in hospital, general ward", POL)


def test_nothing_invented_from_chit_chat():
    assert extract("hello, can you help me?", POL) == {}


@pytest.mark.parametrize("hi,latin", [("सुनीता", "sunita"), ("राकेश", "rakesh"), ("अर्जुन", "arjun")])
def test_name_transliteration(hi, latin):
    assert translit(hi) == latin
