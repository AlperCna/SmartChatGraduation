# ai_module/style_detector_gpt.py

from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def detect_style_gpt(text: str) -> str:
    prompt = f"""
Sen Türkçe yazım üslupları konusunda uzmansın.

Görev:
Aşağıdaki Türkçe mesajın **yazım üslubunu (style)** sınıflandır.

Üslup kategorileri:

- formal:
  Saygılı, mesafeli ve nezaket içeren dil.
  Genellikle şu tür ifadeler bulunur:
  "Sayın", "rica ederim", "müsait olursanız", "teşekkür ederim",
  "uygun mudur", "iyi çalışmalar", "arz ederim".

- informal:
  Samimi, günlük, rahat veya argo dil.
  Örnekler:
  "kanka", "abi", "ya", "naber", "selam", kısaltmalar, emojisiz bile olsa
  konuşma dili.

- neutral:
  Ne resmi ne samimi olan, düz ve tarafsız dil.
  Ne güçlü nezaket ne de yakınlık içerir.

Önemli kurallar:
- DUYGUYA (pozitif/negatif) bakma, sadece üsluba bak.
- KISA ama NAZİK rica cümleleri (argo içermiyorsa) **formal** kabul edilir.
- Hitap içermeyen ama kibar sorular **formal** olabilir.
- Kararsız kaldığında **neutral** yerine **formal** seç.

Mesaj:
"{text}"

Cevap:
Sadece şu kelimelerden BİRİNİ yaz:
formal / neutral / informal
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=3
    )

    return response.choices[0].message.content.strip().lower()
