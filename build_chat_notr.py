"""
Chat-tarzı Notr cümleler oluştur ve train.csv'ye ekle.
Kaynaklar:
  1. Elle yazılmış sentetik chat nötr cümleler (temel kalıplar)
  2. Mevcut Notr verisinden kısa ve sade olanları filtrele
"""
import pandas as pd
import re
import random

random.seed(42)

# -----------------------------------------------------------------------
# 1. SENTETIK CHAT-NOTR CÜMLELERİ
# -----------------------------------------------------------------------
BASE_NOTR = [
    # Zaman / randevu
    "yarın görüşelim", "saat kaçta", "ne zaman geliyorsun", "bugün müsün",
    "biraz sonra gelirim", "akşama kadar buradayım", "sabah görüşürüz",
    "öğleden sonra uygun musun", "pazartesi nasıl", "hafta sonu boş musun",
    "saat üçte buluşalım", "yarın sende miyim", "akşam eve gel",
    "ne zaman konuşuruz", "sabah erken kalkıyorum", "öğle yemeği yedim",
    "biraz bekliyorum", "geliyorum şimdi", "beş dakika sonra oradayım",
    "cumartesi uygun musun", "pazar günü buluşalım", "akşam yemeğinde misin",
    "öğleden önce gel", "gece geç olur", "sabah uyandım",
    "şimdi hazırlanıyorum", "az sonra çıkıyorum", "yolda trafik var",
    "on dakika sonra gelirim", "yarın sabah erken buluşalım",

    # Onay / kabul / alındı
    "tamam anladım", "tamam ok", "tamamdır", "anladım teşekkürler",
    "bilgi için teşekkürler", "görüldü", "aldım mesajı", "ok anladım",
    "evet baktım", "tamamdır iyi günler", "olur tamam", "peki olur",
    "bakarım sonra", "ileteyim", "söylerim", "not ettim",
    "iletişimde olalım", "haberin olsun", "uygun olunca yazarım",
    "ileride konuşuruz", "sonra değerlendiririm", "dosyayı inceliyorum",
    "şu an bakamıyorum sonra bakarım", "haber veririm",

    # Soru / bilgi alma
    "neredesin şimdi", "ne yapıyorsun", "nasıl gidiyor",
    "ne var ne yok", "ne zaman dönersin", "nerede buluşacağız",
    "adresi atar mısın", "numarayı gönderir misin", "hangi durakta",
    "kaç tane lazım", "ne kadar sürer", "kim gelecek",
    "hangi saatte başlıyor", "nerede park edeceksin", "kaçıncı katta",
    "beni arar mısın", "ne istiyorsun", "nasıl bir yer orası",
    "bu hafta müsait misin", "toplantı ne zaman",

    # Günlük hayat
    "market çıkışında alırım", "eve geldim", "yoldayım",
    "işten çıktım", "uykum geldi", "kahve içiyorum şimdi",
    "yemek yapıyorum", "telefonda görüşeyim mi", "mail attım",
    "dosyayı gönderdim", "bakıyorum şu an", "internete bakıyorum",
    "bilgisayarım açık", "toplantıdayım birazdan çıkarım",
    "ofisteyim", "evden çalışıyorum", "dışarıdayım",
    "markete gidiyorum", "ders çalışıyorum", "bir iş çıktı",
    "az önce uyandım", "gece yarısı dönerim", "sabah erken çıkıyorum",

    # Belirsiz / kararsız
    "ya ne bileyim", "bilmiyorum henüz", "düşüneyim",
    "emin değilim", "bakalım", "göreceğiz", "henüz karar vermedim",
    "fikrim yok şu an", "soruyorum araştırıyorum", "not aldım",
    "kafam karışık henüz", "henüz bilemedim", "araştırıyorum",
    "belki olur belki olmaz", "netleştirince yazarım",
    "şu an belirsiz", "koşullara göre", "görüşürüz",

    # Kısa nötr tepkiler
    "hm", "hmm tamam", "aa anladım", "oh öyle mi",
    "gerçekten mi", "var mı öyle", "anlıyorum", "peki",
    "dur bir saniye", "bekle bakayım", "evet evet",
    "aha", "oooh", "aaa", "yok öyle bir şey",
    "sen bilirsin", "nasıl istersen", "fark etmez benim için",
    "istersin", "istersen öyle yapalım", "ne dersen",

    # Bilgi paylaşımı (nötr)
    "link attım bak", "fotoğraf gönderdim", "dosya geldi mi",
    "iki saat sürer", "yirmi lira tutar", "üç kişiyiz",
    "toplantı saat ikide", "adres şu şekilde", "dün gönderdim",
    "geçen hafta konuşmuştuk", "hatırlıyor musun", "geçenlerde bahsettim",
]

