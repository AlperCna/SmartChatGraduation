import sys
sys.path.insert(0, ".")
from ai_module.ml_model import predict_sentiment

tests = [
    "selam",
    "yarin goruselim",
    "seni seviyorum",
    "cok sinirli hissediyorum",
    "tamam ok",
    "naber",
    "merhaba",
    "iyi geceler",
]

print(">>> SENTIMENT MODEL V2 - CANLI TEST")
print(f"{'Sonuc':<12} {'Guven':>6}  Mesaj")
print("-" * 45)
for t in tests:
    r = predict_sentiment(t)
    print(f"{r['sentiment']:<12} {r['confidence']:>6.2f}  {t}")
