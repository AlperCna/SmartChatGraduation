"""
V1 (TF-IDF + LogisticRegression, dengesiz veri) vs
V2 (TF-IDF word+char n-gram + LinearSVC, dengeli veri)
karsilastirmali test.
"""
import pickle, re, warnings
import pandas as pd
import numpy as np
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
warnings.filterwarnings("ignore")

# -----------------------------------------------------------------------
# NORMALIZE (v2 ile ayni)
# -----------------------------------------------------------------------
def normalize(text):
    if not isinstance(text, str): return ""
    text = text.lower()
    text = re.sub(r'http\S+|www\S+|\S+@\S+', ' ', text)
    text = re.sub(r'(.)\1{2,}', r'\1\1', text)
    text = re.sub(r'[^\w\sA-zÀ-ɏ]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# -----------------------------------------------------------------------
# MODELLER
# -----------------------------------------------------------------------
print(">> Modeller yukleniyor...")
with open("sentiment_model.pkl", "rb") as f:
    v1_model = pickle.load(f)
with open("tfidf_vectorizer.pkl", "rb") as f:
    v1_vec = pickle.load(f)
with open("sentiment_model_v2.pkl", "rb") as f:
    v2_pipeline = pickle.load(f)
print(">> Yüklendi.\n")

def predict_v1(text):
    x = v1_vec.transform([text])
    pred = v1_model.predict(x)[0]
    conf = float(v1_model.predict_proba(x).max())
    return pred, conf

def predict_v2(text):
    norm = normalize(text)
    pred = v2_pipeline.predict([norm])[0]
    conf = float(v2_pipeline.predict_proba([norm]).max())
    return pred, conf

# -----------------------------------------------------------------------
# 1. TEST CSV DEĞERLENDİRMESİ
# -----------------------------------------------------------------------
print("=" * 60)
print("BÖLÜM 1: TEST.CSV ÜZERİNDE KARŞILAŞTIRMA")
print("=" * 60)

test_df = pd.read_csv("test.csv", encoding="utf-8").dropna(subset=["text","label"])
test_df = test_df[test_df["label"].isin(["Positive","Negative","Notr"])].sample(
    n=min(3000, len(test_df)), random_state=42
)
print(f"Test ornekleri: {len(test_df)}")
print(test_df["label"].value_counts().to_string())

texts  = test_df["text"].tolist()
labels = test_df["label"].tolist()

v1_preds = [predict_v1(t)[0] for t in texts]
v2_preds = [predict_v2(t)[0] for t in texts]

print(f"\n--- V1 (LR + TF-IDF, dengesiz) ---")
print(classification_report(labels, v1_preds, digits=3,
      labels=["Positive","Notr","Negative"]))

print(f"\n--- V2 (LinearSVC + word+char n-gram, dengeli) ---")
print(classification_report(labels, v2_preds, digits=3,
      labels=["Positive","Notr","Negative"]))

acc_v1 = accuracy_score(labels, v1_preds)
acc_v2 = accuracy_score(labels, v2_preds)
print(f"Genel Accuracy  ->  V1: {acc_v1:.3f}   V2: {acc_v2:.3f}   Fark: {(acc_v2-acc_v1)*100:+.1f}pp")

# -----------------------------------------------------------------------
# 2. SINIF BAZLI KARŞILAŞTIRMA (kisa tablo)
# -----------------------------------------------------------------------
from sklearn.metrics import precision_recall_fscore_support
p1, r1, f1_1, _ = precision_recall_fscore_support(labels, v1_preds, labels=["Positive","Notr","Negative"], zero_division=0)
p2, r2, f1_2, _ = precision_recall_fscore_support(labels, v2_preds, labels=["Positive","Notr","Negative"], zero_division=0)

print("\n--- F1 Karşılaştırma (sınıf bazlı) ---")
print(f"{'Sinif':<12} {'V1 F1':>8} {'V2 F1':>8} {'Degisim':>10}")
print("-" * 42)
for i, cls in enumerate(["Positive","Notr","Negative"]):
    delta = f1_2[i] - f1_1[i]
    arrow = "+" if delta > 0 else ""
    print(f"{cls:<12} {f1_1[i]:>8.3f} {f1_2[i]:>8.3f} {arrow}{delta*100:>+8.1f}pp")

# -----------------------------------------------------------------------
# 3. CHAT CÜMLELERİ KARŞILAŞTIRMASI (genişletilmiş)
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("BÖLÜM 2: CHAT CÜMLELERİ KARŞILAŞTIRMASI")
print("=" * 60)

chat_tests = [
    # --- POZİTİF ---
    ("harika bir gun gecirdim",           "Positive"),
    ("seni cok seviyorum",                "Positive"),
    ("tesekkurler cok guzeldi",           "Positive"),
    ("sag ol canım mutlu oldum",          "Positive"),
    ("bugun mukemmel gitti hersey",       "Positive"),
    ("cok iyi hissediyorum kendimi",      "Positive"),
    # --- NEGATİF ---
    ("cok sinirli hissediyorum",          "Negative"),
    ("bu gercekten cok kotu oldu",        "Negative"),
    ("neden boyle yapiyorsun anlamiyorum","Negative"),
    ("berbat bir deneyimdi hicbir sey",   "Negative"),
    ("hic begenmedicm bu durumu",         "Negative"),
    ("moralim cok bozuk",                 "Negative"),
    ("bu is bitti artik gercekten",       "Negative"),
    # --- NOTR (CHAT) ---
    ("tamam anladim",                     "Notr"),
    ("yarin goruselim",                   "Notr"),
    ("ya ne bileyim",                     "Notr"),
    ("biraz sonra gelirim",               "Notr"),
    ("tamam ok",                          "Notr"),
    ("saat kacta",                        "Notr"),
    ("neredesin simdi",                   "Notr"),
    ("bilmiyorum henuz",                  "Notr"),
    # --- ZOR VAKALAR ---
    ("tamam ama cok yoruldum",            "Negative"),
    ("guzel ama pahaliydi",               "Positive"),
    ("fena degildi aslinda",              "Positive"),
    ("idare eder gider",                  "Notr"),
]

print(f"\n{'Cumle':<40} {'Gercek':<12} {'V1':<12} {'V2':<12}")
print("-" * 78)

v1_correct = v2_correct = 0
v1_errors = []
v2_errors = []

for text, expected in chat_tests:
    p1, c1 = predict_v1(text)
    p2, c2 = predict_v2(text)
    ok1 = "OK" if p1 == expected else "YANLIS"
    ok2 = "OK" if p2 == expected else "YANLIS"
    if p1 == expected: v1_correct += 1
    else: v1_errors.append(text)
    if p2 == expected: v2_correct += 1
    else: v2_errors.append(text)
    flag = " <-- V2 kazandi" if ok1=="YANLIS" and ok2=="OK" else (
           " <-- V1 kazandi" if ok1=="OK" and ok2=="YANLIS" else "")
    print(f"{text:<40} {expected:<12} {p1+' '+ok1:<12} {p2+' '+ok2:<12}{flag}")

total = len(chat_tests)
print(f"\nChat Dogrulugu  ->  V1: {v1_correct}/{total} ({v1_correct/total*100:.0f}%)   V2: {v2_correct}/{total} ({v2_correct/total*100:.0f}%)")

# -----------------------------------------------------------------------
# 4. SKOR DAGILIMLARI (bias testi)
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("BÖLÜM 3: TAHMİN DAĞILIMI (MODEL BIAS TESTİ)")
print("=" * 60)

# 500 rastgele test orneği
sample = test_df.sample(500, random_state=1)
v1_all = [predict_v1(t)[0] for t in sample["text"]]
v2_all = [predict_v2(t)[0] for t in sample["text"]]

v1_dist = pd.Series(v1_all).value_counts(normalize=True)*100
v2_dist = pd.Series(v2_all).value_counts(normalize=True)*100

print(f"\n{'Sinif':<12} {'V1 %':>8} {'V2 %':>8}")
print("-" * 30)
for cls in ["Positive","Notr","Negative"]:
    print(f"{cls:<12} {v1_dist.get(cls,0):>7.1f}% {v2_dist.get(cls,0):>7.1f}%")

print("\n>> V1 Positive'e ne kadar egilimli? Yukaridaki dagilimlara bakin.")
print(">> Ideal: her sinif yaklasik %33.")

# -----------------------------------------------------------------------
# 5. ÖZET RAPOR
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("ÖZET")
print("=" * 60)
print(f"Test CSV accuracy     : V1={acc_v1:.3f}  V2={acc_v2:.3f}  ({(acc_v2-acc_v1)*100:+.1f}pp)")
print(f"Chat dogrulugu        : V1={v1_correct/total*100:.0f}%    V2={v2_correct/total*100:.0f}%")
print(f"V2 avantajli cumle say: {sum(1 for t in chat_tests if predict_v1(t[0])[0]!=t[1] and predict_v2(t[0])[0]==t[1])}")
print(f"V1 avantajli cumle say: {sum(1 for t in chat_tests if predict_v1(t[0])[0]==t[1] and predict_v2(t[0])[0]!=t[1])}")
print("\nV2'nin guclu yonleri:")
print("  - Dengeli egitim verisi -> Negative ve Notr'u daha iyi yakalar")
print("  - Char n-gram -> yazim hatalarına toleransli")
print("  - LinearSVC -> text classification'da LR'den genellikle ust")
print("  - Yeni sklearn versiyonu ile uyumlu")
print("\nZayif nokta:")
print("  - Chat-notr cumleler ('yarın goruselim', 'ya ne bileyim')")
print("    Wikipedia Notr ile egitildi, chat-neutral farkli")
print("    Cozum: chat-notr ornekleri egitim verisine eklenebilir.")
