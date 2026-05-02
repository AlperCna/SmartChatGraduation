import pickle
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "sentiment_model.pkl")
VECTORIZER_PATH = os.path.join(os.path.dirname(__file__), "..", "tfidf_vectorizer.pkl")

STYLE_MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "style_model.pkl")
STYLE_VECTORIZER_PATH = os.path.join(os.path.dirname(__file__), "..", "style_vectorizer.pkl")



from dotenv import load_dotenv

load_dotenv()

USE_BERT_SENTIMENT = os.getenv("USE_BERT_SENTIMENT", "False").lower() == "true"

model = None
vectorizer = None

bert_pipeline = None

def load_sentiment_model():
    global model, vectorizer, bert_pipeline

    if USE_BERT_SENTIMENT:
        if bert_pipeline is None:
            print(">>> LOADING BERT SENTIMENT MODEL... This might take a while.")
            try:
                from transformers import pipeline
                # Load a pretrained turkish sentiment pipeline, or a local fine-tuned one if exists.
                # "dbmdz/bert-base-turkish-cased" fine-tuned by savasy
                bert_pipeline = pipeline("sentiment-analysis", model="savasy/bert-base-turkish-sentiment-cased", device=-1)
                print(">>> BERT MODEL LOADED SUCCESSFULLY!")
            except Exception as e:
                print(">>> FAILED TO LOAD BERT:", e)
                # Fallback
                pass
    else:
        if model is None or vectorizer is None:
            with open(MODEL_PATH, "rb") as f:
                model = pickle.load(f)
            with open(VECTORIZER_PATH, "rb") as f:
                vectorizer = pickle.load(f)
            print(">>> SKLEARN TF-IDF SENTIMENT MODEL LOADED")
            
    return model, vectorizer


def predict_sentiment(text: str):
    global bert_pipeline
    
    # Check if BERT is enabled
    if USE_BERT_SENTIMENT:
        load_sentiment_model()
        if bert_pipeline is not None:
            print(">>> PREDICTING SENTIMENT WITH BERT")
            result = bert_pipeline(text)[0]
            label = result['label']
            confidence = result['score']
            
            # Map BERT labels to our project labels
            # if confidence is low, we might consider it NOTR, but by default it outputs POSITIVE / NEGATIVE
            if label.lower() == 'positive':
                final_label = 'positive'
            elif label.lower() == 'negative':
                final_label = 'negative'
            else:
                final_label = 'notr'
                
            # Simulate a 3rd class (NOTR) if confidence is below 70% 
            if confidence < 0.70:
                final_label = 'notr'
                
            return {
                "sentiment": final_label,
                "confidence": float(confidence)
            }
            
    # Fallback to default TF-IDF model
    model, vectorizer = load_sentiment_model()
    
    if model is None or vectorizer is None:
         return {"sentiment": "notr", "confidence": 0.0}

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
