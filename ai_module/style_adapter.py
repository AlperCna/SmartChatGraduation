# ai_module/style_adapter.py

from backend.services import db_service
from ai_module.style_detector_gpt import detect_style_gpt


def detect_style(sender_id, receiver_id, last_message):
    try:
        # 1️⃣ GPT ile mesaj stili
        message_style = detect_style_gpt(last_message)

        # 2️⃣ Relationship çek
        relationship = db_service.get_relationship(sender_id, receiver_id)

        if not relationship:
            # Relationship yoksa yeni ilişki oluştur ama matriks yapısını bozmadan default at
            db_service.create_relationship(
                sender_id,
                receiver_id,
                style="Formal (Resmi)",
                closeness_score=0,
                politeness_score=50
            )
            relationship_style = "Formal (Resmi)"
        else:
            relationship_style = relationship.get("style", "Formal (Resmi)")

        return {
            "message_style": message_style,
            "relationship_style": relationship_style
        }

    except Exception as e:
        print("STYLE DETECT ERROR:", e)
        return {
            "message_style": "neutral",
            "relationship_style": "neutral"
        }



def adapt_style(text, style):
    """
    Basit stil uyarlama (demo amaçlı)
    """
    if style == "formal":
        return (
            text.capitalize()
            .replace("ya", "")
            .replace("kanka", "")
            .strip()
        )

    elif style == "informal":
        return (
            text.lower()
            .replace("merhaba", "selam")
            .replace("selamlar", "selam")
        )

    return text
