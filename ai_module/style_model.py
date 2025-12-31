import os
import joblib

MODEL_PATH = os.path.join(os.path.dirname(__file__), "style_model2.pkl")
VECTORIZER_PATH = os.path.join(os.path.dirname(__file__), "style_vectorizer2.pkl")

model = None
vectorizer = None

def load_style_model():
    global model, vectorizer


    print(">>> USING STYLE MODEL FILE:", MODEL_PATH)
    print(">>> MODEL EXISTS?", os.path.exists(MODEL_PATH))

    if model is None or vectorizer is None:
        model = joblib.load(MODEL_PATH)
        vectorizer = joblib.load(VECTORIZER_PATH)

    return model, vectorizer


def predict_style(text: str):
    print(">>> predict_style() FROM style_model.py IS RUNNING")
    model, vectorizer = load_style_model()

    X = vectorizer.transform([text])
    pred = model.predict(X)[0]
    confidence = float(model.predict_proba(X).max())

    return {
        "style": pred,
        "confidence": confidence
    }
