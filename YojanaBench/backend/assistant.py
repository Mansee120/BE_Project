"""
assistant.py
------------
Multilingual voice-assistant backend for the YojanaBench dashboard.

The floating "Voice Assistant" widget turns speech into text (client-side Web
Speech API), posts it here, and reads the answer back (client-side
SpeechSynthesis). This module is the brain in the middle:

  * understands a natural-language question in almost any language - the
    question is translated to English for intent detection and the answer is
    translated back into the user's language when the optional
    ``deep_translator`` package is available,
  * answers questions about every scheme in the corpus: summary, eligibility,
    required documents, benefit amounts and the appeal hierarchy,
  * runs a *guided verbal audit*: it asks the applicant's details one by one
    with spoken questions and, once collected, runs the full multi-agent
    pipeline and reads the verdict, entitlement and next steps aloud.

Stays consistent with the rest of YojanaBench: deterministic, offline-first,
zero-cost. Multilingual replies use the optional ``deep_translator`` package
and gracefully degrade to English when it is unavailable.
"""
import re

from .agent import ActivityAgent
from .pipeline import pipeline

# ---------------------------------------------------------------------------
# Scheme aliases - everyday names people actually say.
# ---------------------------------------------------------------------------
_SCHEME_ALIASES = {
    "PMKISAN-2023": ["pm kisan", "pmkisan", "kisan samman nidhi", "kisan",
                     "kisaan", "pm-kisan", "farmer income support",
                     "किसान सम्मान", "किसान", "पीएम किसान"],
    "PMJAY-2023": ["pmjay", "ayushman bharat", "ayushman", "jan arogya",
                   "health insurance scheme", "आयुष्मान", "जन आरोग्य"],
    "PMAYG-2023": ["pmayg", "pm awas", "awas yojana", "aawas", "housing scheme",
                   "gramin aawas", "pradhan mantri awas", "pm aay",
                   "आवास योजना", "प्रधानमंत्री आवास"],
    "MGNREGA-2023": ["mgnrega", "nrega", "mnrega", "employment guarantee",
                     "rural job scheme", "100 days work", "roigar",
                     "मनरेगा", "महात्मा गांधी रोजगार", "रोजगार गारंटी"],
    "IGNOAPS-2023": ["ignoaps", "old age pension", "old age", "vridhavastha",
                     "indira gandhi old age", "senior citizen pension",
                     "वृद्धावस्था पेंशन", "बुज़ुर्ग पेंशन", "बुढ़ापा पेंशन"],
    "IGNWPS-2023": ["ignwps", "widow pension", "widow", "vidhwa",
                    "विधवा पेंशन", "विधवा"],
    "IGNDPS-2023": ["igndps", "disability pension", "divyang pension",
                    "disabled pension", "viklang pension",
                    "दिव्यांग पेंशन", "विकलांग पेंशन"],
    "PDS-NFSA-2023": ["pds", "nfsa", "ration card", "ration", "food security",
                      "rations", "bpl ration", "राशन कार्ड", "राशन",
                      "खाद्य सुरक्षा"],
    "NSP-PREMATRIC-2023": ["prematric", "nsp prematric", "pre matric",
                           "school scholarship", "sc scholarship",
                           "प्री मैट्रिक", "प्रमैट्रिक छात्रवृत्ति"],
    "PMS-SC-2023": ["post matric", "postmatric", "pms", "sc fellowship",
                    "scholarship for sc", "पोस्ट मैट्रिक", "पोस्टमैट्रिक"],
    "PMUY-2023": ["pmuy", "ujjwala", "ujwala", "lpg connection",
                  "gas connection", "उज्ज्वला", "गैस कनेक्शन"],
    "PMSBY-2023": ["pmsby", "suraksha bima", "accident insurance",
                   "दुर्घटना बीमा", "सुरक्षा बीमा"],
    "PMJJBY-2023": ["pmjjby", "jeevan jyoti", "life insurance",
                    "जीवन ज्योति", "जीवन बीमा"],
    "APY-2023": ["apy", "atal pension", "अटल पेंशन"],
    "SSY-2023": ["ssy", "sukanya", "sukanya samriddhi", "सुकन्या",
                 "सुकन्या समृद्धि"],
    "PMMVY-2023": ["pmmvy", "matru vandana", "maternity benefit",
                   "मातृ वंदना", "मातृत्व लाभ"],
    "PMJDY-2023": ["pmjdy", "jan dhan", "jan dhan yojana",
                   "bank account scheme", "जन धन"],
    "PMFBY-2023": ["pmfby", "fasal bima", "crop insurance", "फसल बीमा"],
    "KCC-2023": ["kcc", "kisan credit card", "kisan credit",
                 "किसान क्रेडिट कार्ड"],
    "PMKUSUM-2023": ["pmkusum", "kusum", "solar pump", "solar pump scheme",
                     "सौर पंप"],
    "PMAYU-2023": ["pmayu", "awas urban", "pmay urban", "urban housing",
                   "शहरी आवास"],
    "SBMG-2023": ["sbmg", "swachh bharat", "swachh bharat mission",
                  "toilet scheme", "स्वच्छ भारत", "शौचालय"],
    "JJM-2023": ["jjm", "jal jeevan", "jal jeevan mission", "tap water",
                 "जल जीवन"],
    "MDM-2023": ["mdm", "mid day meal", "midday meal", "poshan",
                 "मध्याह्न भोजन"],
    "ICDS-2023": ["icds", "anganwadi", "child development", "आंगनवाड़ी"],
    "SVA-2023": ["svanidhi", "pm svanidhi", "street vendor", "स्वनिधि",
                 "रेहड़ी पटरी"],
    "PMEGP-2023": ["pmegp", "employment generation",
                   "micro enterprise loan", "रोजगार सृजन"],
    "MUDRA-2023": ["mudra", "mudra loan", "shishu loan", "मुद्रा"],
    "SUI-2023": ["stand up india", "standup india", "stand-up india",
                 "स्टैंड अप इंडिया"],
    "PMVK-2023": ["vishwakarma", "pm vishwakarma", "artisan scheme",
                  "विश्वकर्मा"],
    "ESRAM-2023": ["eshram", "e shram", "unorganised worker", "ई श्रम"],
    "PMKMY-2023": ["pmkmy", "kisan maandhan", "farmer pension",
                   "किसान मानधन"],
    "DDUGKY-2023": ["ddugky", "grameen kaushalya", "skill training rural",
                    "कौशल विकास"],
    "NRLM-2023": ["nrlm", "aajeevika", "self help group", "shg", "आजीविका"],
    "PMFME-2023": ["pmfme", "food processing", "micro food processing",
                   "खाद्य प्रसंस्करण"],
}

