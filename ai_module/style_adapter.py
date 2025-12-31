# ai_module/style_adapter.py

from backend.services import db_service
from ai_module.style_detector_gpt import detect_style_gpt


def detect_style(sender_id, receiver_id, last_message=None):
    """
    GPT tabanlı stil tespiti.
    DB ZORUNLUDUR.
    """

    # 1️⃣ Relationship mutlaka DB'den okunur
    relationship = db_service.get_relationship(sender_id, receiver_id)

    if relationship and relationship.get("style"):
        return relationship["style"]

    # 2️⃣ Relationship yoksa GPT ile tespit edilir
    if last_message:
        detected_style = detect_style_gpt(last_message)

        if relationship:
            db_service.update_relationship(
                sender_id, receiver_id, style=detected_style
            )
        else:
            db_service.create_relationship(
                sender_id, receiver_id, detected_style, 50
            )

        return detected_style

    return "neutral"


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
