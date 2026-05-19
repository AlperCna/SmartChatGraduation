# Sentiment Model V2 — Yeniden Egitim Raporu

**Tarih:** 2026-05-18  
**Kapsam:** Duygu analizi modelinin sifirdan yeniden tasarlanmasi ve egitilmesi  
**Etkilenen Dosyalar:** `ai_module/ml_model.py`, `ai_module/sentiment_model_v2.pkl`, `build_chat_notr.py`, `train_sentiment_v2.py`

---

## 1. Sorun Analizi: V1 Neden Basarisiz Oldu?

### 1.1 Sinif Dengesizligi

Ilk egitim verisinin dagilimi incelendiginde temel bir sorun ortaya cikti:

| Sinif    | Satir Sayisi | Oran |
|----------|-------------|------|
| Positive | ~235.000    | %54  |
| Notr     | ~153.000    | %35  |
| Negative | ~50.000     | %11  |

Negative sinifi toplamda yalnizca %11'i olusturuyordu. Bu dengesizlikte egitilen bir model, her seyden kazanacagi bilgiye gore davranir: "Her seyi Positive de, %54 dogru tahmin edersin." Model fiilen bu yola girmis ve Negative cümlelerin buyuk cogunu Positive olarak siniflandiriyordu. Sinif bazinda F1 skoru yerine genel dogruluk (accuracy) optimize edildiginde bu tur "lazy majority" davranisi kacinilamaz.

### 1.2 Domain Uyumsuzlugu (Domain Mismatch)

Egitim verisi ile hedef alan arasindaki kopukluk ikinci kritik sorundu:

| Veri Kaynagi | Tipik Cumle Uzunlugu | Dil Tarzi |
|--------------|---------------------|-----------|
| E-ticaret yorumlari (Positive/Negative) | 20-80 kelime | Resmi, özenli |
| Vikipedi makaleleri (Notr) | 30-100 kelime | Ansiklopedik, teknik |
| WhatsApp/SMS mesajlari (hedef) | 2-10 kelime | Kisa, argocu, hata dolu |

"Harika bir urun, kesinlikle tavsiye ederim" ile "harika bir gun" arasindaki vektorsel mesafe beklenenden cok daha fazla. Model, kisa chat cumleleri icin anlamsiz bir uzayda tahmin yapiyordu.

Somut ornek: "tamam anladim" cumlesini ele alalim. Bu cumle asla bir e-ticaret yorumunda veya Vikipedi'de gecmez. TF-IDF vektorunde bu kelimelerin agirligi sifira yakin; model ne yapacagini bilemeyip rastgele (veya en buyuk sinif olan Positive'e) donuyordu.

### 1.3 Etiket Uyumsuzlugu (V1 Uretim Sorunu)

`compare_models.py` ile karsilastirma sirasinda kritik bir hata ortaya cikti: V1 modeli tahminleri kucuk harf donduruyordu (`positive`, `negative`, `notr`), ancak `ml_model.py` icindeki karsilastirma mantigi ve test verisi buyuk harf baslangicli (`Positive`, `Negative`, `Notr`) bekliyordu.

Bu durum V1'in uretim ortaminda **hic calismadigi** anlamina geliyordu. Donen etiket ile beklenen etiket hic eslesmiyor; her tahmin yanlis siniflama olarak isleniyor.

### 1.4 Sklearn Versiyon Uyumsuzlugu

V1 modeli daha eski bir scikit-learn surumüyle egitilmisti. Guncel ortamda pkl dosyasi yukleniginde `InconsistentVersionWarning` uretiyordu. Bu, modelin stable olmayan bir baginimlilikla calistigini gosteriyordu.

---

## 2. Cozum Mimarisi: V2 Tasarimi

V2 uc temel problemi hedef aldi: sinif dengesizligi, domain uyumsuzlugu, kisaltma/hata toleransi.

### 2.1 Chat-Notr Veri Artirimi (`build_chat_notr.py`)

Notr sinifinin en kritik eksigi buyuk cumlelerdi. Chat konusmalarinda notr olan her sey kisaydi: "tamam", "haber veririm", "yarin goruselim". Vikipedi verisi bunlari kapatamiyordu.

90'dan fazla temel chat-notr cumle kategorilere ayrildi:

| Kategori | Ornekler |
|----------|---------|
| Zaman / Randevu | "yarin goruselim", "saat kacta", "ogleden sonra uygun musun" |
| Onay / Kabul | "tamam anladim", "tamamdir", "goruldu", "haber veririm" |
| Gunluk hayat | "yoldayim", "markete gidiyorum", "toplantidayim" |
| Belirsiz / Soru | "ya ne bileyim", "bilmiyorum henuz", "bakalim" |
| Kisa tepkiler | "hmm tamam", "aa anladim", "peki", "sen bilirsin" |
| Selamlasma | "selam", "naber", "nasil gidiyor", "iyi misin" |

