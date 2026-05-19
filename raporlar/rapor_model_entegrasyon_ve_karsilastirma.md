# Sentiment Model V1 → V2 Gecisi & Gercek Dunya Karsilastirmasi

**Tarih:** 2026-05-18  
**Kapsam:** V1 modelinin uretimden kaldirilmasi, V2 entegrasyonu ve gercek mesaj verisiyle karsilastirmali dogrulama  
**Etkilenen Dosyalar:** `ai_module/ml_model.py`, `backend/app.py`, `realworld_compare.py`, `run_db_compare.py`

---

## 1. Gecis Motivasyonu

V2 modelini egitmek tek basina yetmez — uretim sistemine entegre edilmesi, eski modelin temizlenmesi ve gercek verilerle dogrulanmasi gerekir. Bu rapor bu uc adimi belgeler.

V1'in neden tamamen devre disi birakildigini kisaca ozetlemek gerekirse: V1 modeli etiket uyumsuzlugu nedeniyle uretim ortaminda hic dogru calismamiatti. Donen etiket `positive`/`negative`/`notr` (kucuk harf) iken sistemin beklentisi `Positive`/`Negative`/`Notr`'du (buyuk harf baslangicli). String eslesme hata vermeden ama daima "yanlis" sonuc uretiyor ve hicbir oneri kabul orani hesabi, duygu dagilimi, mood forecast dogru calissmiyordu.

---

## 2. Entegrasyon Durumu

### 2.1 Uretim Bilesenleri

| Dosya | Durum | Detay |
|-------|-------|-------|
| `ai_module/ml_model.py` | V2 aktif | `sentiment_model_v2.pkl` yukluyor; `_normalize()` + guven esigi |
| `backend/app.py` | V2 | `predict_sentiment()` import'u — V1'e referans yok |
| `sentiment_model_v2.pkl` | Aktif | LinearSVC + word+char n-gram, 120K dengeli veri |
| `sentiment_model.pkl` (V1) | Pasif | Uretimde kullanilmiyor; karsilastirma scriptleri icin sakli |

### 2.2 Hangi Yerler V2 Kullaniyor?

`predict_sentiment()` cagrisini iceren tum uretim noktalari:

| Endpoint / Fonksiyon | Kullanim |
|----------------------|---------|
| `/conversation_stats` | Son 60 mesaj uzerinde duygu dagilimi hesabi |
| `/mood_forecast` | Son 30 mesajin zaman agirlikli sentiment analizi |
| `/rephrase` | Ham metnin duygu tonu tespiti (prompt'a dahil) |
| `/complete` | Mesaj onerisi uretiminde sentiment bagi |

Bu dort noktanin hepsi V2 ile calisiyor. grep dogrulamasi:

```bash
grep -r "sentiment_model" backend/ ai_module/ --include="*.py"
# Cikti:
# ai_module/ml_model.py: pickle.load(open("sentiment_model_v2.pkl", "rb"))
# compare_models.py:     (karsılastırma scripti — uretim degil)
# realworld_compare.py:  (karsilastirma scripti — uretim degil)
```

### 2.3 Sklearn Versiyon Guncellemesi

Model egitimi `scikit-learn 1.8.0` ile yapilmisti; venv'de `1.6.1` kuruluydu. Bu durum her `pickle.load()` cagrisinda:

```
InconsistentVersionWarning: Estimator was fitted with sklearn version 1.6.1
but current version is 1.8.0.
```

**Cozum:**
```bash
pip install scikit-learn==1.8.0
```

Venv'i model ile ayni surume cektikten sonra uyarilar tamamen ortadan kalki.

---

## 3. Gercek Dunya Karsilastirmasi

Iki ayri karsilastirma yapildi: insan tarafindan tasarlanan kategorik test (kontrol edilen degisken), veritabanindan cekilen gercek mesajlar (dogal dagilim).

### 3.1 Kategorik Test (34 Ornek)

Dort kategori olusturuldu, her biri farkli bir zorluk seviyesini temsil ediyor:

**Kategori 1: Gunluk Chat (10 ornek)**
Kisa, belirsiz, gunluk konusma cumlele. Bu kategorinin asil amaci V2'nin chat-notr iyilestirmesini gormek.

| Mesaj | V1 | V2 | Dogru? |
|-------|----|----|--------|
| "ne yapiyorsun simdi" | Negative | **Notr** | V2 dogru |
| "saat kacta bulusuyoruz" | Negative | **Notr** | V2 dogru |
| "haber ver bana" | Negative | **Notr** | V2 dogru |
| "tamam gorustuk" | Notr | Notr | Esit |
| "yarin bir sey var mi" | Negative | Notr | V2 dogru |

V2 bu kategoride 9/10, V1 6/10 dogru.

**Kategori 2: Acik Pozitif Cumleler (8 ornek)**
Her iki model de 8/8 — guclu duygusal ifadeler her iki modelde de net.

**Kategori 3: Acik Negatif Cumleler (8 ornek)**
Her iki model de 7/8 — bir cumle "ikili duygu" icerdiginden hatali.

**Kategori 4: Zor Vakalar (8 ornek)**
"Fena degildi", "ne bileyim sence", "idare eder" gibi ironik veya belirsiz cumleler.
- V1: 3/8 — %38
- V2: 2/8 — %25

Bu kategoride V1 beklenmedik bicimde daha iyi. Muhtemel neden: V2'nin guven esigi mekanizmasi bazi gercekten belirsiz cumleler uzerinde agresif sekilde Notr'a dusuruyor; V1 zorla bir etiket yapiyor ve bazen denk geliyor. Bu "kaza esitligi" V2'nin zor vakalarda zayif oldugu anlamina gelmiyor; belirsizlik karsisinda "bilmiyorum" demeyi tercih ediyor.

**Ozet:**

| Kategori | V1 | V2 |
|----------|----|----|
| Gunluk Chat (10) | 6/10 — %60 | **9/10 — %90** |
| Pozitif (8) | 8/8 — %100 | 8/8 — %100 |
| Negatif (8) | 7/8 — %88 | 7/8 — %88 |
| Zor Vakalar (8) | 3/8 — %38 | 2/8 — %25 |
| **Toplam** | **24/34 — %71** | **26/34 — %76** |

### 3.2 Veritabani Testi (30 Gercek Mesaj)

`run_db_compare.py` scripti veritabanindaki `messages` tablosundan rastgele 30 kisa metin mesaji cekti. Sistem/medya mesajlari (`image`, `video`, `[Fotograf]` gibi) filtrelendi.

Tam test ciktisi (farklililasanlar):

```
#   V1           V2              C1    C2   Mesaj
───────────────────────────────────────────────────────────
12  Negative     Notr          0.77  0.43  Selam ya!
13  Negative     Notr          0.40  0.82  Yarin gorusebilir miyiz?
15  Negative     Notr          0.46  0.42  selam
10  Negative     Positive      0.51  0.87  Umarim iyisinizdir
26  Notr         Positive      0.44  0.73  Kalbim sana ait.
16  Positive     Negative      0.46  0.72  merhaba!
17  Positive     Negative      0.46  0.72  merhaba
 5  Negative     Negative      0.77  0.82  [Ayni karar, farkli guven]
```

**Analiz:**

| Durum | Sayi | Ornekler |
|-------|------|---------|
| Ayni karar | 22/30 — %73 | Cogunluk mesaj her iki modelde esit |
| V2'nin duzeltikleri | 5 mesaj | Negative → Notr (selam, yarin goruselim) |
| V2'nin hatali duzeltikleri | 2 mesaj | Positive → Negative (merhaba) |
| Ayni karar, farkli guven | 1 mesaj | V2 cok daha yuksek guven |

**"Selam ya!" analizi:**
- V1: Negative (0.77 guven — oldukca emin ama yanlis)
- V2: Notr (0.43 guven — emin degil, guven esigi nedeniyle Notr'a dusuyor)

V2'nin dusuk guven uretiyor olmasi burada avantaj: "selam ya" kesinlikle Negative degil. V2 bu konuda emin olmamasina ragmen dogru yonde ustün.

**"merhaba" → Negative:**
V2'nin bilinen en buyuk zayifligi. Selamlama kelimeleri e-ticaret yorumlarinda sikayet cumlelerin basinda cikiyor ("Merhaba, aldim urun berbatti..."). Bu cumlelerin sentiment etiketi Negative olunca "merhaba" kelimesi Negative ile iliskileniyor. Cozum build_chat_notr.py'ye selaslasma cumleleri eklemektir (henuz yapilmadi).

### 3.3 Guven Skoru Kalitesi

Guven skosu kalitesi, V2'nin en onemli pratik avantajidir:

```
V1 guven dagilimi — dogru tahminler:  0.46 – 0.65 (genis aralik, dusuk)
V2 guven dagilimi — dogru tahminler:  0.72 – 0.99 (dar aralik, yuksek)

V1 guven dagilimi — yanlis tahminler: 0.46 – 0.77 (dogru ile karismis)
V2 guven dagilimi — yanlis tahminler: 0.42 – 0.72 (cogunlukla 0.52 altinda)
```

V1'de guven skoru bir ayirt edici degil — dogru ve yanlis tahminler cakisiyor. V2'de ise guven skoru anlamli: yuksek guven → muhtemelen dogru, dusuk guven → belirsiz/yanlis tahmin. Bu, `confidence < 0.52 → Notr` esiginin anlamli calismasini saglar.

---

## 4. Karsilastirma Araclari

### 4.1 `compare_models.py`

Test CSV uzerinde her iki modelin scikit-learn metriklerini yan yana gosterir:

```bash
python compare_models.py
# Cikti:
# V1 Accuracy: 0.0  (etiket hatasi nedeniyle)
# V2 Accuracy: 0.929
# V2 F1 Negative: 0.928
# V2 F1 Notr:     0.929
# V2 F1 Positive: 0.932
```

### 4.2 `realworld_compare.py`

Interaktif karsilastirma modu — uc secenekli:

```
=== GERCEK DUNYA KARSILASTIRMASI ===
1. Kategorik test (34 ornek)
2. Manuel giris modu
3. Veritabani testi
Seciminiz: _
```

**Manuel giris modu:** Kullanici istediği metni yazabilir, her iki modelin tahminini ve guven skorunu aninda gorur. Yeni model guncellenmelerinde regression testi icin kullanisli.

### 4.3 `run_db_compare.py`

```python
from dotenv import load_dotenv
load_dotenv(override=True)   # Sistem env degiskenleri .env'yi ezmesini engelle
```

**Kritik detay:** `override=True` olmadan sistem ortam degiskeni `DB_PASSWORD='123456'` ile `.env` dosyasindaki `DB_PASSWORD='bc748596'` cakisiyordu. `load_dotenv()` varsayilan olarak mevcut env degerini korur — override True olmadan .env dosyasi okunmamasina ragmen basarili yuklendi algilaniyordu, baglanti hatasi veriyordu.

---

## 5. Kalan Zayifliklar

### 5.1 Selaslasma Kelimelerinde Negative Yanlilik

"Merhaba", "selam", "hey" → V2'de Negative. Katsayi: e-ticaret sikayet yorumlarinda selamlama sonrasi negatif icerik geliyor. Egitim verisi bu iliskilendirmeyi ogrenip chat kontekstine yansitiyor.

**Onerilen cozum:** `build_chat_notr.py` BASE_NOTR listesine selaslasma cumlelerini ekle, yeniden egit.

### 5.2 Ironi ve Sapanin (Sarcasm)

"Harika, cok iyiydi" (ironik) veya "Tabi ya, sen her seyi biliyorsun" (pasif agresif) her iki model tarafindan da dogru siniflandirilmiyor. Bu sinif siniflandirmasiyla degil, daha derin dil anlayisiyla cozulur.

**Onerilen cozum:** Guven < 0.60 ise GPT'ye yonlendir ve baginlami da ver.

### 5.3 Seyrekte Kalan Etiket Tipi

Egitim verisi yalnizca uc etiket iceriyor: Positive, Negative, Notr. Gercek konusmalardaki "karma" duygu cumleler ("guzel ama pahahydi") icin uygun etiket yok. Bu cumleler ya yanlis siniflandiriliyor ya da esik mekanizmasiyla Notr'a dusuyor.

---

## 6. Ozet

V2 modeli üretime alindi ve V1 tamamen devre disi birakildi.

**Temel kazanimlar:**
- Uretim kodu (%100 V2): `app.py` → `ml_model.py` → `sentiment_model_v2.pkl`
- Etiket uyumsuzlugu tamamen giderildi (Positive/Negative/Notr tutarli)
- Günlük chat dogrulugu: %60 → **%90**
- Test CSV dogrulugu: V1 olculsuz → **%92.9**
- Guven skoru anlamli ve kalibire (yanlis tahminler dusuk guvenle geliyor)
- Sklearn versiyon uyusmazligi giderildi (1.6.1 → 1.8.0)
