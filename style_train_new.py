import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns

DATASET = "StyleAdapter_Real_80K.csv"

print("📂 Veri yükleniyor...")
df = pd.read_csv(DATASET)

# NaN temizle
df.dropna(inplace=True)

# Shuffle
df = df.sample(frac=1, random_state=42).reset_index(drop=True)

X = df["text"].astype(str).values
y = df["label"].astype(str).values

# ==========================================================
# 1. TRAIN / TEST SPLIT
# ==========================================================
print("✂️ Train/Test ayrılıyor...")
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.15, random_state=42, stratify=y
)

# ==========================================================
# 2. TF-IDF VECTORIZER
# ==========================================================
vectorizer = TfidfVectorizer(
    lowercase=False,        # Formal cased data önemli
    ngram_range=(1, 2),     # Bigram çok kritik!
    min_df=5,
    max_features=None
)

print("🔠 TF-IDF eğitiliyor...")
X_train_vec = vectorizer.fit_transform(X_train)
X_test_vec = vectorizer.transform(X_test)

# ==========================================================
# 3. MODEL — Linear SVM (Formal/Informal için EN İYİSİ)
# ==========================================================
print("🤖 Model eğitiliyor (Linear SVM)...")

model = LinearSVC()
model.fit(X_train_vec, y_train)

# ==========================================================
# 4. DEĞERLENDİRME
# ==========================================================
print("\n📊 Test sonuçları hesaplanıyor...")
pred = model.predict(X_test_vec)

acc = accuracy_score(y_test, pred)
print(f"\n🎯 ACCURACY: %{acc*100:.2f}\n")
print(classification_report(y_test, pred))

# Confusion Matrix çiz
cm = confusion_matrix(y_test, pred)
plt.figure(figsize=(6,5))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues")
plt.title(f"Confusion Matrix (Acc: %{acc*100:.2f})")
plt.xlabel("Predicted")
plt.ylabel("True")
plt.show()

# ==========================================================
# 5. KAYDETME
# ==========================================================
print("\n💾 Model kaydediliyor...")

joblib.dump(model, "style_model_real.pkl")
joblib.dump(vectorizer, "style_vectorizer_real.pkl")

print("\n✅ Eğitim tamamlandı!")
print("   -> style_model_real.pkl")
print("   -> style_vectorizer_real.pkl")
