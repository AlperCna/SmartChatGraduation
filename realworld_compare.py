"""
V1 vs V2 Gerçek Dünya Karşılaştırması
--------------------------------------
Mod 1: Veritabanından gerçek mesajlar çek ve karşılaştır
Mod 2: Elle mesaj gir, anında karşılaştır
"""
import pickle
import re
import sys
import warnings
import os
from dotenv import load_dotenv

load_dotenv()
warnings.filterwarnings("ignore")

# -----------------------------------------------------------------------
# NORMALIZE
# -----------------------------------------------------------------------
def normalize(text):
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r'http\S+|www\S+|\S+@\S+', ' ', text)
    text = re.sub(r'(.)\1{2,}', r'\1\1', text)
    text = re.sub(r'[^\w\sA-z\xC0-ɏ]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# -----------------------------------------------------------------------
# MODEL YUKLE
# -----------------------------------------------------------------------
print("Modeller yukleniyor...")

try:
    with open("sentiment_model.pkl", "rb") as f:
        v1_model = pickle.load(f)
    with open("tfidf_vectorizer.pkl", "rb") as f:
        v1_vec = pickle.load(f)
    v1_ok = True
    print("  V1 (LR + TF-IDF)  : yuklendi")
except Exception as e:
    v1_ok = False
    print(f"  V1                 : YUKLENEMEDI ({e})")

try:
    with open("sentiment_model_v2.pkl", "rb") as f:
        v2_pipeline = pickle.load(f)
    v2_ok = True
    print("  V2 (LinearSVC + word+char n-gram): yuklendi")
except Exception as e:
    v2_ok = False
    print(f"  V2                 : YUKLENEMEDI ({e})")

print()

# -----------------------------------------------------------------------
# TAHMİN FONKSİYONLARI
# -----------------------------------------------------------------------
SENTIMENT_EMOJI = {"Positive": "[+]", "Negative": "[-]", "Notr": "[~]",
                   "positive": "[+]", "negative": "[-]", "notr": "[~]"}

def predict_v1(text):
    if not v1_ok:
        return "—", 0.0
    try:
        x    = v1_vec.transform([text])
        pred = v1_model.predict(x)[0]
        conf = float(v1_model.predict_proba(x).max())
        # V1 lowercase döndürür, düzelt
        mapping = {"positive": "Positive", "negative": "Negative", "notr": "Notr"}
        pred = mapping.get(pred.lower(), pred)
        return pred, conf
    except Exception as e:
        return f"HATA({e})", 0.0

def predict_v2(text):
    if not v2_ok:
        return "—", 0.0
    try:
        norm = normalize(text)
        if not norm:
            return "Notr", 0.0
        pred = v2_pipeline.predict([norm])[0]
        conf = float(v2_pipeline.predict_proba([norm]).max())
        if conf < 0.52 and pred != "Notr":
            pred = "Notr"
        return pred, conf
    except Exception as e:
        return f"HATA({e})", 0.0

def compare_line(text, expected=None):
    p1, c1 = predict_v1(text)
    p2, c2 = predict_v2(text)

    e1 = SENTIMENT_EMOJI.get(p1, "[ ]")
    e2 = SENTIMENT_EMOJI.get(p2, "[ ]")

    agree   = "AYNI    " if p1 == p2 else "FARKLI  "
    v1_mark = ""
    v2_mark = ""
    if expected:
        v1_mark = " OK" if p1 == expected else " XX"
        v2_mark = " OK" if p2 == expected else " XX"

    print(f"  Mesaj   : {text}")
    print(f"  V1      : {e1} {p1:<10}  (guven: {c1:.2f}){v1_mark}")
    print(f"  V2      : {e2} {p2:<10}  (guven: {c2:.2f}){v2_mark}")
    print(f"  Durum   : {agree}{'  Beklenen: ' + expected if expected else ''}")
    print()

# -----------------------------------------------------------------------
# MOD 1: VERİTABANINDAN GERCEK MESAJLAR
# -----------------------------------------------------------------------
def fetch_real_messages(limit=30):
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "smartchat"),
            port=int(os.getenv("DB_PORT", 3306))
        )
        cursor = conn.cursor(dictionary=True)
        # Sistem mesajlarını filtrele, gerçek metin mesajları al
        cursor.execute("""
            SELECT content, sender_id
            FROM messages
            WHERE content IS NOT NULL
              AND content != ''
              AND content NOT IN ('image', 'video', 'audio', 'file', 'location')
              AND LENGTH(content) > 3
              AND LENGTH(content) < 300
            ORDER BY RAND()
            LIMIT %s
        """, (limit,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r["content"] for r in rows]
    except Exception as e:
        print(f"  Veritabani hatasi: {e}")
        return []

def run_db_mode():
    print("=" * 65)
    print("MOD 1: VERITABANINDAN GERCEK MESAJLAR")
    print("=" * 65)
    print("Kac mesaj cekilsin? (Enter = 20): ", end="")
    try:
        n = int(input().strip() or "20")
    except ValueError:
        n = 20

    print(f"\nVeritabanindan {n} rastgele mesaj cekiliyor...\n")
    messages = fetch_real_messages(n)

    if not messages:
        print("Mesaj cekemedim. DB baglantisini kontrol et veya Manuel moda gec.\n")
        return

    v1_counts = {"Positive": 0, "Negative": 0, "Notr": 0}
    v2_counts = {"Positive": 0, "Negative": 0, "Notr": 0}
    agree_count = 0

    print(f"{'#':<3} {'V1':<12} {'V2':<12} {'C1':>5} {'C2':>5}  Mesaj")
    print("-" * 75)

    for i, msg in enumerate(messages, 1):
        p1, c1 = predict_v1(msg)
        p2, c2 = predict_v2(msg)
        flag = "  <-- FARKLI" if p1 != p2 else ""
        print(f"{i:<3} {p1:<12} {p2:<12} {c1:>5.2f} {c2:>5.2f}  {msg[:40]}{flag}")

        v1_counts[p1] = v1_counts.get(p1, 0) + 1
        v2_counts[p2] = v2_counts.get(p2, 0) + 1
        if p1 == p2:
            agree_count += 1

    total = len(messages)
    print()
    print("=" * 65)
    print("OZET")
    print("=" * 65)
    print(f"{'Sinif':<12} {'V1 Sayi':>8} {'V1 %':>7}   {'V2 Sayi':>8} {'V2 %':>7}")
    print("-" * 50)
    for cls in ["Positive", "Notr", "Negative"]:
        v1n = v1_counts.get(cls, 0)
        v2n = v2_counts.get(cls, 0)
        print(f"{cls:<12} {v1n:>8}  {v1n/total*100:>6.1f}%   {v2n:>8}  {v2n/total*100:>6.1f}%")

    print(f"\nModeller {agree_count}/{total} mesajda AYNI kararı verdi ({agree_count/total*100:.0f}%)")
    diff = total - agree_count
    if diff > 0:
        print(f"Modeller {diff} mesajda FARKLI karar verdi — bunlara dikkat et!")
    print()

# -----------------------------------------------------------------------
# MOD 2: MANUEL GİRİŞ
# -----------------------------------------------------------------------
def run_manual_mode():
    print("=" * 65)
    print("MOD 2: MANUEL MESAJ GIRISI")
    print("Cikis icin 'q' yaz.")
    print("=" * 65)
    print()

    session_results = []

    while True:
        try:
            text = input("Mesaj: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if text.lower() in ("q", "quit", "exit", "cikis"):
            break
        if not text:
            continue

        p1, c1 = predict_v1(text)
        p2, c2 = predict_v2(text)
        e1 = SENTIMENT_EMOJI.get(p1, "")
        e2 = SENTIMENT_EMOJI.get(p2, "")
        agree = p1 == p2

        print(f"  V1: {e1} {p1:<10} (guven: {c1:.2f})")
        print(f"  V2: {e2} {p2:<10} (guven: {c2:.2f})")
        if agree:
            print("  --> Her iki model AYNI kararı verdi.")
        else:
            print(f"  --> FARKLI KARAR! V1={p1}, V2={p2}")
        print()

        session_results.append((text, p1, c1, p2, c2))

    if len(session_results) > 1:
        print("=" * 65)
        print("OTURUM OZETI")
        print("=" * 65)
        agreements = sum(1 for r in session_results if r[1] == r[3])
        print(f"Toplam test: {len(session_results)}")
        print(f"Ayni karar: {agreements}/{len(session_results)}")
        farklilar = [(r[0], r[1], r[3]) for r in session_results if r[1] != r[3]]
        if farklilar:
            print("\nFarkli karar verilen mesajlar:")
            for msg, v1r, v2r in farklilar:
                print(f"  V1={v1r:<10} V2={v2r:<10} | {msg}")
        print()

# -----------------------------------------------------------------------
# MOD 3: HAZIR KATEGORI TESTLERİ
# -----------------------------------------------------------------------
PRESET_TESTS = {
    "Gunluk Chat": [
        ("tamam anlıyorum",              "Notr"),
        ("yarın görüşürüz",              "Notr"),
        ("ne yapıyorsun şimdi",          "Notr"),
        ("saat kaçta buluşuyoruz",       "Notr"),
        ("yoldayım birazdan gelirim",    "Notr"),
        ("haber ver bana",               "Notr"),
        ("iyi geceler",                  "Notr"),
        ("nasılsın",                     "Notr"),
        ("tamam ok",                     "Notr"),
        ("peki olur",                    "Notr"),
    ],
    "Pozitif Mesajlar": [
        ("seni çok seviyorum",           "Positive"),
        ("harika bir gün geçirdim",      "Positive"),
        ("teşekkürler çok iyi oldu",     "Positive"),
        ("bu muhteşemdi gerçekten",      "Positive"),
        ("çok mutlu hissediyorum",       "Positive"),
        ("mükemmel bir akşamdı",         "Positive"),
        ("süpersin ya",                  "Positive"),
        ("çok beğendim",                 "Positive"),
    ],
    "Negatif Mesajlar": [
        ("çok sinirli hissediyorum",     "Negative"),
        ("bu gerçekten berbattı",        "Negative"),
        ("neden böyle davranıyorsun",    "Negative"),
        ("moralim çok bozuk",            "Negative"),
        ("hiç beğenmedim",               "Negative"),
        ("bu saçmalık",                  "Negative"),
        ("çok kötü hissediyorum",        "Negative"),
        ("artık dayanamıyorum",          "Negative"),
    ],
    "Zor Vakalar": [
        ("fena değildi aslında",         "Positive"),
        ("tamam ama çok yoruldum",       "Negative"),
        ("güzel ama pahalıydı",          "Positive"),
        ("idare eder gider",             "Notr"),
        ("neyse geçti",                  "Notr"),
        ("olur mu bilmiyorum",           "Notr"),
        ("belki güzel belki değil",      "Notr"),
        ("eh işte",                      "Notr"),
    ],
}

def run_preset_mode():
    print("=" * 65)
    print("MOD 3: HAZIR KATEGORI TESTLERI")
    print("=" * 65)

    total_v1 = total_v2 = total_all = 0

    for category, tests in PRESET_TESTS.items():
        print(f"\n--- {category} ---")
        print(f"{'Mesaj':<40} {'Beklenen':<12} {'V1':<12} {'V2':<12}")
        print("-" * 80)

        cat_v1 = cat_v2 = 0
        for text, expected in tests:
            p1, c1 = predict_v1(text)
            p2, c2 = predict_v2(text)
            ok1 = "OK" if p1 == expected else "XX"
            ok2 = "OK" if p2 == expected else "XX"
            if p1 == expected: cat_v1 += 1
            if p2 == expected: cat_v2 += 1
            flag = " <--" if ok1 == "XX" and ok2 == "OK" else (" -->" if ok1 == "OK" and ok2 == "XX" else "")
            print(f"{text:<40} {expected:<12} {p1+' '+ok1:<12} {p2+' '+ok2:<12}{flag}")

        n = len(tests)
        print(f"Kategori skoru: V1={cat_v1}/{n} (%{cat_v1/n*100:.0f})  V2={cat_v2}/{n} (%{cat_v2/n*100:.0f})")
        total_v1 += cat_v1
        total_v2 += cat_v2
        total_all += n

    print("\n" + "=" * 65)
    print("GENEL SKOR")
    print("=" * 65)
    print(f"V1: {total_v1}/{total_all} = %{total_v1/total_all*100:.0f}")
    print(f"V2: {total_v2}/{total_all} = %{total_v2/total_all*100:.0f}")
    fark = total_v2 - total_v1
    print(f"V2, V1'den {abs(fark)} mesaj {'daha dogru' if fark >= 0 else 'daha yanlis'} siniflandirdi.")
    print()

# -----------------------------------------------------------------------
# ANA MENU
# -----------------------------------------------------------------------
if __name__ == "__main__":
    print()
    print("=" * 65)
    print("  SENTIMENT MODEL GERCEK DUNYA KARSILASTIRMASI")
    print("  V1 (LR + TF-IDF)  vs  V2 (LinearSVC + word+char n-gram)")
    print("=" * 65)
    print()
    print("  1 - Veritabanindan gercek mesajlar cek ve karsilastir")
    print("  2 - Manuel mesaj gir (interaktif)")
    print("  3 - Hazir kategori testleri (gunluk/pozitif/negatif/zor)")
    print("  4 - Hepsini calistir (3, 1, 2 sirasi ile)")
    print()
    print("Seciminiz (1/2/3/4): ", end="")

    try:
        choice = input().strip()
    except (EOFError, KeyboardInterrupt):
        choice = "3"

    if choice == "1":
        run_db_mode()
    elif choice == "2":
        run_manual_mode()
    elif choice == "3":
        run_preset_mode()
    elif choice == "4":
        run_preset_mode()
        run_db_mode()
        run_manual_mode()
    else:
        print("Gecersiz secim, hazir testler calistiriliyor...\n")
        run_preset_mode()
