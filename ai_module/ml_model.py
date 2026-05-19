import pickle
import re
import os
from dotenv import load_dotenv

load_dotenv()

# -----------------------------------------------------------------------
# MODEL PATHS
# -----------------------------------------------------------------------
_BASE = os.path.join(os.path.dirname(__file__), "..")

MODEL_V2_PATH     = os.path.join(_BASE, "sentiment_model_v2.pkl")
STYLE_MODEL_PATH  = os.path.join(_BASE, "style_model.pkl")
STYLE_VEC_PATH    = os.path.join(_BASE, "style_vectorizer.pkl")

# -----------------------------------------------------------------------
# SENTIMENT — V2 (LinearSVC + word+char n-gram, dengeli + chat-notr)
# -----------------------------------------------------------------------
_sentiment_pipeline = None

def _normalize(text: str) -> str:
    """V2 ile aynı preprocessing."""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r'http\S+|www\S+|\S+@\S+', ' ', text)
    text = re.sub(r'(.)\1{2,}', r'\1\1', text)
    text = re.sub(r'[^\w\sA-zÀ-ɏ]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def load_sentiment_model():
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        print(">>> LOADING SENTIMENT MODEL V2 (LinearSVC + chat-notr augmented)...")
        with open(MODEL_V2_PATH, "rb") as f:
            _sentiment_pipeline = pickle.load(f)
        print(">>> SENTIMENT MODEL V2 LOADED")
    return _sentiment_pipeline

def predict_sentiment(text: str) -> dict:
    pipeline = load_sentiment_model()

    norm = _normalize(text)
    if not norm:
        return {"sentiment": "Notr", "confidence": 0.0}

    pred       = pipeline.predict([norm])[0]
    confidence = float(pipeline.predict_proba([norm]).max())

    # Düşük güven → Notr (belirsiz cümleleri zorla sınıflandırma)
    # Threshold: 0.52 — chat kısa cümlelerinde model genellikle 0.4-0.5 arası kalır
    if confidence < 0.52 and pred != "Notr":
        pred = "Notr"

    return {
        "sentiment":  pred,           # "Positive" | "Negative" | "Notr"
        "confidence": confidence
    }

# -----------------------------------------------------------------------
# STYLE MODEL (değişmedi)
# -----------------------------------------------------------------------
_style_model = None
_style_vec   = None

def load_style_model():
    global _style_model, _style_vec
    if _style_model is None or _style_vec is None:
        with open(STYLE_MODEL_PATH, "rb") as f:
            _style_model = pickle.load(f)
        with open(STYLE_VEC_PATH, "rb") as f:
            _style_vec = pickle.load(f)
    return _style_model, _style_vec

def predict_style(text: str) -> dict:
    model, vec = load_style_model()
    x    = vec.transform([text])
    pred = model.predict(x)[0]
    conf = float(model.predict_proba(x).max())
    return {"style": pred, "confidence": conf}
