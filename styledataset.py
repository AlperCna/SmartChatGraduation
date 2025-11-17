import pandas as pd
from datasets import load_dataset
import random
import sys


def create_dataset_by_label():
    print("🚀 Veri seti oluşturuluyor (Tweet-PN Etiketli)...\n")

    final_data = []

    # 1. FORMAL VERİ (WikiANN - Wikipedia) - AYNI KALDI
    print("1️⃣ Formal Veriler (Wikipedia) indiriliyor...")
    try:
        ds_formal = load_dataset("wikiann", "tr", split="train", streaming=True)
        count = 0
        for item in ds_formal:
            text = " ".join(item['tokens']).replace(" .", ".").replace(" ,", ",")
            if 40 < len(text) < 250:
                final_data.append({'text': text, 'label': 'formal'})
                count += 1
                if count % 100 == 0:
                    sys.stdout.write(f"\r   ⏳ Formal: {count}/1000")
                    sys.stdout.flush()
            if count == 1000: break
        print(f"\n   ✅ Formal veri tamam.")
    except Exception as e:
        print(f"   ❌ Formal hata: {e}")

    # 2. INFORMAL VERİ (Winvoker - SADECE 'tweet-pn' OLANLAR)
    print("\n2️⃣ Informal Veriler (Winvoker: tweet-pn) taranıyor...")
    try:
        # Winvoker veri setini yüklüyoruz
        ds_informal = load_dataset("winvoker/turkish-sentiment-analysis-dataset", split="train", streaming=True)

        count = 0
        for item in ds_informal:
            # Ekran görüntüsündeki "tweet-pn" etiketini 'dataset' sütununda arıyoruz.
            # Eğer item içinde 'dataset' sütunu varsa ve değeri 'tweet-pn' ise alıyoruz.
            source_label = item.get('dataset', '')

            if source_label == 'tweet-pn':
                text = item['text'].replace('\n', ' ').strip()

                # Yine de çok kısa (tek kelime) veya çok uzun olanları eleyelim
                if 15 < len(text) < 280:
                    final_data.append({'text': text, 'label': 'informal'})
                    count += 1

                    if count % 100 == 0:
                        sys.stdout.write(f"\r   ⏳ Informal: {count}/1000")
                        sys.stdout.flush()

            if count == 1000: break

        if count < 1000:
            print(f"\n   ⚠️ Uyarı: Sadece {count} adet tweet-pn bulundu. (Streaming modunda az gelmiş olabilir)")
        else:
            print(f"\n   ✅ Informal veri (tweet-pn) tamam.")

    except Exception as e:
        print(f"   ❌ Informal hata: {e}")


    # 3. NEUTRAL VERİ (OPUS-100) - AYNI KALDI
    print("\n3️⃣ Neutral Veriler (Kitap/Altyazı) indiriliyor...")
    try:
        ds_neutral = load_dataset("opus100", "en-tr", split="train", streaming=True)
        count = 0
        for item in ds_neutral:
            tr_text = item['translation']['tr'].replace('\n', ' ').strip()
            if 25 < len(tr_text) < 100:
                clean_text = tr_text.replace('"', '').replace("'", "")
                final_data.append({'text': clean_text, 'label': 'neutral'})
                count += 1
            if count == 1000: break
        print(f"   ✅ Neutral veri tamam.")
    except Exception as e:
        print(f"   ❌ Neutral hata: {e}")


    # KAYDETME

    if final_data:
        df = pd.DataFrame(final_data)
        df = df.sample(frac=1, random_state=42).reset_index(drop=True)

        print("\n📊 VERİ DAĞILIMI:")
        print(df['label'].value_counts())

        filename = "StyleApapterDataset.csv"
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"\n✅ Dosya '{filename}' olarak kaydedildi. Tam istediğin gibi tweet-pn verileri alındı!")
    else:
        print("\n❌ Veri toplanamadı.")


if __name__ == "__main__":
    create_dataset_by_label()