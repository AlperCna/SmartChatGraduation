import pickle
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "sentiment_model.pkl")
VECTORIZER_PATH = os.path.join(os.path.dirname(__file__), "..", "tfidf_vectorizer.pkl")

STYLE_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "style_model.pkl")
STYLE_VECTORIZER_PATH = os.path.join(os.path.dirname(__file__), "..", "style_vectorizer.pkl")



model = None
vectorizer = None

def load_sentiment_model():
    global model, vectorizer



    if model is None or vectorizer is None:
        with open(MODEL_PATH, "rb") as f:
            model = pickle.load(f)

        with open(VECTORIZER_PATH, "rb") as f:
            vectorizer = pickle.load(f)

    return model, vectorizer


def predict_sentiment(text: str):
    model, vectorizer = load_sentiment_model()

    x = vectorizer.transform([text])
    pred = model.predict(x)[0]
    confidence = float(model.predict_proba(x).max())

    return {
        "sentiment": pred,
        "confidence": confidence
    }


style_model = None
style_vectorizer = None


def load_style_model():
    print(">>> USING STYLE MODEL FILE:", MODEL_PATH)
    print(">>> MODEL EXISTS?", os.path.exists(MODEL_PATH))
    global style_model, style_vectorizer

    if style_model is None or style_vectorizer is None:
        with open(STYLE_MODEL_PATH, "rb") as f:
            style_model = pickle.load(f)

        with open(STYLE_VECTORIZER_PATH, "rb") as f:
            style_vectorizer = pickle.load(f)

    return style_model, style_vectorizer


def predict_style(text: str):
    print(">>> predict_style() FROM style_model.py IS RUNNING")
    model, vectorizer = load_style_model()

    x = vectorizer.transform([text])
    pred = model.predict(x)[0]
    confidence = float(model.predict_proba(x).max())

    return {
        "style": pred,
        "confidence": confidence
    }
