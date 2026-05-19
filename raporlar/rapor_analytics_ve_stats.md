# Oneri Analizi & Konusma Istatistikleri — Gelistirme Raporu

**Tarih:** 2026-05-18  
**Ozellik:** Suggestion Analytics + Conversation Statistics  
**Etkilenen Dosyalar:** `backend/app.py`, `backend/services/db_service.py`, `lib/screens/relationship_dashboard_screen.dart`, `lib/services/api_service.dart`

---

## 1. Motivasyon ve Problem Tanimi

Ilk versiyon Relationship Dashboard ekrani yalnizca tek bir metrik gosteriyordu: `closeness_score`. Bu yaklasim ciddi bir eksiklik barindiriyordu — iliskiyi tek bir sayiyla tanimlamak ne kadar dogru olabilir? Gercek iliskiler cok boyutludur: kim daha cok yaziyor, hangi saatte aktifler, konusmanin genel tonu ne, yapay zeka onerileri kabul gorüyor mu?

Bu gelistirme ile dashboard iki yeni analiz boyutu kazandi:

1. **Suggestion Analytics** — Sistemin onerdigi mesaj stillerinin kullanici tarafindan kabul/red edilme oranlari. "Hangi stil daha cok begeniyor?" sorusunu sayisal olarak yanitlar.
2. **Conversation Statistics** — Konusmanin nicel ve nitel analizi: mesaj sayisi, kimin daha cok yazdigi, en aktif saat, duygu dagilimi, en sik kullanilan kelimeler.

Bu iki analiz birlikte, kullaniciya iliskisini 360 derece gormesini saglayan bir kontrol paneli sunar.

---

## 2. Sistem Mimarisi

```
Flutter (RelationshipDashboardScreen)
    │
    ├── Future.wait([
    │       GET /relationships/history/<u1>/<u2>    → Closeness + iliskili istatistikler
    │       GET /conversation_stats/<u1>/<u2>       → Konusma istatistikleri
    │       GET /suggestion_analytics/<user_id>     → Oneri kabul/red analizi
    │       GET /mood_forecast/<u1>/<u2>            → Mood tahmini
    │   ])
    │   Dort API cagrisi paralel atilir — tek loading ekrani
    │
    ▼
Flask Backend (app.py)
    │
    ├── /suggestion_analytics/<user_id>
    │       └── db_service.get_suggestion_analytics()
    │               ├── SQL: Genel ozet (total/accepted/rejected/pending)
    │               └── SQL: Stil bazli gruplama
    │           Python: Kabul orani hesapla, best/worst_style belirle
    │
    └── /conversation_stats/<user1_id>/<user2_id>
            └── db_service.get_conversation_stats()
                    ├── SQL: Genel (toplam, ilk/son mesaj)
                    ├── SQL: Kisi basi mesaj sayisi
                    ├── SQL: En aktif saat (GROUP BY HOUR)
                    └── SQL: Tum metin icerikleri
                Python:
                    ├── Gunluk ortalama hesapla
                    ├── predict_sentiment() → duygu dagilimi
                    └── Counter + stopword → top_words
```

---

## 3. Backend Implementasyonu: Suggestion Analytics

### 3.1 Veritabani Katmani

**`db_service.py` — `get_suggestion_analytics(user_id)`**

Bu fonksiyon iki SQL sorgusu calistirir:

**Sorgu 1 — Genel ozet:**
```sql
SELECT
    COUNT(*) AS total,
    SUM(CASE WHEN status = 'accepted' THEN 1 ELSE 0 END) AS accepted,
    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected,
    SUM(CASE WHEN status = 'pending'  THEN 1 ELSE 0 END) AS pending
FROM message_suggestions
WHERE user_id = %s
```

**Sorgu 2 — Stil bazli gruplama:**
```sql
SELECT
    style,
    COUNT(*) AS total,
    SUM(CASE WHEN status = 'accepted' THEN 1 ELSE 0 END) AS accepted,
    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected
FROM message_suggestions
WHERE user_id = %s
GROUP BY style
ORDER BY total DESC
```

`message_suggestions` tablosu, `/complete` endpoint'inin her cagrildiginda bir satir olusturdugu, kullanicinin "Onayla" veya "Reddet" dediginde status alaninin guncellendigi tablodur. Bu tablo oneri sisteminin geri bildirim dongusudu.

### 3.2 Uygulama Katmani (app.py)

Python tarafinda hesaplanan metrikler:

