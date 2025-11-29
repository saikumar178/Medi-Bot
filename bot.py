# bot.py  — dynamic model, auto-switch on decommission
import os
import re
import time
import logging
from dotenv import load_dotenv

load_dotenv()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("bot")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
# Set model via env; default to Groq recommended current llama 3.3 name
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
# a safe, simple fallback model to try if the first model is decommissioned
GROQ_MODEL_FALLBACK = os.getenv("GROQ_MODEL_FALLBACK", "llama-3.3-8b-versatile").strip()

SHOW_DISCLAIMER = os.getenv("SHOW_DISCLAIMER", "true").lower() in ("1","true","yes")
DISCLAIMER_SENTENCE = "I am not a doctor; this is general information and not a substitute for professional medical advice."

RED_FLAG_PATTERNS = [
    r"\bchest pain\b", r"\bdifficulty breathing\b", r"\bsevere bleeding\b",
    r"\bseizure\b", r"\bunconscious\b", r"\bsuspected stroke\b"
]

def detect_red_flag(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in RED_FLAG_PATTERNS)

def sanitize_text(text: str) -> str:
    text = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w{2,6}\b", "[redacted email]", text)
    text = re.sub(r"\b\d{7,15}\b", "[redacted number]", text)
    return re.sub(r"\s+", " ", text).strip()

# lazy groq client
_groq = None
def groq_available():
    global _groq
    if _groq is not None:
        return True
    if not GROQ_API_KEY:
        return False
    try:
        from groq import Groq
        _groq = Groq(api_key=GROQ_API_KEY)
        return True
    except Exception as e:
        logger.warning("Groq unavailable: %s", e)
        return False

def _call_groq_model(model_id: str, messages: list, max_tokens=400, temperature=0.2):
    client = _groq
    return client.chat.completions.create(
        model=model_id,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )

def call_groq_with_model_switch(user_text: str, model_primary: str, model_fallback: str):
    """
    Try primary model; if API returns model_decommissioned, switch to fallback and retry once.
    """
    messages = [
        {"role": "system", "content": (
            "You are a concise, safety-focused medical assistant. Keep answers short (2-4 sentences). if the topic is not about medical or health just say it's not related to medical or health "
            "Never give exact prescription doses. If the user mentions emergency symptoms, begin with "
            "'This may be an emergency — seek immediate medical care.'"
        )},
        {"role":"user","content": user_text}
    ]
    # attempt primary
    try:
        resp = _call_groq_model(model_primary, messages)
        # robust extraction
        try:
            text = resp.choices[0].message.content.strip()
        except Exception:
            text = str(resp)
        return text, model_primary
    except Exception as e:
        # inspect exception for Groq's BadRequest / decommission info
        msg = str(e)
        logger.warning("Groq primary model call failed: %s", msg)
        # simple check for 'model_decommissioned' in error body
        if "model_decommissioned" in msg or "decommissioned" in msg.lower():
            logger.info("Primary model decommissioned; switching to fallback: %s", model_fallback)
            try:
                resp = _call_groq_model(model_fallback, messages)
                try:
                    text = resp.choices[0].message.content.strip()
                except Exception:
                    text = str(resp)
                return text, model_fallback
            except Exception as e2:
                logger.exception("Fallback model also failed: %s", e2)
                raise
        raise

def get_reply(user_message: str) -> dict:
    text = sanitize_text(user_message)
    if not text:
        return {"reply": "Please enter a medical question or term.", "emergency": False}

    if detect_red_flag(text):
        reply = "This may be an emergency — seek immediate medical care now. Call local emergency services."
        if SHOW_DISCLAIMER:
            reply += " "
        return {"reply": reply, "emergency": True}

    # Prefer LLM answers for general medical questions
    if groq_available():
        try:
            out, used_model = call_groq_with_model_switch(text, GROQ_MODEL, GROQ_MODEL_FALLBACK)
            # ensure disclaimer appended once
            if SHOW_DISCLAIMER and DISCLAIMER_SENTENCE.lower() not in out.lower():
                out = out.rstrip(" .") + ". "
            return {"reply": out, "emergency": False, "meta": {"model": used_model}}
        except Exception as e:
            logger.exception("LLM failed; falling back to small generic advice: %s", e)

    # Minimal generic fallback (not a KB of medical facts)
    fallback = ("I couldn't reach the remote knowledge service. "
                "General self-care: rest, hydrate, and use over-the-counter symptom relievers as directed. "
               )
    if SHOW_DISCLAIMER:
        fallback += DISCLAIMER_SENTENCE
    return {"reply": fallback, "emergency": False, "meta": {"provider": "local-generic-fallback"}}
