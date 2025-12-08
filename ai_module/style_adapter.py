# ai_module/style_adapter.py

from backend.services import db_service
from ai_module.style_model import predict_style   # ← ML model instead of GPT


def detect_style(sender_id, receiver_id, last_message=None):
    """
    Mesajın stilini ML modeliyle tespit eder.
    Eğer ilişki tablosunda stil varsa onu döner.
    Yoksa ML sonucuna göre DB kaydı oluşturur veya günceller.
    """

    # 1. Relationship already exists → trust the stored style
    relationship = db_service.get_relationship(sender_id, receiver_id)
    if relationship and relationship.get("style"):
        return relationship["style"]

    # 2. Use ML model to detect style if we have a message
    if last_message:
        result = predict_style(last_message)
        detected_style = result["style"]  # "formal" or "informal"

        # Create or update DB record
        if not relationship:
            db_service.create_relationship(sender_id, receiver_id, detected_style, 50)
        else:
            db_service.update_relationship(sender_id, receiver_id, style=detected_style)

        return detected_style

    # 3. Fallback
    return "neutral"


def adapt_style(text, style):
    """
    Cümleyi verilen üsluba göre uyarlar.
    (Bu fonksiyon önceki halinden değişmedi.)
    """
    if style == "formal":
        return text.capitalize().replace("ya", "").replace("kanka", "").strip()

    elif style == "informal":
        return text.lower().replace("merhaba", "selam").replace("selamlar", "selam")

    return text


# Test
if __name__ == "__main__":
    sample_text = "merhaba nasılsın"
    print("Formal:", adapt_style(sample_text, "formal"))
    print("Informal:", adapt_style(sample_text, "informal"))
    print("Neutral:", adapt_style(sample_text, "neutral"))
