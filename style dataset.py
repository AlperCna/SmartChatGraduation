import pandas as pd
from datasets import load_dataset
import random
import re
import sys


# ==========================================
# 1. TEMİZLEME VE FİLTRELEME
# ==========================================

def clean_text_standard(text):
    text = str(text)
    # Linkleri ve etiketleri temizle
    text = re.sub(r"http\S+|www\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"#\w+", "", text)

    # Sadece harf, rakam ve noktalama kalsın (Büyük/Küçük harfe DOKUNMA)
    text = re.sub(r"[^a-zA-Z0-9çğıöşüÇĞİÖŞÜ\s.,!?:;\"\'\-\(\)]", " ", text)
    text = re.sub(r'([.,!?:;])(?=[^\s])', r'\1 ', text)  # Noktalamadan sonra boşluk
    text = re.sub(r"\s+", " ", text).strip()
    return text


# Informal Filtresi (Bu kelimeler Informal içinde geçmemeli)
FORBIDDEN_IN_INFORMAL = [
    "arz ederim", "rica ederim", "saygılarımla", "tarafınıza", "tarafıma",
    "sayın", "bey", "hanım", "efendim", "bilgilerinize", "gereğini",
    "işbu", "dilekçe", "başvuru", "onayınıza", "lütfen", "teşekkür ederim",
    "yardımcı olabilir misiniz", "mümkün müdür", "iletiniz", "yapınız",
    "sağlayınız", "dönüş yapabilir misiniz", "isterim", "beklemekteyim",
    "merhabalar", "iyi çalışmalar", "kolay gelsin", "kurum", "müdürlüğü",
    "belirtildi", "ifade edildi", "kaydedildi", "açıklandı"  # Haber dili fiilleri
]


def is_contaminated(text):
    text_lower = text.lower()
    for word in FORBIDDEN_IN_INFORMAL:
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
            return True
    return False


# ==========================================
# 2. VERİ SETİ OLUŞTURMA (REAL DATA ONLY)
# ==========================================

def create_dataset_real_final():
    print("🚀 STYLE ADAPTER (Hukuk + Wiki + TTC4900 + Interpress) OLUŞTURULUYOR...\n")
    final_data = []

    # ---------------------------------------------------------
    # 1. FORMAL VERİ (Toplam 40.000)
    # ---------------------------------------------------------
    print("👔 FORMAL veri toplanıyor (Hedef: 40,000)...")
    formal_count = 0

    # 1A) Hukuki Metinler (10K)
    print("   🔹 [1/4] Hukuki Metinler (Legal NLI)...")
    try:
        ds = load_dataset("Turkish-NLI/legal_nli_TR_V1", split="train", streaming=True)
        count = 0
        for item in ds:
            text = clean_text_standard(item["premise"])
            if 50 < len(text) < 500:
                final_data.append({'text': text, 'label': 'formal'})
                count += 1
                formal_count += 1
            if count == 10000: break
        print(f"      ✔ Hukuk Tamam: {count}")
    except Exception as e:
        print(f"      ❌ Hata: {e}")

    # 1B) Haberler - TTC4900 (10K)
    # Kategori Filtresi: 0:Ekonomi, 2:Sağlık, 3:Siyaset, 5:Teknoloji, 6:Dünya
    # (1:Kültür ve 4:Spor'u almayalım, bazen laubali olabilirler)
    print("   🔹 [2/4] Haberler (TTC4900 - Siyaset/Ekonomi/Teknoloji)...")
    try:
        ds = load_dataset("savasy/ttc4900", split="train", streaming=True)
        count = 0
        for item in ds:
            if item['category'] in [0, 2, 3, 5, 6]:
                text = clean_text_standard(item["text"])
                # Haberler çok uzun olabilir, ilk 400 karakteri (özeti) alalım
                if len(text) > 50:
                    text_cut = text[:400]
                    final_data.append({'text': text_cut, 'label': 'formal'})
                    count += 1
                    formal_count += 1
            if count == 10000: break
        print(f"      ✔ TTC4900 Tamam: {count}")
    except Exception as e:
        print(f"      ❌ Hata: {e}")

    # 1C) Haberler - Interpress (10K)
    print("   🔹 [3/4] Haberler (Interpress)...")
    try:
        ds = load_dataset("yavuzkomecoglu/interpress_news_category_tr", split="train", streaming=True)
        count = 0
        for item in ds:
            # Interpress genel olarak düzgün haber metinleridir
            text = clean_text_standard(item["text"])
            if len(text) > 50:
                text_cut = text[:400]  # Yine çok uzun olmasın diye kesiyoruz
                final_data.append({'text': text_cut, 'label': 'formal'})
                count += 1
                formal_count += 1
            if count == 10000: break
        print(f"      ✔ Interpress Tamam: {count}")
    except Exception as e:
        print(f"      ❌ Hata: {e}")

    # 1D) Wikipedia TR (10K veya Kalanı Tamamla)
    print("   🔹 [4/4] Wikipedia TR (Tamamlayıcı)...")
    try:
        ds = load_dataset("oriental-lab/wikipedia-turkish", split="train", streaming=True)
        count = 0
        target_wiki = 40000 - formal_count  # Eksik kalan kısmı Wiki ile doldur

        if target_wiki > 0:
            for item in ds:
                text = clean_text_standard(item["text"])
                if 60 < len(text) < 400:
                    final_data.append({'text': text, 'label': 'formal'})
                    count += 1
                    formal_count += 1
                if count >= target_wiki: break
        print(f"      ✔ Wiki Tamam: {count}")
    except Exception as e:
        print(f"      ❌ Hata: {e}")

    print(f"   ✅ FORMAL TOPLAM: {formal_count}")

    # ---------------------------------------------------------
    # 2. INFORMAL VERİ (Toplam 40.000) - SIKI FİLTRELİ
    # ---------------------------------------------------------
    print("\n💬 INFORMAL veri toplanıyor (Hedef: 40,000)...")
    print("   ⚠️  FİLTRE AKTİF: 'Lütfen/Rica/Belirtildi' geçenler atılıyor.")
    informal_count = 0

    # 2A) Winvoker Tweet-PN
    print("   🔸 [1/3] Winvoker (Tweet-PN)...")
    try:
        ds = load_dataset("winvoker/turkish-sentiment-analysis-dataset", split="train", streaming=True)
        count = 0
        for item in ds:
            if item.get('dataset') == 'tweet-pn':
                raw_text = item['text']
                if is_contaminated(raw_text): continue

                text = clean_text_standard(raw_text)
                if 15 < len(text) < 280:
                    final_data.append({'text': text, 'label': 'informal'})
                    count += 1
                    informal_count += 1
            if count == 13000: break
        print(f"      ✔ Winvoker Tamam: {count}")
    except Exception as e:
        print(f"Hata: {e}")

    # 2B) Turkish Dialog Dataset
    print("   🔸 [2/3] Turkish Dialog...")
    try:
        ds = load_dataset("TFLai/Turkish-Dialog-Dataset", split="train", streaming=True)
        count = 0
        while informal_count < 30000:
            for item in ds:
                raw_text = item["text"]
                if is_contaminated(raw_text): continue

                text = clean_text_standard(raw_text)
                if 10 < len(text) < 200:
                    final_data.append({'text': text, 'label': 'informal'})
                    count += 1
                    informal_count += 1
                if informal_count == 30000: break
            break
        print(f"      ✔ Dialog Tamam: {count}")
    except Exception as e:
        print(f"Hata: {e}")

    # 2C) Toxic Language
    print("   🔸 [3/3] Toxic Language...")
    try:
        ds = load_dataset("Overfit-GM/turkish-toxic-language", split="train", streaming=True)
        count = 0
        while informal_count < 40000:
            for item in ds:
                raw_text = item["text"]
                text = clean_text_standard(raw_text)
                if 10 < len(text) < 300:
                    final_data.append({'text': text, 'label': 'informal'})
                    count += 1
                    informal_count += 1
                if informal_count == 40000: break
            break
        print(f"      ✔ Toxic Tamam: {count}")
    except Exception as e:
        print(f"Hata: {e}")

    print(f"   ✅ INFORMAL TOPLAM: {informal_count}")

    # ---------------------------------------------------------
    # 3. KAYDETME
    # ---------------------------------------------------------
    if final_data:
        df = pd.DataFrame(final_data)
        min_count = df['label'].value_counts().min()
        print(f"\n⚖️ Dengeleme (Her sınıf {min_count} adet)...")

        balanced_df = pd.concat([
            df[df['label'] == 'formal'].sample(min_count, random_state=42),
            df[df['label'] == 'informal'].sample(min_count, random_state=42)
        ])

        final_df = balanced_df.sample(frac=1, random_state=42).reset_index(drop=True)
        filename = "StyleAdapter_Real_80K.csv"
        final_df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"\n✅ BAŞARILI! Dosya '{filename}' olarak kaydedildi.")
        print(f"   Toplam Satır: {len(final_df)}")
    else:
        print("Veri yok.")


if __name__ == "__main__":
    create_dataset_real_final()