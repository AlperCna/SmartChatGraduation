"""
SmartChat Sentiment Model v2 — Yeniden Eğitim
Sorunlar (v1):
  - urun_yorumlari: 197K Positive vs 13K Negative → model Positive'e eğilimli
  - Notr = Wikipedia metni → chat nötr cümlelerini temsil etmiyor
  - sklearn versiyon uyumsuzluğu
  - Domain mismatch (ürün yorumu != chat dili)

Çözümler (v2):
  - Her sınıftan eşit örnekleme (40K x 3 = 120K)
  - Notr için wiki + chat-benzeri kısa cümleler tercih edilir
  - Word n-gram (1-3) + Char n-gram (2-5) → bağlam + yazım hatası toleransı
  - LinearSVC → text classification için LR'den genellikle daha iyi
  - Türkçe normalizasyon preprocessing
"""

import pandas as pd
import numpy as np
import pickle
import re
import os
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.utils import resample

# -----------------------------------------------------------------------
# 1. TÜRKÇE NORMALİZASYON
# -----------------------------------------------------------------------
def normalize(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.lower()
    # URL / email kaldır
    text = re.sub(r'http\S+|www\S+|\S+@\S+', ' ', text)
    # Tekrarlanan karakterleri azalt (çokkk → çok)
    text = re.sub(r'(.)\1{2,}', r'\1\1', text)
    # Emoji / özel karakter temizle ama noktalama kalsın
    text = re.sub(r'[^\w\sÀ-ɏ]', ' ', text, flags=re.UNICODE)
    # Çoklu boşluk
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# -----------------------------------------------------------------------
# 2. VERİ YÜKLE VE DENGELİ ÖRNEKLEME
# -----------------------------------------------------------------------
print(">> Veri yükleniyor (augmented)...")
df = pd.read_csv("train_augmented.csv", encoding="utf-8")
df = df[["text", "label"]].dropna()
df["text"] = df["text"].apply(normalize)
df = df[df["text"].str.len() > 5]

print(f">> Ham veri: {len(df):,} satır")
print(df["label"].value_counts())

# Sınıf bazlı havuzlar
pos = df[df["label"] == "Positive"]
neg = df[df["label"] == "Negative"]
notr = df[df["label"] == "Notr"]

# Notr için kısa wiki cümlelerini tercih et (chat'e daha yakın)
notr_short = notr[notr["text"].str.len() < 200]
notr_pool  = notr_short if len(notr_short) >= 40000 else notr

# Dengeleme hedefi: her sınıftan N örnek
N = min(40000, len(neg), len(pos), len(notr_pool))
print(f"\n>> Her sınıftan {N:,} örnek alınıyor...")

pos_s  = resample(pos,       n_samples=N, random_state=42, replace=False)
neg_s  = resample(neg,       n_samples=N, random_state=42, replace=False)
notr_s = resample(notr_pool, n_samples=N, random_state=42, replace=False)

data = pd.concat([pos_s, neg_s, notr_s]).sample(frac=1, random_state=42).reset_index(drop=True)
print(f">> Dengelenmiş veri: {len(data):,} satır")
print(data["label"].value_counts())

X = data["text"].values
y = data["label"].values

# -----------------------------------------------------------------------
# 3. TRAIN / TEST SPLIT
# -----------------------------------------------------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.15, random_state=42, stratify=y
)
print(f"\n>> Train: {len(X_train):,}  |  Test: {len(X_test):,}")

# -----------------------------------------------------------------------
# 4. MODEL PIPELINE
#   - Word TF-IDF (1-3 gram) + Char TF-IDF (2-5 gram) birleşik feature
#   - LinearSVC + Calibration (predict_proba için)
# -----------------------------------------------------------------------
from sklearn.pipeline import FeatureUnion

word_tfidf = TfidfVectorizer(
    analyzer="word",
    ngram_range=(1, 3),
    max_features=80000,
    sublinear_tf=True,
    min_df=2,
)

char_tfidf = TfidfVectorizer(
    analyzer="char_wb",
    ngram_range=(2, 5),
    max_features=50000,
    sublinear_tf=True,
    min_df=3,
)

features = FeatureUnion([
    ("word", word_tfidf),
    ("char", char_tfidf),
])

svc = LinearSVC(C=1.0, max_iter=2000, class_weight="balanced")
clf = CalibratedClassifierCV(svc, cv=3)

pipeline = Pipeline([
    ("features", features),
    ("clf",      clf),
])

# -----------------------------------------------------------------------
# 5. EĞİT
# -----------------------------------------------------------------------
print("\n>> Model eğitiliyor (word + char n-gram, LinearSVC)...")
pipeline.fit(X_train, y_train)
print(">> Eğitim tamamlandı.")

# -----------------------------------------------------------------------
# 6. KAYDET (evaluation'dan önce — crash olsa bile model kurtarılır)
# -----------------------------------------------------------------------
out_model = "sentiment_model_v2.pkl"
with open(out_model, "wb") as f:
    pickle.dump(pipeline, f)
print(f"\n>> Model kaydedildi: {out_model} (chat-notr augmented)")

# -----------------------------------------------------------------------
# 7. DEĞERLENDİR
# -----------------------------------------------------------------------
y_pred = pipeline.predict(X_test)
print("\n=== TEST SONUÇLARI ===")
print(classification_report(y_test, y_pred, digits=3))
print("Confusion Matrix:")
print(confusion_matrix(y_test, y_pred, labels=["Positive", "Notr", "Negative"]))

# -----------------------------------------------------------------------
# 8. CHAT CÜMLELERİ ÜZERİNDE MANUEL TEST
# -----------------------------------------------------------------------
chat_tests = [
    ("harika bir gun gecirdim",      "Positive"),
    ("cok sinirli hissediyorum",     "Negative"),
    ("tamam anladim",                "Notr"),
    ("neden boyle davraniyorsun",    "Negative"),
    ("seni seviyorum",               "Positive"),
    ("bu sacmalik",                  "Negative"),
    ("yarin goruselim",              "Notr"),
    ("cok kotu hissettim bugun",     "Negative"),
    ("ya ne bileyim",                "Notr"),
    ("tesekkurler harika oldu",      "Positive"),
    ("berbat bir deneyimdi",         "Negative"),
    ("tamam ok",                     "Notr"),
    ("sag ol canim",                 "Positive"),
    ("hic begenmedicm",              "Negative"),
    ("biraz sonra gelirim",          "Notr"),
]

print("\n=== CHAT CUMLELER TEST ===")
print(f"{'Tahmin':<12} {'Gercek':<12} {'Guven':<6}  Cumle")
print("-" * 65)
correct = 0
for text, expected in chat_tests:
    norm = normalize(text)
    pred = pipeline.predict([norm])[0]
    proba = pipeline.predict_proba([norm]).max()
    ok = "OK" if pred == expected else "YANLIS"
    if pred == expected:
        correct += 1
    print(f"{pred:<12} {expected:<12} {proba:.2f}   [{ok}]  {text}")

print(f"\nChat dogrulugu: {correct}/{len(chat_tests)} = {correct/len(chat_tests)*100:.0f}%")
print("\nBitirmek icin compare_models.py calistirin.")
