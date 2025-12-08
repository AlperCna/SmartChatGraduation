import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns

# -------------------------------------------------------
# 1. Load the cleaned dataset
# -------------------------------------------------------

df = pd.read_csv("clean_formal_informal_dataset.csv")

texts = df["text"].astype(str).values
labels = df["label"].astype(str).values

# -------------------------------------------------------
# 2. Split dataset
# -------------------------------------------------------

X_train, X_test, y_train, y_test = train_test_split(
    texts, labels, test_size=0.2, random_state=42, stratify=labels
)

# -------------------------------------------------------
# 3. Vectorize text
# -------------------------------------------------------

vectorizer = TfidfVectorizer(
    ngram_range=(1,2),
    min_df=3,
    max_df=0.95,
    sublinear_tf=True
)

X_train_vec = vectorizer.fit_transform(X_train)
X_test_vec = vectorizer.transform(X_test)

# -------------------------------------------------------
# 4. Train model (Logistic Regression is best for this task)
# -------------------------------------------------------

model = LogisticRegression(max_iter=2000)
model.fit(X_train_vec, y_train)

# -------------------------------------------------------
# 5. Evaluate
# -------------------------------------------------------

pred = model.predict(X_test_vec)

print("Accuracy:", accuracy_score(y_test, pred))
print("\nClassification Report:\n", classification_report(y_test, pred))
print("\nConfusion Matrix:\n", confusion_matrix(y_test, pred))

# Plot confusion matrix
plt.figure(figsize=(5,4))
sns.heatmap(confusion_matrix(y_test, pred), annot=True, fmt="d",
            xticklabels=model.classes_, yticklabels=model.classes_)
plt.title("Style Classification Confusion Matrix")
plt.xlabel("Predicted")
plt.ylabel("True")
plt.show()

# -------------------------------------------------------
# 6. Save model + vectorizer for backend
# -------------------------------------------------------

joblib.dump(model, "ai_module/style_model2.pkl")
joblib.dump(vectorizer, "ai_module/style_vectorizer2.pkl")

print("\nSaved: style_model2.pkl and style_vectorizer2.pkl")