# Question order used by the verbal audit. "gender" is always asked for the
# demographic record; the rest are included only when a scheme's eligibility
# clauses actually reference them.
_PREFERRED_FIELDS = ["age", "gender", "category", "annual_income",
                     "region", "family_size"]

_INT_FIELDS = {"age", "family_size", "disability_percent", "class_level",
               "annual_income"}

# Multilingual vocabulary for answer parsing (substring match).
_YES = ["yes", "yeah", "yep", "yup", "haan", "han", "haa", "ja", "ji",
        "hahn", "oun", "awm", "haanji", "ho", "aamam", "avunu", "haudu",
        "हाँ", "हां", "हो", "హా", "হ্যাঁ", "হা", "हा", "ஆம்", "হা", "है"]
_NO = ["no", "nah", "nahi", "nahin", "nope", "nakh", "nathi", "illai",
       "not", "नहीं", "नही", "नाही", "ना", "নয়", "না", "नहीं", "இல்லை"]
_SKIP = ["skip", "next", "unknown", "dont know", "don't know", "nahi pata",
         "not sure", "जानकारी नहीं", "skip karo"]

_GENDER = {
    "male": ["male", "man", "men", "boy", "purush", "aadmi", "purusha",
             "पुरुष", "आदमी", "পুরুষ"],
    "female": ["female", "woman", "women", "girl", "mahila", "aurat", "stree",
               "स्त्री", "महिला", "औरत", "মহিলা", "பெண"],
    "other": ["other", "trans", "अन्य", "অন্যান্য", "மற்ற"],
}
_CATEGORY = {
    "General": ["general", "gen", "सामान्य", "সাধারণ"],
    "SC": ["sc", "scheduled caste", "अनुसूचित जाति"],
    "ST": ["st", "scheduled tribe", "आदिवासी", "जनजाति", "adiwasi"],
    "OBC": ["obc", "other backward", "पिछड़ा", "pichra", "backward"],
    "EWS": ["ews", "economically weaker", "आर्थिक रूप से कमजोर"],
}
_REGION = {
    "rural": ["rural", "village", "gaon", "gramin", "ग्रामीण", "गांव",
              "গাঁ"],
    "urban": ["urban", "city", "town", "sheher", "shahar", "nagar", "शहर",
              "नगर"],
}
_CARD_TYPE = {
    "AAY": ["aay", "antyodaya", "अत्योदय"],
    "PHH": ["phh", "priority household"],
    "APL": ["apl", "above poverty"],
    "None": ["none", "no card", "no ration", "नहीं", "ना"],
}
_EDUCATION = {
    "11": ["11", "eleventh", "class 11", "कक्षा 11"],
    "12": ["12", "twelfth", "class 12", "कक्षा 12"],
    "UG": ["ug", "undergraduate", "graduation", "स्नातक"],
    "PG": ["pg", "post graduate", "master", "परास्नातक"],
    "Diploma": ["diploma", "डिप्लोमा"],
    "Professional": ["professional", "व्यावसायिक"],
}
_HOUSE = {
    "houseless": ["houseless", "no house", "बेघर"],
    "kutcha": ["kutcha", "kaccha", "कच्चा"],
    "pucca": ["pucca", "pakka", "पक्का"],
}


def _mytag(code):
    """Map a short language code to the locale tag MyMemory expects."""
    code = (code or "en")
    base, sep, region = code.partition("-")
    if sep:
        return code
    defaults = {
        "en": "IN", "hi": "IN", "kn": "IN", "ta": "IN", "te": "IN",
        "ml": "IN", "mr": "IN", "gu": "IN", "pa": "IN", "bn": "IN",
        "as": "IN", "or": "IN", "bho": "IN", "sa": "IN", "kok": "IN",
        "mai": "IN", "ks": "IN", "mni": "IN", "doi": "IN", "sat": "IN",
        "raj": "IN",
        "ne": "NP", "ur": "PK", "sd": "PK", "si": "LK", "fa": "IR",
        "ar": "SA", "he": "IL", "my": "MM", "zh": "CN", "ja": "JP",
        "ko": "KR", "de": "DE", "fr": "FR", "es": "ES", "pt": "BR",
        "ru": "RU", "it": "IT", "nl": "NL", "tr": "TR", "th": "TH",
        "vi": "VN", "id": "ID", "tl": "PH", "pl": "PL", "sv": "SE",
        "ms": "MY", "no": "NO", "da": "DK", "fi": "FI", "cs": "CZ",
        "el": "GR", "hu": "HU", "ro": "RO", "uk": "UA", "sr": "RS",
        "bg": "BG", "ka": "GE", "sw": "KE", "ha": "NG", "yo": "NG",
        "am": "ET", "km": "KH",
    }
    return f"{base}-{defaults.get(base, 'IN')}"


