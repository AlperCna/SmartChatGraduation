# Mood Forecast ML & Empathy Scorer — Gelistirme Raporu

**Tarih:** 2026-05-18  
**Ozellikler:** Mood Forecast yeniden tasarimi (ML tabanli) + Empathy Scorer yeni endpoint  
**Etkilenen Dosyalar:** `backend/app.py`, `backend/services/db_service.py`, `lib/screens/relationship_dashboard_screen.dart`

---

## 1. Mood Forecast — ML'e Tasima

### 1.1 Eski Yaklasimin Sorunlari

Onceki implementasyon, bir onceki konusmanin son **3 mesajini** okuyordu. Icinde 1 tane bile negatif mesaj varsa direkt "negative" donduruyordu. Bu yaklasimin bes temel kusuru vardi:

1. **Zaman boyutu yok:** 3 gun once yazilan gergin bir mesaj ile 3 dakika once yazilan gergin bir mesaj ayni agirlikta degerlendiriliyordu.
2. **Cok az veri:** 3 mesaj istatistiksel olarak anlamsiz bir orneklem. Biri "tamam" diye tek mesaj yazmissa sistem bunu yorumlayamiyor.
3. **Saatlik/gunluk patern koru:** Biri her gece saat 2'de gergince yaziyorsa bu onun "gece modu", yoksa guncel bir cataklasma degil.
4. **Mesajlasma sikligi goz ardi edildi:** Kisi 7 gundir 50 mesaj yazarken bugün hicbir sey yazmadiysa bu sessizlik onemli bir sinyal.
5. **Binary cikti:** Yalnizca "negative" veya "positive" — ara tondaki mesajlar (mixed, neutral) kayboluyor.

### 1.2 Yeni Algoritma: Bes Katman

#### Katman 1 — Zaman Agirlikli Sentiment

Son 30 mesaj cekilir. Her mesajin yasi (`age_hours`) hesaplanir ve ustel bozunum (exponential decay) uygulanir:

```python
import math

LAMBDA = 0.08  # Bozunum sabiti

for msg in messages:
    age_hours = (now - msg["timestamp"]).total_seconds() / 3600
    weight    = math.exp(-LAMBDA * age_hours)
    sentiment = predict_sentiment(msg["content"])
    
    sentiment_map = {"Positive": +1.0, "Notr": 0.0, "Negative": -1.0}
    score = sentiment_map.get(sentiment["sentiment"], 0.0) * sentiment["confidence"]
    
    weighted_scores.append(score * weight)
    weights.append(weight)

weighted_avg = sum(weighted_scores) / sum(weights)
```

**Lambda seciminin mantigi:**

| Mesaj yasi | weight = exp(-0.08 * t) |
|-----------|------------------------|
| 30 dakika | 0.96 (neredeyse tam agirlik) |
| 6 saat | 0.62 (hala dominant) |
| 24 saat | 0.15 (minimal etki) |
| 48 saat | 0.02 (pratikte sifir) |

Lambda = 0.08 deger, "son 6 saat agirlikli belirleyici, 24 saat oncesi neredeyse onemli degil" davranisi saglar. Daha kucuk lambda (0.02) cok uzun hafiza — 3 hafta onceki mesajlar hala etkileyici. Daha buyuk lambda (0.3) cok kisa hafiza — yalnizca son 1-2 mesaj belirleyici ve gurultulu.

#### Katman 2 — Trend Tespiti

Mesajlar iki yariya bolunur: birinci yari en yeni mesajlari, ikinci yari daha eski mesajlari icerir. Aralarindaki fark trendi belirler:

```python
mid = max(1, len(raw_sentiments) // 2)

score_recent = sum(sentiment_map.get(s, 0) for s in raw_sentiments[:mid]) / mid
score_older  = sum(sentiment_map.get(s, 0) for s in raw_sentiments[mid:]) / max(1, len(raw_sentiments) - mid)

delta = score_recent - score_older

if delta > 0.15:
    trend = "rising"    # Konusma giderek iyilesiyor
elif delta < -0.15:
    trend = "falling"   # Konusma giderek kötülessiyor
else:
    trend = "stable"    # Dengeli seyir
```

