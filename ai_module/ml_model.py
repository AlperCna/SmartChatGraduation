import pickle
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "sentiment_model.pkl")
VECTORIZER_PATH = os.path.join(os.path.dirname(__file__), "..", "tfidf_vectorizer.pkl")


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