def make_variants(sentences, n=3000):
    """Tekrar içermeyecek şekilde varyant üret."""
    typo_map = {"ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ı": "i", "ç": "c"}
    abbrevs  = {"tamam": "tmm", "anladım": "anladm", "teşekkürler": "tsk",
                "bilmiyorum": "bilmyrm", "görüşelim": "goruselim",
                "tamamdır": "tamamdir", "bakıyorum": "bakiyorum"}
    fillers  = ["ya", "hani", "yani", "şey", "lan", "abi", "canım", ""]
    suffixes = ["", " ya", " yani", " hani", " abi", " tamam mı", " ok mu"]

    seen = set(sentences)
    variants = list(sentences)

    attempts = 0
    while len(variants) < n and attempts < n * 20:
        attempts += 1
        base = random.choice(sentences)
        mods = []

        r = random.random()
        if r < 0.20:
            for k, v in typo_map.items():
                if k in base and random.random() < 0.5:
                    base = base.replace(k, v, 1)
                    mods.append("typo")
                    break
        if r < 0.35:
            for k, v in abbrevs.items():
                if k in base:
                    base = base.replace(k, v, 1)
                    mods.append("abbrev")
                    break
        if random.random() < 0.25:
            filler = random.choice(fillers)
            if filler:
                base = filler + " " + base
        if random.random() < 0.20:
            base = base + random.choice(suffixes)
        if random.random() < 0.15:
            base = base.capitalize()
        if random.random() < 0.10 and not base.endswith("?"):
            base = base + "?"

        base = base.strip()
        if base not in seen and len(base) > 3:
            seen.add(base)
            variants.append(base)

    return variants[:n]

chat_notr = make_variants(BASE_NOTR, n=3000)
chat_notr_df = pd.DataFrame({
    "text":    chat_notr,
    "label":   "Notr",
    "dataset": "chat_notr"
})

print(f"Uretilen chat-notr ornegi: {len(chat_notr_df)}")
print("Ornekler:")
for s in chat_notr[:10]:
    print(f"  {s}")

# -----------------------------------------------------------------------
# 2. MEVCUT TRAIN'DEN KISA NOTR CUMLELER (wiki'den sade olanlar)
# -----------------------------------------------------------------------
print("\nMevcut Notr filtreleniyor...")
train = pd.read_csv("train.csv", encoding="utf-8")
wiki_notr = train[train["dataset"] == "wiki"].copy()
# Kısa (10-80 karakter), tek cümle, rakam içermeyenler
wiki_short = wiki_notr[
    (wiki_notr["text"].str.len() >= 10) &
    (wiki_notr["text"].str.len() <= 80) &
    (~wiki_notr["text"].str.contains(r'\d{4}', na=False)) &
    (~wiki_notr["text"].str.contains(r'http', na=False))
].sample(n=min(2000, len(wiki_notr)), random_state=42)

print(f"Wiki'den secilen kisa Notr: {len(wiki_short)}")

# -----------------------------------------------------------------------
# 3. AUGMENTED TRAIN CSV KAYDET
# -----------------------------------------------------------------------
augmented = pd.concat([train, chat_notr_df, wiki_short[["text","label","dataset"]]], ignore_index=True)
augmented = augmented.sample(frac=1, random_state=42).reset_index(drop=True)
augmented.to_csv("train_augmented.csv", index=False, encoding="utf-8")

print(f"\nAugmented veri kaydedildi: train_augmented.csv")
print(f"Toplam satır: {len(augmented):,}")
print(augmented["label"].value_counts())