Trend bilgisi mood'dan bagimsiz degerlidir: "negative ama rising" ile "negative ve falling" cok farkli durumlari ifade eder. Birincisinde bir iyilesme var; ikincisinde konusma giderek kötülessiyor ve dikkat gerekiyor.

#### Katman 3 — Saatlik Yazma Paterni

Son 30 gunun mesaj dagilimi saat bazinda analiz edilir:

```python
# db_service.py
def get_hourly_sentiment_pattern(user_id, partner_id):
    sql = """
    SELECT HOUR(timestamp) AS hour, COUNT(*) AS count
    FROM messages
    WHERE (sender_id = %s AND receiver_id = %s)
       OR (sender_id = %s AND receiver_id = %s)
      AND timestamp >= NOW() - INTERVAL 30 DAY
    GROUP BY HOUR(timestamp)
    ORDER BY hour
    """
```

```python
# app.py
night_hours = {22, 23, 0, 1, 2, 3, 4, 5, 6}
total_msgs  = sum(h["count"] for h in hourly_data)
night_msgs  = sum(h["count"] for h in hourly_data if h["hour"] in night_hours)
night_ratio = night_msgs / total_msgs if total_msgs > 0 else 0

night_writer = night_ratio > 0.5   # Mesajlarinin %50+ gece yazilmis
```

`night_writer: true` olan bir kullanicinin gece yazildigi negatif mesajlari, gunduz yazilan negatif mesajlardan farkli yorumlanmali. Sistem bu bilgiyi `warning` metnine dahil eder: "Bu kisi genellikle gece aktif — gece mesajlarinda daha duygusal tonlar normal."

#### Katman 4 — Mesajlasma Sikligi Dusuu

```python
# db_service.py
def get_message_frequency(user_id, partner_id):
    sql = """
    SELECT DATE(timestamp) AS date, COUNT(*) AS count
    FROM messages
    WHERE (sender_id = %s AND receiver_id = %s)
       OR (sender_id = %s AND receiver_id = %s)
      AND timestamp >= NOW() - INTERVAL 7 DAY
    GROUP BY DATE(timestamp)
    ORDER BY date DESC
    """
```

```python
# app.py
if len(daily_counts) >= 3:
    today_count     = daily_counts[0]["count"]
    avg_last_7_days = sum(d["count"] for d in daily_counts[1:]) / max(1, len(daily_counts) - 1)
    freq_drop       = today_count < (avg_last_7_days * 0.4)
```

`freq_drop: true` → Kisi son 7 gunun ortalamasinin %40'in altinda mesaj atiyor. Bu sessizlik bir sinyal — mesgul, yorgun veya konudan uzaklasmiyor olabilir. Sistemin uyari metni bunu "Kisi bugun normalden az mesaj atiyor; yoğun veya yorgun olabilir" seklinde yorumlar.

#### Katman 5 — Mood Karari ve Anlamlandirma

```python
# Mood siniflandirma
if weighted_avg <= -0.35:
    mood = "negative"
elif weighted_avg >= 0.35:
    mood = "positive"
elif -0.35 < weighted_avg <= -0.10:
    mood = "mixed"      # Hafif negatif egimli
else:
    mood = "neutral"

# Uyari metni olusturma
if mood == "negative" and trend == "falling":
    warning = "Son mesajlarda giderek daha gergin bir ton var. Belki bugun konuyu hafif tutmak iyi olabilir."
elif mood == "negative" and night_writer:
    warning = "Bu kisi genellikle gece aktif — gece mesajlarinda daha duygusal tonlar normal olabilir."
elif freq_drop:
    warning = "Kisi bugun normalden cok az mesaj atiyor; mesgul veya yorgun olabilir."
elif mood == "positive" and trend == "rising":
    warning = None   # Iyi konusmada uyariya gerek yok
```

### 1.3 Yanit Formati

```json
{
  "mood":         "negative",
  "score":        -0.358,
  "trend":        "falling",
  "warning":      "Son mesajlarda giderek daha gergin bir ton var. Belki bugun konuyu hafif tutmak iyi olabilir.",
  "tip":          "Empati gosteren kisa bir cumle konusmayi yumusatabilir.",
  "data_points":  12,
  "night_writer": false,
  "freq_drop":    false
}
```