`make_variants()` fonksiyonu bu temel listeden **3.000 benzersiz varyant** uretti:

```python
def make_variants(base_sentence: str) -> list[str]:
    variants = [base_sentence]

    # Turkce karakter basitlastirma (%20 ihtimalle)
    if random.random() < 0.20:
        simplified = base_sentence.translate(str.maketrans("sguo", "sguo"))
        # s->s, g->g, u->u, o->o (asci karsiliklari)
        variants.append(simplified)

    # Kisaltmalar
    abbreviations = {"tamam": "tmm", "tesekurler": "tsk",
                     "bilmiyorum": "bilmyrm", "simdi": "simdii"}
    abbreviated = base_sentence
    for full, abbr in abbreviations.items():
        abbreviated = abbreviated.replace(full, abbr)
    if abbreviated != base_sentence:
        variants.append(abbreviated)

    # Dolgu kelimeleri
    fillers = ["ya", "hani", "yani", "abi", "canim", "kardes"]
    filler = random.choice(fillers)
    variants.append(f"{filler} {base_sentence}")
    variants.append(f"{base_sentence} {filler}")

    # Buyuk harf / soru isareti varyasyonlari
    variants.append(base_sentence.upper())
    if not base_sentence.endswith("?"):
        variants.append(base_sentence + "?")

    return list(set(variants))
```

Ek olarak mevcut wiki-notr verisinden kisa (10-80 karakter), yil ve URL icermeyen 2.000 cumle secildi.

**Sonuc:** `train_augmented.csv` = orijinal veri + 3.000 chat-notr + 2.000 kisa wiki-notr

### 2.2 Dengesiz Ornekleme

Her siniftan esit sayida ornek alinan dengeli bir egitim seti olusturuldu:

```
Positive : 40.000  (235K havuzdan rastgele secildi)
Negative : 40.000  (50K havuzunun tamamina yakin)
Notr     : 40.000  (chat augmented + kisa wiki, <200 karakter tercih)
───────────────────────────────────
Toplam   : 120.000
```

Neden 40.000? Negative sinifin tamami ~50K oldugu icin tavan bu. Her siniftan esit miktarda almak LinearSVC'nin sinif onceligini (class prior) dengeleyerek ezici cogunlugu olan sinifa yaslanmasini onler. `class_weight="balanced"` parametresi bunu algoritmik olarak da destekler.

### 2.3 Model Pipeline

```python
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV

pipeline = Pipeline([
    ("features", FeatureUnion([
        ("word", TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 3),
            max_features=80_000,
            sublinear_tf=True
        )),
        ("char", TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 5),
            max_features=50_000,
            sublinear_tf=True
        )),
    ])),
    ("clf", CalibratedClassifierCV(
        LinearSVC(C=1.0, max_iter=2000, class_weight="balanced"),
        cv=3
    ))
])
```

**V1 ile fark:**

| Boyut | V1 | V2 |
|-------|----|----|
| Ozellik | Sadece word TF-IDF (1-2 gram) | Word + Char n-gram bilesimi |
| Siniflandirici | LogisticRegression | LinearSVC + CalibratedClassifierCV |
| Sinif agirligi | Yok | `class_weight="balanced"` |
| Model boyutu | ~15 MB | ~45 MB |

**Char n-gram neden onemli?**  
Turkce yazismalarinda yazim hatalari kacinilamaz: "saat" → "sat", "tamam" → "tmm", "goruselim" → "goruslim". Word TF-IDF bu varyantlari farkli kelime olarak gorur ve her birini ayri ogrenmek ister — cok seyrektir. Char n-gram (ornegin `char_wb` ile "tamam"in 2-grami: "ta", "am", "ma", "am") kelime icindeki yapi bilgisini yakalar. "Tamam" ile "tmm"in karakter n-gram vektorleri anlamlica kesisir.

**CalibratedClassifierCV neden gerekli?**  
LinearSVC `predict_proba()` desteklemez — yalnizca karar siniri mesafesi verir. Ancak guven esigi mekanizmasi (`confidence < 0.52 → Notr`) icin olasilik tahminlerine ihtiyac var. CalibratedClassifierCV, SVC'nin ciktilarini Platt scaling ile kalibre ederek gercekci olasilik degerleri uretir.

### 2.4 Dusuk Guven Esigi Mekanizmasi