```python
@app.route("/suggestion_analytics/<int:user_id>")
def suggestion_analytics(user_id):
    data = db_service.get_suggestion_analytics(user_id)
    summary = data["summary"]
    by_style = data["by_style"]

    # Genel kabul orani
    total = summary["total"] or 1
    acceptance_rate = round(summary["accepted"] / total * 100, 1)

    # Her stil icin kabul orani
    for row in by_style:
        t = row["total"] or 1
        row["acceptance_rate"] = round(row["accepted"] / t * 100, 1)

    # En cok / en az kabul edilen stil
    accepted_styles = [r for r in by_style if r["total"] >= 3]
    best_style  = max(accepted_styles, key=lambda r: r["acceptance_rate"])["style"] if accepted_styles else None
    worst_style = min(accepted_styles, key=lambda r: r["acceptance_rate"])["style"] if accepted_styles else None

    return jsonify({
        "total": summary["total"],
        "accepted": summary["accepted"],
        "rejected": summary["rejected"],
        "pending": summary["pending"],
        "acceptance_rate": acceptance_rate,
        "best_style": best_style,
        "worst_style": worst_style,
        "by_style": by_style
    })
```

**Minimum 3 ornek filtresi:** `total >= 3` kosulu olmadan tek bir kabul edilmis oneri bile olan bir stil %100 kabul orani gosterir — yaniltici. En az 3 ornek olmadan istatistiksel anlam tasimaz.

### 3.3 Tam Yakit Formati

```json
{
  "total": 40,
  "accepted": 28,
  "rejected": 7,
  "pending": 5,
  "acceptance_rate": 70.0,
  "best_style":  "informal",
  "worst_style": "formal",
  "by_style": [
    {"style": "informal", "total": 22, "accepted": 18, "rejected": 2, "acceptance_rate": 81.8},
    {"style": "neutral",  "total": 12, "accepted": 8,  "rejected": 3, "acceptance_rate": 66.7},
    {"style": "formal",   "total": 6,  "accepted": 2,  "rejected": 2, "acceptance_rate": 33.3}
  ]
}
```

---

## 4. Backend Implementasyonu: Conversation Statistics

### 4.1 Veritabani Katmani

**`db_service.py` — `get_conversation_stats(user1_id, user2_id)`**

Dort SQL sorgusu:

**Sorgu 1 — Genel:**
```sql
SELECT
    COUNT(*) AS total_messages,
    MIN(timestamp) AS first_message,
    MAX(timestamp) AS last_message
FROM messages
WHERE (sender_id = %s AND receiver_id = %s)
   OR (sender_id = %s AND receiver_id = %s)
```

**Sorgu 2 — Kisi basi mesaj sayisi:**
```sql
SELECT sender_id, COUNT(*) AS count
FROM messages
WHERE (sender_id = %s AND receiver_id = %s)
   OR (sender_id = %s AND receiver_id = %s)
GROUP BY sender_id
```

**Sorgu 3 — En aktif saat:**
```sql
SELECT HOUR(timestamp) AS hour, COUNT(*) AS count
FROM messages
WHERE (sender_id = %s AND receiver_id = %s)
   OR (sender_id = %s AND receiver_id = %s)
GROUP BY HOUR(timestamp)
ORDER BY count DESC
LIMIT 1
```

**Sorgu 4 — Metin icerikleri (sentiment + kelime analizi):**
```sql
SELECT content FROM messages
WHERE (sender_id = %s AND receiver_id = %s)
   OR (sender_id = %s AND receiver_id = %s)
  AND content IS NOT NULL
ORDER BY timestamp DESC
LIMIT 200
```

### 4.2 Python Islem Katmani

**Gunluk ortalama hesabi:**
```python
from datetime import datetime

days = (last_dt - first_dt).days or 1
avg_per_day = round(total_messages / days, 1)
```

Hesap basit gorunse de ince bir nokta var: `or 1` oneki sifira bolunmeyi engeller — ilk ve son mesaj ayni gundeyse `days = 0` olur.

**Duygu dagilimi:**
```python
# Son 60 mesaj uzerinde ornekleme (token maliyeti kontrolu)
sample = all_texts[:60]
sentiments = [predict_sentiment(t)["sentiment"] for t in sample if len(t.strip()) > 3]

counts = Counter(sentiments)
total_s = len(sentiments) or 1
sentiment_dist = {
    "positive": round(counts.get("Positive", 0) / total_s * 100, 1),
    "negative": round(counts.get("Negative", 0) / total_s * 100, 1),
    "neutral":  round(counts.get("Notr", 0)     / total_s * 100, 1),
}
```

