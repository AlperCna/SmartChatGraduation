# ai_module/style_adapter.py

from backend.services import db_service
from ai_module.style_detector_gpt import detect_style_gpt


def detect_style(sender_id, receiver_id, last_message):
    message_style = detect_style_gpt(last_message)

    relationship = db_service.get_relationship(sender_id, receiver_id)

    if not relationship:
        db_service.create_relationship(
            sender_id,
            receiver_id,
            message_style,
            confidence=60
        )
        relationship_style = message_style
    else:
        relationship_style = relationship.get("style") or message_style

        if message_style != relationship_style:
            db_service.soft_update_style(
                sender_id,
                receiver_id,
                new_style=message_style
            )

    return {
        "message_style": message_style,
        "relationship_style": relationship_style
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
