import pandas as pd
from datasets import load_dataset
import random
import sys
import re


# Temizleme fonksiyonu (Dışarıda tanımlanması gerekir)
def clean_text(text):
    text = re.sub(r"http\S+|www\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"#\w+", "", text)
    text = re.sub(r"[^a-zA-Z0-9çğıöşüÇĞİÖŞÜ\s.,!?]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def create_dataset_by_label():
    print("🚀 Veri seti oluşturuluyor (Winvoker Etiketlere Ayrılıyor)...\n")
    final_data = []

    # --- 1. FORMAL VERİ (WIKIPEDIA TR) - 40.000 HEDEF ---
    print("1️⃣ Formal Veriler (Wikipedia TR) indiriliyor...")

    # WikiANN/Wiki yerine daha büyük ve giriş gerektirmeyen Wikipedia'yı kullanıyoruz.
    try:
        ds_formal_wiki = load_dataset("oriental-lab/wikipedia-turkish", split="train", streaming=True)
        count = 0
        for item in ds_formal_wiki:
            text = clean_text(item["text"])
            if 40 < len(text) < 250:
                final_data.append({'text': text, 'label': 'formal'})
                count += 1
            if count == 40000: break
        print(f"   ✅ Formal veri tamamlandı. Çekilen: {count}")
    except Exception as e:
        print(f"   ❌ Formal/Wikipedia hata: {e}")
        # Hata durumunda boş geçip devam ediyoruz.

    # --- 2. INFORMAL VERİ (Winvoker + Diyalog + Toksik) - 40.000 HEDEF ---
    print("\n2️⃣ Informal Veriler (Winvoker + Diyalog + Toksik) taranıyor...")

    informal_count = 0

    # 2A) Winvoker (Sadece 'tweet-pn' — En saf Informal) – 10K HEDEF
    print(" - Winvoker ('tweet-pn') taranıyor...")
    try:
        ds_winvoker = load_dataset("winvoker/turkish-sentiment-analysis-dataset", split="train", streaming=True)
        for item in ds_winvoker:
            if item.get('dataset', '') == 'tweet-pn' and informal_count < 10000:
                text = clean_text(item['text'])
                if 15 < len(text) < 280:
                    final_data.append({'text': text, 'label': 'informal'})
                    informal_count += 1
        print(f"   ✔ Winvoker 'tweet-pn' → {informal_count}")
    except Exception as e:
        print(f"   ❌ Winvoker hata: {e}")

    # 2B) Turkish Dialog Dataset (Sohbet Metinleri) – 20K HEDEF
    print(" - TFLai/Turkish-Dialog-Dataset (20K) indiriliyor...")
    try:
        ds_dialog = load_dataset("TFLai/Turkish-Dialog-Dataset", split="train", streaming=True)
        dialog_count = 0
        while informal_count < 30000:  # 10K Winvoker + 20K Diyalog = 30K
            for item in ds_dialog:
                text = clean_text(item["text"])
                if 10 < len(text) < 180:
                    final_data.append({'text': text, 'label': 'informal'})
                    informal_count += 1
                    dialog_count += 1
                if informal_count == 30000: break
            break
        print(f"   ✔ Turkish Dialog → {dialog_count}")
    except Exception as e:
        print(f"   ❌ Turkish Dialog hata: {e}")

    # 2C) Turkish Toxic Language (Geriye Kalan ~10K)
    print(" - Overfit-GM/turkish-toxic-language (Kalan) indiriliyor...")
    try:
        ds_toxic = load_dataset("Overfit-GM/turkish-toxic-language", split="train", streaming=True)
        toxic_count = 0
        while informal_count < 40000:  # Toplam 40K hedefine ulaşana kadar çek
            for item in ds_toxic:
                text = clean_text(item["text"])
                if 10 < len(text) < 300:
                    final_data.append({'text': text, 'label': 'informal'})
                    informal_count += 1
                    toxic_count += 1
                if informal_count == 40000: break
            break
        print(f"   ✔ Turkish Toxic → {toxic_count}")
    except Exception as e:
        print(f"   ❌ Turkish Toxic hata: {e}")

    print(f"   ✅ Informal TOPLAM: {informal_count}")

    # --- 3. NEUTRAL VERİ (OPUS-100) - 40.000 HEDEF ---
    print("\n3️⃣ Neutral Veriler (OPUS-100) indiriliyor...")

    try:
        ds_neutral = load_dataset("opus100", "en-tr", split="train", streaming=True)
        count = 0
        for item in ds_neutral:
            tr_text = clean_text(item['translation']['tr'])
            if 25 < len(tr_text) < 100:
                final_data.append({'text': tr_text, 'label': 'neutral'})
                count += 1
            if count == 40000: break
        print(f"   ✅ Neutral veri tamamlandı. Çekilen: {count}")
    except Exception as e:
        print(f"   ❌ Neutral hata: {e}")

    # --- KAYDETME ve DENGELEME ---
    print("\n--- Veriler Kaydediliyor ve Dengeleniyor ---")
    if final_data:
        df = pd.DataFrame(final_data)

        # Son Veri Dağılımını Göster
        print("\n📊 HAM VERİ DAĞILIMI:")
        print(df['label'].value_counts())

        # Fazla olan etiketleri (Örn: Neutral) kırpalım ki dengeli olsun.
        min_count = df['label'].value_counts().min()

        if min_count > 0 and min_count < 40000:
            print(
                f"\n⚠️ Uyarı: En düşük veri sayısı ({min_count}) olduğu için tüm set {min_count * 3} veriye düşürülerek dengelenecektir.")

            balanced_df = pd.concat([
                df[df['label'] == 'formal'].sample(min_count, random_state=42),
                df[df['label'] == 'informal'].sample(min_count, random_state=42),
                df[df['label'] == 'neutral'].sample(min_count, random_state=42)
            ])
            df = balanced_df.sample(frac=1, random_state=42).reset_index(drop=True)

            print("\n📊 DENGELİ VERİ DAĞILIMI:")
            print(df['label'].value_counts())

        filename = "StyleAdapterDataset_Final_Balanced.csv"
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"\n✅ Dosya '{filename}' olarak kaydedildi. Toplam çekilen: {len(df)} veri.")
    else:
        print("\n❌ Veri toplanamadı. CSV dosyası oluşturulmadı.")


if __name__ == "__main__":
    create_dataset_by_label()