Tum mesajlar uzerinde ML calistirmak hem yavas (N x 200 ms) hem de gereksizdir. 60 mesajlik ornekleme istatistiksel olarak yeterli temsil saglar.

**Kelime frekansi:**
```python
STOPWORDS = {
    # Turkce baglacslar ve zamirler
    "bir", "bu", "ve", "da", "de", "ama", "yani", "isste", "ki", "ile",
    "ne", "var", "ben", "sen", "o", "biz", "siz", "onlar", "mi", "mu",
    # Ingilizce yaygin kelimeler
    "image", "hello", "video", "are", "the", "and", "you", "ok",
    # Sistem mesajlari
    "gonderiminiz", "iletildi", "okundu", "fotograf", "ses",
}

words = []
for text in all_texts:
    tokens = text.lower().split()
    words.extend([w for w in tokens if len(w) > 2 and w not in STOPWORDS])

top_words = [{"word": w, "count": c} for w, c in Counter(words).most_common(8)]
```

**Neden stopword genisletildi?** Ilk versiyonda "image", "hello", "gonderildi" gibi kelimeler listenin basinda cikiyordu. Bu kelimeler anlamli konusma icerigi degil; sistem/medya mesajlaridir. Uc kategoride stopword listesi tamamlandi: Turkce baglacslar, ingilizce yaygin kelimeler, sistem/uygulama kelimeleri.

### 4.3 Tam Yakit Formati

```json
{
  "total_messages": 124,
  "first_message": "2025-08-04",
  "last_message": "2026-05-18",
  "avg_per_day": 0.4,
  "user1_count": 52,
  "user2_count": 72,
  "most_active_hour": 21,
  "sentiment": {
    "positive": 18.3,
    "negative": 28.6,
    "neutral":  53.1
  },
  "top_words": [
    {"word": "tamam",  "count": 14},
    {"word": "selam",  "count": 11},
    {"word": "naber",  "count": 8},
    {"word": "harika", "count": 6}
  ]
}
```

---

## 5. Flutter Implementasyonu

### 5.1 Paralel Veri Yukleme

```dart
Future<void> _loadAll() async {
  setState(() => _loading = true);
  try {
    final results = await Future.wait([
      _api.getRelationshipHistory(senderId: _me, receiverId: _other),
      _api.getConversationStats(user1Id: _me, user2Id: _other),
      _api.getSuggestionAnalytics(userId: _me),
      _api.getMoodForecast(senderId: _me, receiverId: _other),
    ]);
    setState(() {
      _history    = results[0];
      _stats      = results[1];
      _analytics  = results[2];
      _mood       = results[3];
      _loading    = false;
    });
  } catch (e) {
    setState(() => _loading = false);
  }
}
```

`Future.wait` dort API cagrisini paralel atiyor — seri yaklasimda 4 x ~300 ms = ~1.2 saniye bekleme olurdu; paralel yaklasimda en yavas cagri olan ~400 ms belirleyici. Kullanici deneyimi acisindan kritik bir optimizasyon.

### 5.2 AI Oneri Analizi Karti

```
╔══════════════════════════════════════════════════════╗
║  🤖 AI Oneri Analizi                                 ║
╠══════════════════════════════════════════════════════╣
║  Toplam    Kabul    Red                              ║
║    40       28       7                               ║
╠══════════════════════════════════════════════════════╣
║  Genel Kabul Orani                                   ║
║  ████████████████░░░░   70.0%                        ║
╠══════════════════════════════════════════════════════╣
║  En Cok:  [Samimi/Kanka]    En Az: [Resmi]           ║
╠══════════════════════════════════════════════════════╣
║  Samimi/Kanka  ████████████████████░  81.8%          ║
║  Notr/Belirsiz ██████████████░░░░░░░  66.7%          ║
║  Resmi         ██████░░░░░░░░░░░░░░░  33.3%          ║
╚══════════════════════════════════════════════════════╝
```

**Progress bar renk mantigi:**
- Yesil (≥60%): Sistem bu stilden kabul goruyor, devam et
- Turuncu (<60%): Bu stil kullanici icin calismiyor, gozden gecir

**Stil normalize helper:**

```dart
String _normalizeStyle(String style) {
  switch (style.toLowerCase()) {
    case "informal":  return "Samimi / Kanka";
    case "formal":    return "Resmi / Kibarca";
    case "neutral":   return "Notr / Belirsiz";
    case "assertive": return "Dogrudan";
    case "empathetic":return "Anlayisli";
    default:          return style;
  }
}
```