_TR_CACHE = {}


def _translate(word, source, target):
    """Translate ``word`` from ``source`` to ``target`` (None on failure).

    Tries Google's free endpoint first and, if that is blocked, falls back to
    MyMemory's keyless endpoint. Results are cached in-process so an audit's
    repeated questions do not exhaust the free quotas.
    """
    if not word:
        return word
    if (source or "").split("-")[0] == (target or "").split("-")[0]:
        return word
    key = (word, source, target)
    hit = _TR_CACHE.get(key)
    if hit is not None:
        return hit
    out = None
    try:
        from deep_translator import GoogleTranslator
        out = GoogleTranslator(source="auto", target=target).translate(word)
    except Exception:
        out = None
    if not out:
        try:
            from deep_translator import MyMemoryTranslator
            out = MyMemoryTranslator(source=_mytag(source),
                                     target=_mytag(target)).translate(word)
        except Exception:
            out = None
    if out and len(_TR_CACHE) < 2000:
        _TR_CACHE[key] = out
    return out


_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# Hindi (Roman + Devanagari) number words used by the verbal audit.
_HINDI_NUMS = {
    "ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5, "chhah": 6,
    "chhe": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10, "gyaarah": 11,
    "baarah": 12, "tera": 13, "chaudah": 14, "pandrah": 15, "solah": 16,
    "satrah": 17, "atharah": 18, "unnees": 19, "bees": 20, "tees": 30,
    "chalis": 40, "chaalees": 40, "pachaas": 50, "saath": 60, "sattar": 70,
    "assi": 80, "nabbe": 90, "nauwe": 90, "sau": 100, "hazaar": 1000,
    "hazar": 1000, "lakh": 100000,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5,
    "छह": 6, "छः": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
    "ग्यारह": 11, "बारह": 12, "तेरह": 13, "चौदह": 14, "पंद्रह": 15,
    "पन्द्रह": 15, "सोलह": 16, "सत्रह": 17, "अठारह": 18, "उन्नीस": 19,
    "बीस": 20, "तीस": 30, "चालीस": 40, "पचास": 50, "साठ": 60, "सत्तर": 70,
    "अस्सी": 80, "नब्बे": 90, "सौ": 100, "हजार": 1000, "लाख": 100000,
}


def _extract_number(text):
    """Return the first number in ``text``.

    Handles Arabic/Devanagari digits, lakh notation, and spoken Hindi numbers
    (e.g. "pachaas hazaar", "साठ").
    """
    norm = text.translate(_DEVANAGARI_DIGITS)
    m = re.search(r"(\d[\d,]*\.?\d*)", norm)
    if m:
        value = float(m.group(1).replace(",", "").replace(" ", ""))
        if "lakh" in norm.lower() or "लाख" in norm:
            value *= 100000
        return value
    total = 0
    current = 0
    found = False
    for w in norm.lower().split():
        if w in _HINDI_NUMS:
            found = True
            val = _HINDI_NUMS[w]
            if val >= 100:
                total += (current or 1) * val
                current = 0
            else:
                current += val
    return float(total + current) if found else None


def _has_any(text, words):
    text = text.lower()
    return any(w in text for w in words)


def _parse_choice(text, table, default=None):
    text = text.lower()
    for value, words in table.items():
        if any(w in text for w in words):
            return value
    return default


def _parse_bool(text):
    text = text.lower()
    if _has_any(text, _SKIP):
        return None
    if _has_any(text, _YES):
        return True
    if _has_any(text, _NO):
        return False
    return None


def _parse_field(field, text):
    """Turn a spoken answer into the value the intake agent expects."""
    if field == "email":
        if _has_any(text, _SKIP):
            return ""
        m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
        if m:
            return m.group(0)
        return text.strip() if "@" in text else ""
    if field == "full_name":
        return "" if _has_any(text, _SKIP) else text.strip()
    if field in _INT_FIELDS:
        num = _extract_number(text)
        return int(num) if num is not None else None
    if field == "gender":
        return _parse_choice(text, _GENDER)
    if field == "category":
        return _parse_choice(text, _CATEGORY)
    if field == "region":
        return _parse_choice(text, _REGION)
    if field == "card_type":
        return _parse_choice(text, _CARD_TYPE, "None")
    if field == "education_level":
        return _parse_choice(text, _EDUCATION)
    if field == "house_type":
        return _parse_choice(text, _HOUSE)
    if field in ("state", "district"):
        return text.strip() or None
    return _parse_bool(text)


_QUESTIONS = {
    "full_name": "What is the applicant's name?",
    "email": "What is your email address? Say skip if you would rather not "
             "share it.",
    "age": "How old are you? Please say your age.",
    "gender": "What is your gender? Say male, female, or other.",
    "category": "What is your social category? General, SC, ST, OBC, or EWS?",
    "annual_income": "What is your family's total annual income in rupees? "
                     "You can say it in lakhs, for example two lakh.",
    "region": "Do you live in a rural or an urban area?",
    "state": "Which state do you live in?",
    "district": "Which district do you live in?",
    "family_size": "How many members are there in your family?",
    "bpl": "Is your household on the Below Poverty Line list? Say yes or no.",
    "is_widow": "Are you a widow? Say yes or no.",
    "is_farmer": "Are you a landholding farmer with cultivable land? "
                 "Say yes or no.",
    "is_income_tax_payer": "Are you an income tax payer? Say yes or no.",
    "is_institutional_landholder": "Are you an institutional landholder, or do "
                                   "you hold a constitutional post? Say yes "
                                   "or no.",
    "card_type": "What type of ration card do you have? Say AAY, PHH, APL, "
                 "or no card.",
    "disability_percent": "What is your disability percentage?",
    "house_type": "Is your house kutcha, pucca, or are you houseless?",
    "owns_pucca_house": "Do you own a pucca, that is a permanent house? "
                        "Say yes or no.",
    "secc_listed": "Are you listed in the SECC, the Socio Economic and Caste "
                   "Census list? Say yes or no.",
    "class_level": "In which class are you studying? Say the class number.",
    "education_level": "What is your education level? Say 11, 12, UG, PG, "
                       "diploma, or professional.",
    "hosteller": "Are you a hosteller? Say yes or no.",
}