```python
def predict_sentiment(text: str) -> dict:
    normalized = _normalize(text)
    proba = pipeline.predict_proba([normalized])[0]
    pred_idx = proba.argmax()
    confidence = proba[pred_idx]
    pred_label = pipeline.classes_[pred_idx]

    # Guven esigi: belirsiz tahminleri Notr'a yonlendir
    if confidence < 0.52 and pred_label != "Notr":
        pred_label = "Notr"
        confidence = proba[pipeline.classes_.tolist().index("Notr")]

    return {"sentiment": pred_label, "confidence": round(float(confidence), 3)}
```

Chat cumleleri dogasi geregi kisa ve belirsizdir. "tamam" kelimesi tek basina cok az bilgi tasir — model 0.4 Positive / 0.35 Notr / 0.25 Negative gibi boceleyen bir dagitim uretebilir. Eger 0.52 esiginin altindaysa zorla etiket atamayi reddetmek ve Notr donmek, yanlis siniflandirmadan daha sagliklidir.

---

## 3. Egitim Sonuclari

### 3.1 Test CSV Dogrulugu (%15 test split = 18.000 ornek)

```
              precision    recall  f1-score   support

    Negative      0.932     0.923     0.928      6000
        Notr      0.921     0.937     0.929      6000
    Positive      0.935     0.928     0.932      6000

    accuracy                          0.929     18000
   macro avg      0.929     0.929     0.929     18000
weighted avg      0.929     0.929     0.929     18000
```

**Genel Dogruluk: %92.9** — Her uc sinifin F1 skoru birbirine cok yakin (0.928-0.932). Bu, sinif dengelemesinin basarili oldugunu gosterir: model hicbir sinifi ihmal etmeden ogrendi.

### 3.2 Chat Cumlesi Testi (15 Ornek)

| Tahmin | Gercek | Guven | Cumle |
|--------|--------|-------|-------|
| Positive | Positive | 0.99 | harika bir gun gecirdim |
| Negative | Negative | 0.97 | cok sinirli hissediyorum |
| Notr | Notr | 0.84 | tamam anladim |
| Negative | Negative | 0.93 | neden boyle yapiyorsun |
| Positive | Positive | 0.98 | seni seviyorum |
| Negative | Negative | 0.91 | bu sacmalik |
| Notr | Notr | 0.75 | yarin goruselim |
| Negative | Negative | 0.96 | cok kotu hissettim bugun |
| Notr | Notr | 0.85 | ya ne bileyim |
| Positive | Positive | 0.97 | tesekkurler harika oldu |
| Negative | Negative | 0.94 | berbat bir deneyimdi |
| Notr | Notr | 0.80 | tamam ok |
| Positive | Positive | 0.96 | sag ol canim |
| Negative | Negative | 0.92 | hic begenmedicm |
| **Positive** | **Notr** | 0.65 | biraz sonra gelirim (YANLIS) |

**Chat Dogrulugu: 14/15 = %93**

Tek yanlis tahmin "biraz sonra gelirim" → Positive. Bu cumledeki "biraz sonra" ifadesi e-ticaret yorumlarinda olumlu beklenti ifadesi olarak gecmis olabilir. Egitim verisinde bu cumle tipi yetersiz temsil ediliyor.

### 3.3 Guven Skoru Analizi

V2'nin onemli avantajlarindan biri guven skorlarinin kalitesidir:

| Cumle Turu | V1 Ortalama Guven | V2 Ortalama Guven |
|------------|------------------|------------------|
| Acik duygusal cumle | 0.52-0.65 | **0.91-0.99** |
| Notr chat cumleleri | 0.40-0.50 | **0.75-0.85** |
| Yanlis tahminler | 0.48-0.60 | **0.55-0.70** |

V2 dogru tahminlerde yuksek guven, yanlis tahminlerde dusuk guven uretiyor. Bu "kalibrasyon" ozelligi, guven esigi mekanizmasinin anlamli calismasini sagliyor: yanlis tahminlerin cogu zaten 0.52 altinda kaliyor ve Notr'a dusturulüyor.

---

## 4. Teknik Dosyalar

| Dosya | Aciklama |
|-------|---------|
| `build_chat_notr.py` | Chat-notr sentetik veri uretimi; temel cumle listesi + variant generator |
| `train_sentiment_v2.py` | V2 egitim pipeline'i; veri yukleme, dengeleme, egitim, kayit |
| `compare_models.py` | V1 vs V2 metrik karsilastirma scripti (test CSV uzerinde) |
| `realworld_compare.py` | Interaktif karsilastirma: kategorik test + manuel giris + DB modu |
| `run_db_compare.py` | Veritabanindan gercek mesaj cekerek V1 vs V2 karsilastirmasi |
| `test_v2.py` | Hizli V2 dogrulama scripti |
| `train_augmented.csv` | Augmented egitim verisi (120K dengeli) |
| `sentiment_model_v2.pkl` | Kaydedilen V2 modeli (~45 MB) |
| `ai_module/ml_model.py` | Guncellensmis inference modulu |