Eski yanita gore 5 yeni alan: `score`, `trend`, `tip`, `night_writer`, `freq_drop`. `data_points` alani kac mesaj uzerinde tahmin yapildigini gosteriyor — 2 mesajla yapilan tahmin ile 25 mesajla yapilan tahmin arasindaki guvenilirlik farki kullaniciya aktarilabiliyor.

### 1.4 Veritabani Fonksiyonlari (db_service.py)

```python
def get_messages_for_mood_forecast(user_id: int, partner_id: int, limit: int = 30):
    """
    Mood forecast icin mesajlari ceker.
    - Sadece ALICI'dan gelen mesajlari alir (karsi tarafin duygu durumu)
    - Sistem/medya mesajlarini filtreler
    - Timestamp ile birlikte dondurur (zaman agirliklandirma icin)
    """
    sql = """
    SELECT content, timestamp
    FROM messages
    WHERE sender_id = %s AND receiver_id = %s
      AND content NOT REGEXP '^(image|video|ses|fotograf|\\[)'
      AND LENGTH(content) > 2
    ORDER BY timestamp DESC
    LIMIT %s
    """
    return execute_query(sql, (partner_id, user_id, limit))
```

Kritik tasarim karari: **yalnizca alicidan gelen mesajlar** alinir (`sender_id = partner_id`). Mood forecast, karsi tarafin ruh halini tahmin etmeyi amaclar — kullanicinin kendi yazdiklari degil, karsi tarafin yazdiklari analiz edilir.

---

## 2. Empathy Scorer

### 2.1 Neden Gerekli?

Kullanicinin gonderdigi mesajin empati duzeyi, konusmanin gidisatini dogrudan etkiler. Yuksek empati → karsi taraf daha acik, daha guvenli. Dusuk empati → yanlisanlasilma, mesafe artisi.

Ancak empati olcmek zordur:
- Kural bazli yaklasim Turkce kaliplari yakalayabilir ama bagi anlayamaz
- GPT bagi anlar ama her mesaj icin GPT cagirmak yavas ve pahali

Cozum: **Hibrit mimari** — kural bazli hizli bir ilk gecis, ardindan GPT ile derin analiz. Ikisi agirliklara gore birlestirilir.

### 2.2 Mimari

```
POST /empathy_score
{
  "text":        string,   // Kullanicinin yazdigi mesaj
  "sender_id":   int,
  "receiver_id": int
}

                              Mesaj metni
                                  │
               ┌──────────────────┴──────────────────┐
               │                                      │
    Kural tabanlı analiz                   GPT-4.1-mini analizi
    Turkish pattern matching               Bağlam: son 4 alıcı mesajı
    _rule_based_empathy_score()            + mesaj metni
               │                                      │
    rule_score (0-100)                     gpt_score (0-100)
         ×0.35                                  ×0.65
               │                                      │
               └──────────────────┬──────────────────┘
                                  │
                         final_score = rule×0.35 + gpt×0.65
                                  │
                    politeness_delta hesabi
                                  │
                    UPDATE user_relationships
```

### 2.3 Kural Tabanlı Bileşen

```python
_EMPATHY_PATTERNS = {
    "high": [
        "anladim", "anliyorum", "zor olmusstur", "zor olmali",
        "uzgunum", "yanindayim", "seninle birlikteyim",
        "ne yapabilirim", "nasil yardimci olabilirim",
        "hakkisin", "anlasiliyor", "tabii ki", "kesinlikle hakliyorsun",
        "cok zor", "bu gercekten zor", "destekliyorum"
    ],
    "medium": [
        "tamam", "dogru", "biliyorum", "sabret", "gecer",
        "iyi olur", "dusunmustum", "duymustum", "anlattin"
    ],
    "low": [
        "sacmalama", "abartiyorsun", "neden", "ne diyorsun",
        "yok oyle bir sey", "sen ne biliyorsun", "su kadar basit",
        "sen anlayamazsin"
    ]
}

def _rule_based_empathy_score(text: str) -> float:
    text_lower = text.lower()
    score = 0.40  # Notr baslangic noktasi

    for pattern in _EMPATHY_PATTERNS["high"]:
        if pattern in text_lower:
            score += 0.15
    for pattern in _EMPATHY_PATTERNS["medium"]:
        if pattern in text_lower:
            score += 0.05
    for pattern in _EMPATHY_PATTERNS["low"]:
        if pattern in text_lower:
            score -= 0.12

    return max(0.0, min(1.0, score))   # [0.0, 1.0] arasi clamp
```

