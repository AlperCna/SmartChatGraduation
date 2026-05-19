import pickle, re, os, warnings
from dotenv import load_dotenv
load_dotenv(override=True)
warnings.filterwarnings("ignore")

def normalize(text):
    if not isinstance(text, str): return ""
    text = text.lower()
    text = re.sub(r"http\S+|www\S+|\S+@\S+", " ", text)
    text = re.sub(r"(.)\1{2,}", r"\1\1", text)
    text = re.sub(r"[^\w\sA-z\xC0-ɏ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

with open("sentiment_model.pkl", "rb") as f:
    v1_model = pickle.load(f)
with open("tfidf_vectorizer.pkl", "rb") as f:
    v1_vec = pickle.load(f)
with open("sentiment_model_v2.pkl", "rb") as f:
    v2_pipeline = pickle.load(f)

def pred_v1(t):
    x = v1_vec.transform([t])
    pred = v1_model.predict(x)[0]
    conf = float(v1_model.predict_proba(x).max())
    m = {"positive": "Positive", "negative": "Negative", "notr": "Notr"}
    return m.get(pred.lower(), pred), conf

def pred_v2(t):
    norm = normalize(t)
    if not norm:
        return "Notr", 0.0
    pred = v2_pipeline.predict([norm])[0]
    conf = float(v2_pipeline.predict_proba([norm]).max())
    if conf < 0.52 and pred != "Notr":
        pred = "Notr"
    return pred, conf

import mysql.connector
conn = mysql.connector.connect(
    host=os.getenv("DB_HOST", "localhost"),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD") or "bc748596",
    database=os.getenv("DB_NAME", "smartchat"),
    port=int(os.getenv("DB_PORT", 3306))
)
cur = conn.cursor(dictionary=True)
sql = (
    "SELECT content FROM messages "
    "WHERE content IS NOT NULL AND content != '' "
    "AND content NOT IN ('image','video','audio','file','location') "
    "AND LENGTH(content) > 3 AND LENGTH(content) < 200 "
    "ORDER BY RAND() LIMIT 30"
)
cur.execute(sql)
msgs = [r["content"] for r in cur.fetchall()]
cur.close()
conn.close()

print(f"Veritabanindan {len(msgs)} mesaj cekildi\n")
print(f"{'#':<3} {'V1':<12} {'V2':<12} {'C1':>5} {'C2':>5}  Mesaj")
print("-" * 75)

v1c = {"Positive": 0, "Negative": 0, "Notr": 0}
v2c = {"Positive": 0, "Negative": 0, "Notr": 0}
agree = 0

for i, msg in enumerate(msgs, 1):
    r1, c1 = pred_v1(msg)
    r2, c2 = pred_v2(msg)
    flag = "  <-- FARKLI" if r1 != r2 else ""
    display = msg[:38] + ("..." if len(msg) > 38 else "")
    display = display.encode("cp1254", errors="replace").decode("cp1254")
    print(f"{i:<3} {r1:<12} {r2:<12} {c1:>5.2f} {c2:>5.2f}  {display}{flag}")
    v1c[r1] = v1c.get(r1, 0) + 1
    v2c[r2] = v2c.get(r2, 0) + 1
    if r1 == r2:
        agree += 1

n = len(msgs)
print()
print("DAGILIM:")
print(f"{'Sinif':<12} {'V1 sayi':>8} {'V1 %':>6}   {'V2 sayi':>8} {'V2 %':>6}")
print("-" * 50)
for cls in ["Positive", "Notr", "Negative"]:
    v1n = v1c.get(cls, 0)
    v2n = v2c.get(cls, 0)
    print(f"{cls:<12} {v1n:>8}  {v1n/n*100:>5.0f}%   {v2n:>8}  {v2n/n*100:>5.0f}%")

print(f"\nAyni karar: {agree}/{n} (%{agree/n*100:.0f})")
print(f"Farkli karar: {n-agree}/{n} mesajda modeller farkli sonuc uretti")