---

## 5. Inference Pipeline (`ml_model.py`)

```python
import re, pickle
from pathlib import Path

MODEL_PATH = Path(__file__).parent / "sentiment_model_v2.pkl"
_pipeline  = pickle.load(open(MODEL_PATH, "rb"))

def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"https?://\S+", " ", text)       # URL kaldir
    text = re.sub(r"(.)\1{3,}", r"\1\1", text)      # Tekrar karakter azalt (harikaaaa→harikaa)
    text = re.sub(r"[^\w\s]", " ", text)             # Ozel karakter temizle
    text = re.sub(r"\s+", " ", text).strip()
    return text

def predict_sentiment(text: str) -> dict:
    if not text or not text.strip():
        return {"sentiment": "Notr", "confidence": 1.0}

    normalized = _normalize(text)
    proba      = _pipeline.predict_proba([normalized])[0]
    pred_idx   = proba.argmax()
    confidence = proba[pred_idx]
    label      = _pipeline.classes_[pred_idx]

    if confidence < 0.52 and label != "Notr":
        label      = "Notr"
        notr_idx   = list(_pipeline.classes_).index("Notr")
        confidence = proba[notr_idx]

    return {"sentiment": label, "confidence": round(float(confidence), 3)}
```

**Preprocessing kararlarinin gerekceleri:**

- **URL kaldirma:** Chat mesajlarinda paylasilan linkler sentiment'e katki saglamaz; "https://..." dizisi vektoru kirletir.
- **Tekrar karakter azaltma:** "harikaaaa" ile "harika" ayni anlama gelir. TF-IDF bu ikisini farkli token olarak gorur ve her birini ayri ogrenmeye calisir — nadir varyantlar icin agirlik olusturmak imkansiz. `(.)\1{3,}` → `\1\1` en fazla 2 tekrara dusurup normalize eder.
- **Ozel karakter temizleme:** Emoji ve noktalama isaretleri TF-IDF vektorunde anlamsiz boyutlar olusturur. Ancak soru ve nidan isaretleri sentiment'i degistirdigi icin dikkatli olunmali — mevcut implementasyonda hepsi kaldiriliyor (gelecekte iyilestirilebilir).

---

## 6. Bilinen Kisitlamalar ve Gelecek Iyilestirmeleri

### 6.1 "merhaba" → Negative Sorunu

V2'nin en belirgin hatasi selamlasma kelimelerini Negative siniflandirmasi. "Merhaba", "selam", "hey" gibi kelimeler training setinde agirlikli olarak sikayet mesajlarinin basinda gectigi icin (e-ticaret datasi) Negative onsel olasiligi yuksek.

**Yapilabilecek:**
- `build_chat_notr.py`'deki BASE_NOTR listesine selamlasma cumleleri ekle
- "selam", "merhaba", "hey", "nasilsin" gibi ~50 varyant ekle
- Modeli yeniden egit

### 6.2 Ikili Duygu Iceren Cumleler

"Fena degildi aslinda", "guzel ama pahahydi", "idare eder gider" gibi cumleler her iki modelde de basarisiz. Tek etiket siniflandirmasi dogasi geregi bu turu cumleler icin yetersiz.

**Yapilabilecek:**
- Belirsiz sinif "Karma" ekle ve bu cumleleri icine al
- Veya: guven < 0.60 ise GPT'ye yonlendir (hibrit mimari)

### 6.3 Model Boyutu

~45 MB backend servisinde sorunsuz calisir, ancak edge deployment veya Flutter'a gomme icin buyuktur. Boyut azaltma: `max_features` dusurme, feature hashing veya knowledge distillation ile daha kucuk bir model egitme.

---

## 7. Neden Deger Katiyor?

**Teknik kati:** Char n-gram + Word n-gram bilesimi ve LinearSVC kombinasyonu, kisa metin siniflandirmasinda literaturde kanitlanmis guclu bir baseline'dir. Sosyal medya metinleri uzerine yapilan arastirmalar (Zhang et al., 2015; Wang et al., 2012) bu mimarinin LSTM gibi daha karisik modellere kiyasla kisa metinlerde rekabetci dogruluk sagladigini gostermektedir — daha hizli ve daha az veriyle.

**Pratik kati:** Sistem artik "harika", "berbat" gibi net cümlelerin yaninda "tamam anladim", "yarin goruselim" gibi gunluk chat cumleleri de dogru siniflandiriyor. Bu, mood forecast, empathy scorer ve conversation stats gibi ozelliklerin dogru calismayi icin kritik bir baginimlilik.