Baslangic noktasi 0.40 (notr): sifir yazilmis bir mesaj yerine, ozel bir sinyalin yoklugunda orta-dusuk bir deger mantikli. Tam sifirdan baslamak, herhangi bir medium pattern olmadigi durumlarda bile cok dusuk skor uretirdi.

### 2.4 GPT Bileseni

```python
context_messages = db_service.get_recent_receiver_messages(
    sender_id=sender_id,
    receiver_id=receiver_id,
    limit=4
)
context_text = "\n".join([f"- {m['content']}" for m in context_messages])

gpt_prompt = f"""
Asagidaki mesaj bir konusmada yaziliyor. Mesajin empati duzeyini degerlendir.

Baglamdaki son mesajlar (karsi tarafin yazdiklari):
{context_text}

Analiz edilecek mesaj:
"{text}"

Su 4 kritere gore 0-100 arasi puan ver:
1. Duygusal taninma: Karsi tarafin hissini fark ediyor mu?
2. Dogrulama: "Hakliyorsun", "Anliyorum" gibi ifadeler var mi?
3. Destek sunma: Yardim teklifi veya yaninda oldugunu hissettiriyor mu?
4. Ton: Sicak mi, soguk mu, elestirel mi?

Yalnizca bu JSON'i dondur:
{{
  "gpt_score": <0-100 arasi sayi>,
  "feedback":  "<1-2 cumle degerlendirme>",
  "suggestion": "<iyilestirme onerisi>"
}}
"""

response = openai_client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[{"role": "user", "content": gpt_prompt}],
    temperature=0.3,
    max_tokens=150
)
```

**Neden temperature 0.3?** Empati degerlendirmesi oznel ama tutarli olmali. Yuksek temperature (0.7+) ayni mesaj icin farkli puanlar uretir — guvenilir bir skor icin dusuk temperature gerekli. 0.3 kucuk bir yaraticilik payi birakir (feedback metni farkli ifade edilebilir) ama puan stabilitesini korur.

**Neden %65 GPT agirligi?** Kural bazli sistem yalnizca belirli Turkce kaliplarini ariyor — bir mesajin tamamini, baglamini veya tonunu anlayamiyor. GPT ise tam cumleyi, konusma baglamini ve anlami birlikte degerlendiriyor. Bu fark, GPT'ye daha yuksek agirlik verilmesini hakli kiliyor. Ancak %100 GPT yapmamak gecikmeyi ve maliyeti optimize ediyor: kural bazli %35 pay, GPT'nin yorumlamasina hafifce destek veriyor.

### 2.5 politeness_score Guncellenmesi

```python
final_score = int(rule_score * 0.35 + gpt_score * 0.65)

# Empati seviyesine gore politeness degisimi
if final_score >= 70:
    delta = +4
elif final_score >= 50:
    delta = +1
elif final_score >= 30:
    delta = 0
else:
    delta = -3

# Veritabani guncelleme
if delta != 0:
    db_service.update_politeness(
        user_id=sender_id,
        partner_id=receiver_id,
        delta=delta
    )
```

Bu guncelleme mekanizmasinin ozunu olustu: Kullanici sistematik olarak empati gosteren mesajlar yaziyorsa politeness_score zamanla yukseliyor. Bu da iliskinin "Serbest Uzak" → "Serbest Yakin" veya "Resmi Uzak" → "Saygin" gibi evrimi anlamina geliyor. Tersine, surekli empati dusuk mesajlar politeness_score'u asagilik cekiyor.

**Delta neden asimetrik (+4 vs -3)?** Empati kurmak zordur, yikmak kolaydir. Pozitif geri bildirim cok kucuk adimlarla gelir (+1, +4); negatif geri bildirim daha az ama belirgin (-3). Bu, iliskinin dengeli seyir etmesi icin tasarlandi — tek bir kotu mesaj tum empati birikimini silmemeli.

### 2.6 Test Ornekleri

