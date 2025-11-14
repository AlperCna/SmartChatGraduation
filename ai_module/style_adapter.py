# ai_module/style_adapter.py

from backend.services import db_service
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
print("API Key test:", os.getenv("OPENAI_API_KEY")[:6], "...")  # sadece ilk 6 karakter

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def detect_style(sender_id, receiver_id, last_message=None):
    """
    İki kullanıcı arasındaki ilişki seviyesine göre stil belirler.
    Kayıt yoksa GPT ile tespit eder ve DB'ye ekler.
    """
    relationship = db_service.get_relationship(sender_id, receiver_id)
    if relationship and relationship.get("style"):
        return relationship["style"]

    if last_message:
        prompt = f"""
        Mesaj: "{last_message}"
        Görev: Bu mesajın tonunu belirle. 
        Sadece 'formal', 'neutral' veya 'informal' olarak cevap ver.
        """
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=5
        )
        detected_style = response.choices[0].message.content.strip().lower()

        if not relationship:
            db_service.create_relationship(sender_id, receiver_id, detected_style, 50)
        else:
            db_service.update_relationship(sender_id, receiver_id, style=detected_style)

        return detected_style

    return "neutral"


def adapt_style(text, style):
    """
    Cümleyi verilen üsluba göre uyarlar.
    """
    if style == "formal":
        # Baş harfi büyük yap, kısaltma ve argo kaldır
        return text.capitalize().replace("ya", "").replace("kanka", "").strip()

    elif style == "informal":
        # Daha samimi dil
        return text.lower().replace("merhaba", "selam").replace("selamlar", "selam")

    return text


# Test
if __name__ == "__main__":
    sample_text = "merhaba nasılsın"
    print("Formal:", adapt_style(sample_text, "formal"))
    print("Informal:", adapt_style(sample_text, "informal"))
    print("Neutral:", adapt_style(sample_text, "neutral"))