API'den gelen ham stil degerleri (`informal`, `formal`, `neutral`) teknik tearim — kullaniciya gosterilecek metinler Turkce ve anlamli olmali. Bu helper iki dunyayi birbirinden izole eder; backend stil isimlendirmesi degisse bile bu tek nokta guncellemesi yeterli olur.

### 5.3 Konusma Istatistikleri Karti

```
╔══════════════════════════════════════════════════════╗
║  💬 Konusma Istatistikleri                           ║
╠══════════════════════════════════════════════════════╣
║  Toplam Mesaj    Gunluk Ort.    En Aktif Saat        ║
║      124            0.4           21:00              ║
╠══════════════════════════════════════════════════════╣
║  Kim Daha Cok Yaziyor?                               ║
║  Sen   ██████████░░░░░░░░░░░  42%                    ║
║  Kars. ░░░░░░░░░░██████████  58%                     ║
╠══════════════════════════════════════════════════════╣
║  Duygu Dagilimi                                      ║
║  Poz ██░░░░░░░░░  18.3%                              ║
║  Notr ██████░░░░  53.1%                              ║
║  Neg  ███░░░░░░░  28.6%                              ║
╠══════════════════════════════════════════════════════╣
║  Sik Gecen Kelimeler                                 ║
║  [tamam 14] [selam 11] [naber 8] [harika 6]          ║
╠══════════════════════════════════════════════════════╣
║  📅 04 Agu 2025 — 18 May 2026                        ║
╚══════════════════════════════════════════════════════╝
```

**"Kim daha cok yaziyor" iki renkli bar:** Kullanicinin kendi bari Teal (#26A69A), karsi tarafin bari Indigo (#5C6BC0). Kullanici mesaj dengesizligini tek bakista anlayabilir — "karsi taraf hep benden cok yaziyorsa" ya da "hep ben yaziyorsam" sezgisel olarak okunur.

**En aktif saat gosterimi:** `most_active_hour: 21` → `"21:00"` formatina cevirilir. Bu bilgi mood forecast'taki `night_writer` bulgusunu tamamlar — sistemin "gece yazar" tespiti kullanicinin kendi istatistiklerinde de gorulur.

---

## 6. Tasarim Kararlari ve Gerekceleri

| Karar | Alternatif | Gerceke |
|-------|-----------|---------|
| 60 mesaj ornekleme (sentiment) | Tum mesajlar | Token maliyeti + gecikme kontrolu; 60 istatistiksel yeterli |
| Future.wait paralel yukleme | Seri await | 3x daha hizli yukleme; kullanici deneyimi |
| minimum 3 ornek filtresi (analytics) | Filtresiz | 1 kabulde %100 gosterilmesi yaniltic |
| Stopword uc kategorisi | Sadece Turkce | Ingilizce + sistem kelimeleri de kirletiyor |
| _normalizeStyle helper | Direkt string | Backend degisikliklerine karsi izolasyon |

---

## 7. Neden Deger Katiyor?

**Kullanici icin:** Dashboard artik yalnizca "bu kisiye ne kadar yakinim?" sorusunu degil, "bu iliskide ben nasil davraniyorum?" sorusunu da yanitliyor. Kim daha cok yazdigini gorup dengesi bozuk iliskilerde farkinda olmak, bazen iliskileri kurtarabilecek kadar degerli bir bilgidir.

**Sistem icin:** Suggestion Analytics, AI oneri sisteminin kalitesini zaman icinde olcmek ve gelistirmek icin gereken geri bildirim dongusudu. Hangi stilin kabul gordugunun bilinmesi, ilerleyen asamalarda kullaniciya "Bu kisi icin en etkili stil X, bunu deneyelim" seklinde kisisellestirilmis oneri yapilabilmesinin temelidir.

**Akademik kati:** Konusma analizi (conversation analysis) NLP arastirmalarinda temel bir alan olup bu implementasyon; duygu dagilimi, kelime frekansi analizi ve iliskisel asimetri (kimin daha cok yazdigi) gibi birden fazla konusma metrigini tek bir API cagrisiyla birlestirmektedir. Ayrica oneri sistemleri literaturunde "geri bildirim dongusü" (feedback loop) konsepti, iyilestirici AI sistemlerinin temel bilesenidir — Suggestion Analytics bu konseptin pratik uygulamasidir.