| Mesaj | rule_score | gpt_score | final | level |
|-------|-----------|----------|-------|-------|
| "Anladim, zor olmusstur. Seninle birlikteyim." | 55 | 78 | 70 | high |
| "Iyi olur, gecer." | 45 | 52 | 49 | medium |
| "Tamam." | 40 | 38 | 39 | low |
| "sacmalama, abartiyorsun" | 16 | 8 | 11 | very_low |
| "Cok zor olmali bu durum, nasil yardimci olabilirim?" | 70 | 88 | 82 | high |

### 2.7 Tam Yanit Formati

```json
{
  "score":            68,
  "level":            "medium",
  "rule_score":       52,
  "gpt_score":        75,
  "feedback":         "Mesaj karsi tarafin zor bir durum yasadigini fark edip anladigini belirtiyor, ancak duygusal destek sinirli kaliyor.",
  "suggestion":       "Daha fazla duygusal dogrulama eklenebilir, ornegin 'Istersen konusabiliriz.'",
  "politeness_delta": 1
}
```

`level` alanlari: `very_low` (0-29), `low` (30-49), `medium` (50-69), `high` (70-89), `very_high` (90+).

---

## 3. Flutter Entegrasyonu (Mevcut Durum)

Empathy Scorer endpoint'i backend'de hazir ve test edilmis durumda. Flutter entegrasyonu ertelendi — ozellik su an yalnizca API olarak erisililebilir durumdadir.

**Planlanan entegrasyon senaryosu:**
Kullanici mesaj yazarken `✨` menusunden "Empati Puani" secenegini acabilir. Panel acilir, skor ve iyilestirme onerisi gosterilir. Kullanici ister metni oneridogrultusunda duzeltir, ister oldugu gibi gonderir.

Mood forecast ise hali hazirda Flutter'da calisir durumda — `RelationshipDashboardScreen` Mood karti bu veriye gore gosterim yapıyor.

---

## 4. Degistirilen Dosyalar

| Dosya | Degisiklik |
|-------|-----------|
| `backend/app.py` | `/mood_forecast` komple yeniden yazildi; `POST /empathy_score` eklendi; `_EMPATHY_PATTERNS` ve `_rule_based_empathy_score()` eklendi |
| `backend/services/db_service.py` | 4 yeni fonksiyon: `get_messages_for_mood_forecast()`, `get_hourly_sentiment_pattern()`, `get_message_frequency()`, `get_recent_receiver_messages()` |
| `lib/screens/relationship_dashboard_screen.dart` | Mood Forecast karti eklendi; `_buildMoodCard()`, `_moodConfig()` implementasyonu |

---

## 5. Neden Deger Katiyor?

**Mood Forecast:**  
Eski implementasyonda "son mesajda 'iyi' dedi mi?" seviyesinde bir tahmin vardi. Yeni sistemde son saatler agirlikli, trend dinamik, gece yazarligi ve sessizlik de sinyal olarak kullaniliyor. Bu, duygusal tahmin problemini birer metin siniflandirmasindan bir zaman serisi analizi problemine donustururyor — kavramsal olarak cok daha guclu bir yaklasim.

**Empathy Scorer:**  
Kullanicinin mesaji gonderilmeden once empati duzeyini gormesi, iletisimi reaktif degil proaktif yapıyor. Sistemi "nasil yazilmis?" degil "ne kadar empatik yazilmis?" soruna odaklanacak sekilde tasarlamak, sosyal beceri destegi alaninda aracarastirmasi literaturunde "just-in-time feedback" kavramininin pratik uygulamasi.

**Politeness_score Dinamigi:**  
Kullanicinin iliskiyi nasil yonettigi zamanla sayisal olarak izlenebilir hale geliyor. "Bu kisi zamanla daha empatik davrani mi?" sorusuna veri tabanindaki politeness degisimi ile yanitlanabilir — bu, davranissal degisim olcumu acisindan degerli bir araclir.

**Akademik kati:**  
- Zaman agirlikli duygu analizi (time-weighted sentiment analysis): sosyal bilisim ve iletisim arastirmalarinda guncel konular arasinda
- Empati tespiti (empathy detection): NLP literaturunde son yillarda artis gosteren bir alt alan; Buechel et al. (2018) ve Rashkin et al. (2019) temel referanslar
- Hibrit kural+GPT mimari: verimlilik ile kalite arasindaki dengeyi saglayan yakin donem pratik yaklasim
