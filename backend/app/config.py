import os
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_PATH = os.getenv("DB_PATH", str(BASE / "storage" / "claim_to_cash.db"))
# Serverless functions can only write to /tmp.
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/claimezy_uploads" if os.getenv("VERCEL") else str(BASE / "storage" / "uploads")))
AI_CACHE_DIR = Path(os.getenv("AI_CACHE_DIR", str(BASE / "app" / "data" / "ai_cache")))

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "").strip()
SARVAM_BASE = os.getenv("SARVAM_BASE", "https://api.sarvam.ai")
SARVAM_CHAT_MODEL = os.getenv("SARVAM_CHAT_MODEL", "sarvam-105b")
SARVAM_VISION_MODEL = os.getenv("SARVAM_VISION_MODEL", "gemma4")  # image-capable model on /v2/chat/completions
SARVAM_STT_MODEL = os.getenv("SARVAM_STT_MODEL", "saaras:v3")
SARVAM_TTS_MODEL = os.getenv("SARVAM_TTS_MODEL", "bulbul:v4-flash")
SARVAM_TTS_FALLBACK_MODEL = "bulbul:v3"  # for languages v4-flash has no persona in yet
SARVAM_TTS_FALLBACK_SPEAKER = "priya"
SARVAM_TTS_PACE = float(os.getenv("SARVAM_TTS_PACE", "1.0"))  # Sarvam's recommended start for conversational agents
# One warm, customer-care persona per language (v4 IDs are name_language_style). Picked by round-tripping
# sample claim lines through Saaras STT (3 runs each). Simran in English and in Hinglish (enhi) keeps one voice; elsewhere a
# native persona beats a Hindi one speaking the language. Set SARVAM_TTS_SPEAKER to use one voice everywhere.
SARVAM_TTS_SPEAKER = os.getenv("SARVAM_TTS_SPEAKER", "").strip()
SARVAM_TTS_VOICES = {
    "en-IN": "simran_en_customer",
    "hi-IN": "simran_enhi_customer",
    "mr-IN": "ritu_mr_insurance",
    "bn-IN": "roopa_bn_conversational",
    "ta-IN": "vijay_ta_narration",
    "te-IN": "kavitha_te_conversation",
    "kn-IN": "chaitra_kn_conversation",
    "gu-IN": "pooja_gu_customer",
    "pa-IN": "anand_pa_customer",
    # ml-IN and od-IN: no v4 personas yet, so they stay on v3 (Sarvam's own advice)
}

# RBI bank rate used for insurer-delay interest (PPI Regulations 2017: bank rate + 2%)
BANK_RATE = float(os.getenv("BANK_RATE", "5.75"))

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
try:
    AI_CACHE_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass  # read-only deployment: the committed cache is still readable

# Languages: Sarvam LLM / translation cover 22 Indian languages + English; Bulbul TTS covers 11.
LANGUAGES = [
    {"code": "en-IN", "name": "English", "native": "English", "tts": True},
    {"code": "hi-IN", "name": "Hindi", "native": "हिन्दी", "tts": True},
    {"code": "mr-IN", "name": "Marathi", "native": "मराठी", "tts": True},
    {"code": "bn-IN", "name": "Bengali", "native": "বাংলা", "tts": True},
    {"code": "ta-IN", "name": "Tamil", "native": "தமிழ்", "tts": True},
    {"code": "te-IN", "name": "Telugu", "native": "తెలుగు", "tts": True},
    {"code": "kn-IN", "name": "Kannada", "native": "ಕನ್ನಡ", "tts": True},
    {"code": "ml-IN", "name": "Malayalam", "native": "മലയാളം", "tts": True},
    {"code": "gu-IN", "name": "Gujarati", "native": "ગુજરાતી", "tts": True},
    {"code": "pa-IN", "name": "Punjabi", "native": "ਪੰਜਾਬੀ", "tts": True},
    {"code": "od-IN", "name": "Odia", "native": "ଓଡ଼ିଆ", "tts": True},
    {"code": "as-IN", "name": "Assamese", "native": "অসমীয়া", "tts": False},
    {"code": "ur-IN", "name": "Urdu", "native": "اردو", "tts": False},
    {"code": "ne-IN", "name": "Nepali", "native": "नेपाली", "tts": False},
    {"code": "kok-IN", "name": "Konkani", "native": "कोंकणी", "tts": False},
    {"code": "ks-IN", "name": "Kashmiri", "native": "کٲشُر", "tts": False},
    {"code": "sd-IN", "name": "Sindhi", "native": "سنڌي", "tts": False},
    {"code": "sa-IN", "name": "Sanskrit", "native": "संस्कृतम्", "tts": False},
    {"code": "sat-IN", "name": "Santali", "native": "ᱥᱟᱱᱛᱟᱲᱤ", "tts": False},
    {"code": "mni-IN", "name": "Manipuri", "native": "মৈতৈলোন্", "tts": False},
    {"code": "mai-IN", "name": "Maithili", "native": "मैथिली", "tts": False},
    {"code": "brx-IN", "name": "Bodo", "native": "बड़ो", "tts": False},
    {"code": "doi-IN", "name": "Dogri", "native": "डोगरी", "tts": False},
]
LANG_NAME = {l["code"]: l["name"] for l in LANGUAGES}