_GREET_RE = re.compile(r"\b(hello|hi|hey|namaste|namaskar|salaam|hola)\b",
                       re.IGNORECASE)


class Assistant:
    """Per-request NLU + reply building over the shared pipeline."""

    def __init__(self, pipe=pipeline):
        self.pipeline = pipe
        self.corpus = pipe.corpus
        self.schemes = self.corpus.list_schemes()
        self.sessions = {}

    # -- session management --------------------------------------------------
    def _session(self, session_id, lang="en"):
        if len(self.sessions) > 100:
            self.sessions.pop(next(iter(self.sessions)))
        s = self.sessions.setdefault(session_id or "default",
                                     {"lang": "en", "flow": None})
        if lang:
            s["lang"] = lang
        return s

    # -- scheme lookup -------------------------------------------------------
    def _match_scheme(self, text):
        text = text.lower()
        for sid, aliases in _SCHEME_ALIASES.items():
            for alias in aliases:
                if alias and alias in text:
                    return sid
        for s in self.schemes:
            sid = s["scheme_id"].lower()
            name = (s["name"] or "").lower()
            if sid in text:
                return s["scheme_id"]
            for part in name.split("(")[0].split():
                if len(part) > 3 and part in text:
                    return s["scheme_id"]
        return None

    def _get_scheme(self, scheme_id):
        return self.corpus.get_scheme(scheme_id)

    @staticmethod
    def _clause_fields(scheme):
        fields = []
        for clause in scheme.get("eligibility_clauses", []):
            f = clause.get("field")
            if f and f not in fields:
                fields.append(f)
        return fields

    def status(self):
        return {"ok": True, "schemes": len(self.schemes)}

    def welcome(self, lang="en"):
        """A short self-introduction, localised into ``lang``.

        Used by the voice widget when it opens and whenever the user picks a
        different language, so the assistant always greets in that language.
        """
        reply, _ = self._answer("greet", None)
        return {"reply": self._localise(reply, lang), "lang": lang}

    # -- entry ----------------------------------------------------------------
    def handle(self, message, lang="en", session_id=None):
        message = (message or "").strip()
        if not message:
            return {"reply": "", "lang": lang}

        en = self._to_english(message, lang)
        session = self._session(session_id, lang)

        if self._is_control(en):
            session["flow"] = None
            session["pending_start"] = False
            session["pending_action"] = None
            return {"reply": self._localise(
                ["Okay, I have stopped. Whenever you are ready, you can ask me "
                 "about any scheme, or say check if I am eligible and I will "
                 "guide you."], lang),
                "lang": lang, "intent": "cancel", "data": {}}

        if session.get("pending_action"):
            return self._resolve_pending(session, lang, en)

        if session.get("flow"):
            return self._advance_audit(session, lang, en)

        intent, scheme_id = self._detect(en)

        if intent == "create_case":
            if scheme_id or session.get("pending_start"):
                session["pending_start"] = False
                target = scheme_id or session.get("scheme_id")
                return self._start_case(session, lang, target)
            session["pending_start"] = "case"
            return self._ask_which_scheme(lang, action="case")

        if intent == "start_audit":
            if scheme_id or session.get("pending_start"):
                session["pending_start"] = False
                target = scheme_id or session.get("scheme_id")
                return self._start_audit(session, lang, target)
            session["pending_start"] = "audit"
            return self._ask_which_scheme(lang, action="audit")

        if session.get("pending_start") and scheme_id:
            action = session.get("pending_start")
            session["pending_start"] = False
            if action == "case":
                return self._start_case(session, lang, scheme_id)
            return self._start_audit(session, lang, scheme_id)

        if intent == "list_cases":
            return self._do_list_cases(lang)
        if intent == "send_notice":
            return self._do_send_notice(session, lang, scheme_id)
        if intent == "file_appeal":
            return self._do_file_appeal(session, lang, scheme_id)
        if intent == "draft_email":
            return self._do_draft_email(session, lang, message, scheme_id)

        session["pending_start"] = False
        reply, data = self._answer(intent, scheme_id)
        return {"reply": self._localise(reply, lang), "lang": lang,
                "intent": intent, "data": data, "scheme_id": scheme_id}

    # -- language helpers -----------------------------------------------------
    @classmethod
    def _to_english(cls, text, lang):
        target = (lang or "en").split("-")[0]
        if target in ("en", "auto"):
            return text.lower()
        translated = _translate(text, target, "en")
        return (translated or text).lower()

    def _localise(self, texts, lang):
        if isinstance(texts, str):
            texts = [texts]
        target = (lang or "en").split("-")[0]
        if target == "en":
            return "\n\n".join(t for t in texts if t)
        out = []
        for t in texts:
            if not t:
                continue
            translated = _translate(t, "en", target)
            out.append(translated or t)
        return "\n\n".join(out)

    # -- intent detection -----------------------------------------------------
    @staticmethod
    def _is_control(en):
        if re.search(r"\b(stop|cancel|exit|quit)\b", en):
            return True
        if re.search(r"\bend the\b", en):
            return True
        return _has_any(en, ["बंद करो", "रोको", "बंद"])

    def _detect(self, en):
        scheme_id = self._match_scheme(en)

        if _GREET_RE.search(en) or _has_any(en, ["नमस्ते", "नमस्कार"]):
            return "greet", scheme_id
        if _has_any(en, ["help", "what can you do", "how do you work",
                         "can you help me", "मदद", "सहायता"]):
            return "help", None
        if _has_any(en, ["list all schemes", "all schemes", "list the schemes",
                         "what schemes are there", "name the schemes",
                         "which schemes exist", "show schemes",
                         "सभी योजनाएं", "योजनाओं की सूची"]):
            return "list_schemes", None
        if _has_any(en, ["write the audit case", "write an audit case",
                         "write a case", "write case", "write the case",
                         "create an audit case", "create a case", "create case",
                         "make an audit case", "make a case", "prepare the case",
                         "prepare a case", "generate a case", "new case",
                         "build the case", "audit case file", "case file",
                         "केस बनाओ", "केस लिखो", "ऑडिट केस", "केस तैयार"]):
            return "create_case", scheme_id
        if _has_any(en, ["send the notice", "send notice", "send the email",
                         "email the notice", "email the decision",
                         "deliver the notice", "send the decision",
                         "send it to the applicant", "नोटिस भेजो",
                         "ईमेल भेजो", "नोटिस भेजें"]):
            return "send_notice", scheme_id
        if _has_any(en, ["file an appeal", "file appeal", "file the appeal",
                         "lodge an appeal", "lodge appeal",
                         "submit an appeal", "submit appeal",
                         "appeal this case", "register appeal",
                         "register an appeal", "record the appeal",
                         "appeal the decision", "अपील दर्ज", "अपील करो"]):
            return "file_appeal", scheme_id
        if _has_any(en, ["draft an email", "draft a letter", "write an email",
                         "write a letter", "compose an email",
                         "compose a letter", "draft email", "draft a notice",
                         "ईमेल लिखो", "पत्र लिखो"]):
            return "draft_email", scheme_id
        if _has_any(en, ["list cases", "show cases", "saved cases",
                         "my cases", "written cases", "audit cases",
                         "list the cases", "केस दिखाओ", "केस सूची"]):
            return "list_cases", None
        if _has_any(en, ["check if i am eligible", "am i eligible",
                         "can i get", "which scheme", "what scheme",
                         "run audit", "apply for", "verify my eligibility",
                         "पात्रता जांच", "क्या मैं पात्र हूं", "पात्र हूं"]):
            return "start_audit", scheme_id
        if _has_any(en, ["how much", "amount", "benefit", "entitlement",
                         "how much money", "get money", "what do i get",
                         "राशि", "कितना पैसा", "कितना पैसा मिलता",
                         "कितना पैसा मिलेगा", "लाभ"]):
            return "amount", scheme_id
        if _has_any(en, ["document", "paper", "proof", "certificate",
                         "needed", "submit", "दस्तावेज", "दस्तावेज़",
                         "कागज", "प्रमाण पत्र"]):
            return "documents", scheme_id
        if _has_any(en, ["who is eligible", "eligibility", "criteria",
                         "qualify", "conditions", "who can", "requirements",
                         "पात्रता", "कौन पात्र", "किन्हें", "योग्यता"]):
            return "eligibility", scheme_id
        if _has_any(en, ["appeal", "grievance", "complaint", "rejected",
                         "next step", "अपील", "शिकायत"]):
            return "appeal", scheme_id
        if _has_any(en, ["about", "tell me", "what is", "what's", "explain",
                         "information", "details", "introduce", "बताओ",
                         "के बारे में", "क्या है"]):
            return "about", scheme_id
        if scheme_id:
            return "about", scheme_id
        return "fallback", None

    # -- quick answers --------------------------------------------------------
    def _answer(self, intent, scheme_id):
        if intent == "greet":
            return (["Namaste! I am your YojanaBench voice assistant. I can "
                     "speak in your language and explain all the government "
                     "yojanas in this dashboard.",
                     "Ask me by voice - for example, which scheme am I "
                     "eligible for, what documents are needed, or how much "
                     "money will I get. Say help to hear everything I can "
                     "do."], {})
        if intent == "help":
            return (["Here is what I can do. I can explain any scheme - who "
                     "is eligible, what documents are required, and exactly "
                     "how much money or benefit you will get. I can also run "
                     "a full voice audit for you: I will ask your details one "
                     "by one, then tell you the verdict out loud.",
                     "I can also do the paperwork for you. Say write the "
                     "audit case and I will run the audit, compose the notice, "
                     "work out the appeal and save the case file. Then I can "
                     "send the notice and file the appeal. You can also say "
                     "list cases to hear everything I have written.",
                     "Try saying: tell me about old age pension. Or say: how "
                     "much amount under PM Kisan. Or say: write the audit case "
                     "for old age pension."], {})
        if intent == "list_schemes":
            names = [s["name"].split(" (")[0] for s in self.schemes]
            return ([f"There are {len(self.schemes)} schemes in this "
                     f"dashboard. They are: {', '.join(names)}. Ask me about "
                     f"any one of them, or say check if I am eligible and I "
                     f"will guide you through a quick audit."], {})
        if intent == "fallback":
            names = [s["name"].split(" (")[0] for s in self.schemes[:5]]
            return ([f"I did not understand that. You can ask me about any of "
                     f"the {len(self.schemes)} yojanas here, for example "
                     f"{', '.join(names)}, and more. Say help to see "
                     f"everything I can do."], {})
        if not scheme_id:
            return ([f"Which scheme would you like to know about? I can "
                     f"explain eligibility, documents, amount, and appeal "
                     f"details for any of the {len(self.schemes)} schemes "
                     f"here. Just say the scheme name."], {})
        scheme = self._get_scheme(scheme_id)
        if not scheme:
            return ([f"I could not find that scheme. Please try saying its "
                     f"name again, for example PM Kisan or old age "
                     f"pension."], {})
        if intent == "amount":
            return self._amount(scheme), {"scheme_id": scheme_id}
        if intent == "documents":
            return self._documents(scheme), {"scheme_id": scheme_id}
        if intent == "eligibility":
            return self._eligibility(scheme), {"scheme_id": scheme_id}
        if intent == "appeal":
            return self._appeal(scheme), {"scheme_id": scheme_id}
        return self._about(scheme), {"scheme_id": scheme_id}

    # -- reply builders -------------------------------------------------------
    @staticmethod
    def _about(scheme):
        level = scheme.get("level", "central")
        scope = scheme.get("state") or "all of India"
        return [f"{scheme['name']} is a {level} government yojana under the "
                f"{scheme.get('category')} sector, applicable in {scope}.",
                scheme["summary"]]

    @staticmethod
    def _eligibility(scheme):
        clauses = [c["text"] for c in scheme.get("eligibility_clauses", [])
                   if c.get("mandatory", True)]
        lead = f"You are eligible for {scheme['name']} if all of these hold. "
        return [lead + " And, ".join(clauses)]

    @staticmethod
    def _documents(scheme):
        docs = scheme.get("required_documents", [])
        mandatory = [d["name"] for d in docs if d.get("mandatory", True)]
        optional = [d["name"] for d in docs if not d.get("mandatory", True)]
        out = [f"For {scheme['name']} you must arrange these documents: "
               f"{'; '.join(mandatory)}."]
        if optional:
            out.append(f"These are optional: {'; '.join(optional)}.")
        return out

    @staticmethod
    def _amount(scheme):
        rules = scheme.get("entitlement_rules", [])
        if not rules:
            return [f"The guidelines for {scheme['name']} do not mention a "
                    f"fixed benefit amount."]
        lines = [f"Under {scheme['name']}, the benefit you receive is: "]
        for rule in rules:
            lines.append(rule["text"])
            c = rule.get("compute", {})
            if c.get("instalments_per_year") and c.get("annual_total"):
                lines.append(f"That is {c['value']} {c.get('unit')} per "
                             f"instalment, {c['instalments_per_year']} times "
                             f"a year, totalling {c['annual_total']} rupees "
                             f"per year.")
        return lines

    @staticmethod
    def _appeal(scheme):
        levels = scheme.get("appeal_hierarchy", [])
        out = [f"If your application under {scheme['name']} is rejected, you "
               f"can appeal in this order: "]
        for a in levels:
            out.append(f"Level {a['level']}: {a['authority']}, within "
                       f"{a['deadline_days']} days. {a['description']}")
        return out

    # -- vocal audit ----------------------------------------------------------
    def _ask_which_scheme(self, lang, action="audit"):
        names = [s["name"].split(" (")[0] for s in self.schemes[:6]]
        verb = "prepare the audit case for" if action == "case" else "check"
        reply = self._localise(
            [f"Which scheme would you like me to {verb}? For example: " +
             "; ".join(names) + ", and others. Once I know the scheme, I will "
             "ask you a few quick questions and then tell you your "
             "eligibility."], lang)
        return {"reply": reply, "lang": lang,
                "intent": "create_case" if action == "case" else "start_audit",
                "data": {"flow": "pending", "action": action}}

    def _start_audit(self, session, lang, scheme_id):
        if not scheme_id:
            return self._ask_which_scheme(lang, action="audit")
        fields = self._audit_fields(scheme_id)
        scheme = self._get_scheme(scheme_id)
        session.update({"flow": "audit", "action": "audit",
                        "scheme_id": scheme_id, "applicant": {},
                        "fields": fields, "index": 0})
        reply = self._localise(
            [f"Let us start the voice audit for {scheme['name']}. I will ask "
             "you a few quick questions. Say stop anytime to cancel."], lang) \
            + "\n\n" + self._localise([self._question(fields[0])], lang)
        return {"reply": reply, "lang": lang, "intent": "start_audit",
                "data": {"flow": "audit", "scheme_id": scheme_id}}

    def _start_case(self, session, lang, scheme_id):
        if not scheme_id:
            return self._ask_which_scheme(lang, action="case")
        scheme = self._get_scheme(scheme_id)
        fields = ["full_name", "email"] + self._audit_fields(scheme_id)
        session.update({"flow": "audit", "action": "case",
                        "scheme_id": scheme_id, "applicant": {},
                        "fields": fields, "index": 0, "last_case": None})
        reply = self._localise(
            [f"Let us write the audit case for {scheme['name']}. I will ask a "
             "few questions, then run the audit, compose the notice, work out "
             "any appeal and save the case file. Say stop anytime to cancel."],
            lang) + "\n\n" + self._localise([self._question(fields[0])], lang)
        return {"reply": reply, "lang": lang, "intent": "create_case",
                "data": {"flow": "audit", "scheme_id": scheme_id,
                         "action": "case"}}

    def _audit_fields(self, scheme_id):
        scheme = self._get_scheme(scheme_id)
        needed = self._clause_fields(scheme)
        fields = [f for f in _PREFERRED_FIELDS if f in needed or f == "gender"]
        for f in needed:
            if f not in fields:
                fields.append(f)
        return fields

    @staticmethod
    def _question(field):
        return _QUESTIONS.get(
            field, f"Please answer yes or no: does the "
            f"{field.replace('_', ' ')} condition apply to you?")

    def _advance_audit(self, session, lang, en):
        fields = session["fields"]
        index = session.get("index", 0)
        field = fields[index] if index < len(fields) else None
        if field is None:
            session["flow"] = None
            return self._run_audit(session, lang)

        value = _parse_field(field, en)
        if value is None:
            text = "I could not understand that. " + self._question(field)
            return {"reply": self._localise([text], lang), "lang": lang,
                    "intent": "audit", "data": {"flow": "audit"}}

        session["applicant"][field] = value
        session["index"] = index + 1
        if session["index"] >= len(fields):
            session["flow"] = None
            return self._run_audit(session, lang)
        nxt = fields[session["index"]]
        reply = self._localise(["Thank you. Next question."], lang) + \
            "\n\n" + self._localise([self._question(nxt)], lang)
        return {"reply": reply, "lang": lang, "intent": "audit",
                "data": {"flow": "audit"}}

    @staticmethod
    def _money(value):
        try:
            return "Rs {:,}".format(int(value))
        except (TypeError, ValueError):
            return str(value)

    def _run_audit(self, session, lang):
        if session.get("action") == "case":
            return self._write_case(session, lang)
        applicant = session.get("applicant", {})
        scheme_id = session.get("scheme_id")
        result = self.pipeline.run_case(scheme_id, applicant,
                                        submitted_documents=None)
        scheme = self._get_scheme(scheme_id)
        missing = [d["name"] for d in scheme.get("required_documents", [])
                   if d.get("mandatory", True)]
        return {
            "reply": self._localise(self._verdict_text(result, missing), lang),
            "lang": lang, "intent": "audit",
            "data": {"flow": "audit_done", "scheme_id": scheme_id,
                     "verdict": result["verdict"]["decision"],
                     "case_id": result["case"]["case_id"]},
        }

    # -- agent activities -----------------------------------------------------
    def _write_case(self, session, lang):
        applicant = session.get("applicant", {})
        scheme_id = session.get("scheme_id")
        outcome = ActivityAgent().write_case(scheme_id, applicant)
        record = outcome["record"]
        session["last_case"] = record
        session["action"] = None
        lines = self._case_summary_lines(outcome)
        lines.append("Should I also send this notice to the applicant and file "
                     "the appeal? Say yes to do everything, or no to stop.")
        session["pending_action"] = "all"
        return {"reply": self._localise(lines, lang), "lang": lang,
                "intent": "create_case",
                "data": {"flow": "case_done", "scheme_id": scheme_id,
                         "case_id": record["case_id"], "path": outcome["path"],
                         "decision": record["decision"],
                         "notice_subject": record["notice_subject"],
                         "appeal_applicable": record["appeal_applicable"]}}

    def _case_summary_lines(self, outcome):
        record = outcome["record"]
        verdict = outcome["result"]["verdict"]
        decision = verdict["decision"]
        lines = [f"I prepared the audit case for {record['scheme_name']}."]
        confidence = verdict.get("confidence")
        if confidence is not None:
            lines.append(f"The verdict is {decision.replace('_', ' ')} with "
                         f"{round(confidence * 100)} percent confidence.")
        else:
            lines.append(f"The verdict is {decision.replace('_', ' ')}.")
        ent = verdict.get("computed_entitlement")
        if ent is not None and decision == "eligible":
            unit = (verdict.get("entitlement_unit") or "rupees").replace(
                "INR/", "rupees per ")
            lines.append(f"The computed entitlement is {self._money(ent)} "
                         f"{unit}.")
        if record.get("notice_subject"):
            lines.append(f"I composed the grounded notice: "
                         f"{record['notice_subject']}.")
        lines.append(f"I saved the case file as {record['case_id']}.")
        if record.get("appeal_applicable"):
            step = record.get("appeal_next_step") or "follow the appeal hierarchy."
            lines.append(f"An appeal applies here. Next step: {step}.")
        else:
            lines.append("No appeal is needed for this decision.")
        return lines

    def _resolve_pending(self, session, lang, en):
        record = session.get("last_case")
        yes = _parse_bool(en)
        if yes is None:
            return {"reply": self._localise(
                ["Please say yes to let me send the notice and file the "
                 "appeal, or no to stop."], lang),
                "lang": lang, "intent": "confirm", "data": {"flow": "confirm"}}
        session["pending_action"] = None
        if not record:
            return {"reply": self._localise(
                ["I do not have a prepared case to act on."], lang),
                "lang": lang, "intent": "confirm", "data": {}}
        if not yes:
            return {"reply": self._localise(
                [f"Okay, I have not sent anything. Case {record['case_id']} is "
                 f"saved and ready whenever you need it."], lang),
                "lang": lang, "intent": "create_case",
                "data": {"flow": "case_done", "case_id": record["case_id"]}}

        agent = ActivityAgent()
        lines = ["Understood. I am carrying out the remaining activities now."]
        delivery = agent.send_notice(record)
        if delivery.get("sent"):
            lines.append(f"I sent the notice to {delivery.get('to')}.")
        elif delivery.get("outbox_path"):
            lines.append(f"There is no live mail server configured, so I saved "
                         f"the notice as a draft in the outbox for "
                         f"{delivery.get('to')}.")
        else:
            lines.append(f"I could not send the notice: "
                         f"{delivery.get('error', 'unknown error')}.")
        appeal_lines, filed = self._appeal_and_lines(agent, record)
        lines.extend(appeal_lines)
        return {"reply": self._localise(lines, lang), "lang": lang,
                "intent": "do_all",
                "data": {"flow": "case_done", "case_id": record["case_id"],
                         "sent": bool(delivery.get("sent")),
                         "appeal_filed": filed}}

    @staticmethod
    def _appeal_and_lines(agent, record):
        decision = record.get("decision")
        if record.get("appeal_applicable") or decision != "eligible":
            appeal = agent.file_appeal(record)
            entry = appeal.get("entry", {})
            lines = [f"I filed the appeal for case {record['case_id']}. This "
                     f"is attempt {entry.get('attempt', 1)}."]
            if appeal.get("official_notice"):
                lines.append("The official notice subject is "
                             f"{appeal['official_notice'].get('subject')}.")
            return lines, True
        return (["I did not file an appeal because the decision is eligible."],
                False)

    def _do_list_cases(self, lang):
        cases = ActivityAgent().list_cases()
        if not cases:
            return {"reply": self._localise(
                ["No audit cases have been written yet. Say write the audit "
                 "case and I will prepare one for you."], lang),
                "lang": lang, "intent": "list_cases", "data": {"cases": []}}
        lines = [f"I have {len(cases)} written audit case in this office."
                 if len(cases) == 1 else
                 f"I have {len(cases)} written audit cases in this office."]
        for c in cases[:8]:
            lines.append(f"{c.get('case_id')}: {c.get('scheme_name')}, verdict "
                         f"{(c.get('decision') or '').replace('_', ' ')}, saved "
                         f"on {(c.get('created_at') or '')[:10]}.")
        return {"reply": self._localise(lines, lang), "lang": lang,
                "intent": "list_cases", "data": {"cases": cases}}

    def _do_send_notice(self, session, lang, scheme_id):
        record = session.get("last_case")
        if not record:
            return self._need_case(lang, "send the notice")
        delivery = ActivityAgent().send_notice(record)
        if delivery.get("sent"):
            lines = [f"I sent the notice for case {record['case_id']} to "
                     f"{delivery.get('to')}."]
        elif delivery.get("outbox_path"):
            lines = [f"No live mail server is configured, so I saved the "
                     f"notice as a draft in the outbox for "
                     f"{delivery.get('to')}."]
        else:
            lines = [f"I could not send the notice for case {record['case_id']}: "
                     f"{delivery.get('error', 'unknown error')}."]
        return {"reply": self._localise(lines, lang), "lang": lang,
                "intent": "send_notice",
                "data": {"case_id": record["case_id"], "delivery": delivery}}

    def _do_file_appeal(self, session, lang, scheme_id):
        record = session.get("last_case")
        if not record:
            return self._need_case(lang, "file the appeal")
        appeal = ActivityAgent().file_appeal(record)
        entry = appeal.get("entry", {})
        lines = [f"I filed the appeal for case {record['case_id']}. This is "
                 f"attempt {entry.get('attempt', 1)}."]
        if appeal.get("official_notice"):
            lines.append("The official notice subject is "
                         f"{appeal['official_notice'].get('subject')}.")
        return {"reply": self._localise(lines, lang), "lang": lang,
                "intent": "file_appeal",
                "data": {"case_id": record["case_id"], "appeal": appeal}}

    def _do_draft_email(self, session, lang, message, scheme_id):
        record = session.get("last_case") or {}
        draft = ActivityAgent().draft_email(
            instruction=message, scheme_name=record.get("scheme_name", ""))
        subject = draft.get("subject") or ""
        body = draft.get("body_text") or ""
        lines = [f"I drafted an email. The subject is: {subject}."]
        if body:
            lines.append(f"The body says: {body}")
        return {"reply": self._localise(lines, lang), "lang": lang,
                "intent": "draft_email", "data": {"draft": draft}}

    def _need_case(self, lang, action):
        return {"reply": self._localise(
            [f"I do not have a written case yet, so there is nothing to "
             f"{action}. Say write the audit case and I will prepare one, then "
             f"I can {action}."], lang),
            "lang": lang, "intent": "fallback", "data": {}}

    def _verdict_text(self, result, missing_docs):
        v = result["verdict"]
        scheme = result["case"]["scheme_name"]
        decision = v["decision"]
        out = [f"For {scheme}, the audit verdict is "
               f"{decision.replace('_', ' ')}."]
        explanation = (v.get("explanation") or "").strip()
        if explanation:
            out.append(re.split(r"(?<=[.!?])\s", explanation)[0])
        if v.get("confidence") is not None:
            out.append(f"The confidence in this decision is "
                       f"{round(v['confidence'] * 100)} percent.")
        ent = v.get("computed_entitlement")
        if ent is not None and decision == "eligible":
            unit = (v.get("entitlement_unit") or "").replace("INR/",
                                                             "rupees per ")
            out.append(f"Your entitlement is {self._money(ent)} {unit}.")
            if v.get("entitlement_formula"):
                out.append(v["entitlement_formula"])
        if missing_docs:
            out.append(f"For the application you must provide these "
                       f"documents: {', '.join(missing_docs)}.")
        if v.get("human_approval_required"):
            out.append("This verdict requires an officer's review before the "
                       "benefit can be released.")
        appeal = result.get("appeal")
        if appeal and appeal.get("applicable") and appeal.get("next_step"):
            out.append(f"Next step for appeal: {appeal['next_step']}.")
        return out


assistant = Assistant()