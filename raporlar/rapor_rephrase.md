# "Bunu Nasıl Söylesem?" (Rephrase) — Geliştirme Raporu

**Tarih:** 2026-05-18  
**Özellik:** Kullanıcının ham mesajını ilişki bağlamına göre 3 tonda yeniden yazma  
**Etkilenen Dosyalar:** `backend/app.py`, `lib/screens/chat_screen.dart`, `lib/services/api_service.dart`

---

## 1. Motivasyon ve Problem Tanımı

İnsanlar çoğu zaman ne söylemek istediklerini bilirler ama bunu nasıl ifade edeceklerini bulamazlar. "Neden hep geç kalıyorsun?" demek istiyorken karşı tarafı kırmadan bunu nasıl söyleyeceğini bilmemek, ya aşırı yumuşatılmış ya da sert çıkan mesajlara yol açar.

Mevcut `/complete` endpoint'i kullanıcının ham metnini **tek bir stil önerisiyle** tamamlıyordu. Bu yaklaşımın iki kısıtlaması vardı:
1. Kullanıcının tercihini sormadan tek bir ton dayatıyordu
2. İlişki bağlamını yüzeysel biçimde kullanıyordu

Rephrase özelliği bu iki problemi çözer: kullanıcıya **3 farklı ton versiyonu** sunar ve her versiyonu üretirken ilişki metriklerini (closeness + politeness), konuşma geçmişini ve mesajın duygu tonunu derinlemesine analiz eder.

---

## 2. Sistem Mimarisi

```
Kullanıcı ham metni yazar → ✨ butonuna basar → "Nasıl Söylesem?" seçer

Flutter → POST /rephrase
           {text, sender_id, receiver_id}

Backend (app.py):
  1. Son 5 mesaj → konuşma geçmişi
  2. GPT + DB hibrit stil tespiti (detect_style)
  3. ML sentiment analizi (predict_sentiment - V2 modeli)
  4. DB'den ilişki metrikleri (closeness, politeness)
  5. _build_rephrase_context() → doğal dil bağlam açıklaması
  6. GPT-4.1-mini → 3 ton versiyonu
  7. JSON parse + metadata zenginleştirme

Flutter ← {versions: [{tone, text}, ...], metadata...}

Floating Panel → Kullanıcı tona tıklar → Metin kutusuna dolar
```

---

## 3. Backend Implementasyonu

### 3.1 Endpoint

```
POST /rephrase
{
  "text":        string,   // Kullanıcının ham yazdığı
  "sender_id":   int,
  "receiver_id": int
}
```

### 3.2 Bağlam Zenginleştirme Pipeline'ı

Rephrase özelliğinin güçlü yanı, GPT'ye ham metni vermeden önce çok katmanlı bir bağlam oluşturmasıdır:

**Katman 1 — Konuşma Geçmişi:**  
Son 5 mesaj çekilerek GPT'ye bağlam sağlanır. GPT böylece konuşmanın nereye doğru gittiğini, hangi konunun konuşulduğunu anlayabilir.

**Katman 2 — Hibrit Stil Tespiti:**  
`detect_style()` fonksiyonu hem veritabanındaki ilişki stilini hem de gelen metnin yazım stilini analiz eder. Kullanıcı formal biri ile informal konuşuyor olabilir; bu ayrım tona yansıtılır.

**Katman 3 — Sentiment Analizi (V2 ML Modeli):**  
Kullanıcının ham metni `predict_sentiment()` ile analiz edilir. Negatif bir metin "Nazik" tona dönüştürülürken GPT'ye "bu metin negatif bir duygu içeriyor, bunu yumuşat" direktifi verilebilir.

**Katman 4 — İlişki Metrikleri:**  
`closeness_score` ve `politeness_score` değerleri `_build_rephrase_context()` fonksiyonu ile GPT'nin anlayabileceği doğal dil açıklamalarına çevrilir:

```python
def _build_rephrase_context(closeness: int, politeness: int) -> str:
    if closeness >= 75:
        ctx = "Bu kişiyle çok yakın, samimi bir arkadaşlık var. Argo ve hitap kelimeleri doğaldır."
    elif closeness >= 40:
        ctx = "Orta düzey tanışıklık. 'Sen' hitabı uygundur, samimi ama saygılı."
    else:
        ctx = "Az tanışıklık veya resmi ilişki. 'Siz' hitabı, mesafeli ve kibar."
    
    if politeness >= 70:
        ctx += " Konuşma tonu genellikle çok kibar ve resmidir."
    elif politeness <= 30:
        ctx += " Konuşma tonu samimi ve rahattır, formalite beklenmez."
    
    return ctx
```

Bu dönüşüm kritiktir: `closeness=85` sayısı GPT için anlamsızdır, ama "çok yakın samimi arkadaşlık" ifadesi doğrudan ton üretimine etki eder.

### 3.3 Prompt Mühendisliği: AMAÇ / YAP / YAPMA / ÖRNEK Yapısı

İlk iterasyonda GPT tonları yüzeysel uyguluyordu:
- "Nazik" → metin başına "merak ettim" ekliyordu, özü değiştirmiyordu
- "Doğrudan" → yazım hatalarını düzeltip aynı cümleyi bırakıyordu
- "Esprili" → "ya" veya "haha" gibi dolgu kelimeler ekliyordu

Bu sorunu çözmek için her ton için **AMAÇ / YAP / YAPMA / ÖRNEK** yapısı getirildi:

```
NAZİK TON:
  AMAÇ: Mesajın özündeki duyguyu veya isteği karşı tarafa incitmeden ilet.
        Söylemek istediğin şeyi söyle ama kapıyı kapatma.
  YAP:  Empati kur. Karşı tarafın bakış açısına yer aç.
        Soru formatı kullanarak yumuşat.
  YAPMA: "Merak ettim", "Acaba" gibi jenerik ekler koyma.
         Özü tamamen değiştirme, mesajı içi boş kibar bir şeye çevirme.
  ÖRNEK: "neden böyle yapıyorsun?" → "Bir şey mi oldu, anlatsana?"

DOĞRUDAN TON:
  AMAÇ: Mesajı fazla söz harcamadan, net ve anlaşılır biçimde söyle.
  YAP:  Tek cümle. Aktif dil. Ana noktayı ilk kelimeden ver.
  YAPMA: "Lütfen", "Acaba" gibi yumuşatıcılar ekleme.
         Uzatma, savunma veya gerekçe ekleme.
  ÖRNEK: "neden böyle yapıyorsun?" → "Böyle yapmanın sebebi ne?"

ESPRİLİ TON:
  AMAÇ: Mesajın gerçek anlamını koruyarak beklenmedik bir komiklik kat.
        Gerginliği kır, bağ kur.
  YAP:  İroni, abartı veya kelime oyunu kullan. Gerçekten komik olsun.
  YAPMA: Sadece ünlem veya emoji ekleyerek espri yapmaya çalışma.
         Sıradan bir cümleye "ya" ekleyip esprili saymaktan kaçın.
  ÖRNEK: "neden böyle yapıyorsun?" → "Böyle giderse seni kullanma kılavuzuyla anlamamız gerekecek."
```

Bu yapı, GPT'nin yüzeysel ton uygulamasını engelleyen en kritik tasarım kararıdır. Somut örnekler sayesinde model "ton"u soyut bir kavram olarak değil, somut bir uygulama olarak görür.

### 3.4 Tam Yanıt Formatı

```json
{
  "versions": [
    {"tone": "kind",     "text": "Bir şey mi oldu, anlatsana?"},
    {"tone": "direct",   "text": "Böyle yapmanın sebebi ne?"},
    {"tone": "humorous", "text": "Böyle giderse seni kullanma kılavuzuyla anlamamız gerekecek."}
  ],
  "original":            "neden byle yapıyorsun",
  "message_style":       "Informal",
  "relationship_style":  "Informal (Samimi/Kanka)",
  "sentiment":           "negative",
  "sentiment_confidence": 0.81,
  "closeness":           72,
  "politeness":          45,
  "timestamp":           "2026-05-18T14:32:11"
}
```

Metadata alanları kullanıcıya gösterilmez ama ileride analitik, A/B testi ve model iyileştirme için değerlidir.

**GPT Parametreleri:**

| Parametre | Değer | Gerekçe |
|-----------|-------|---------|
| model | gpt-4.1-mini | Ton üretimi için yeterli kalite |
| temperature | 0.6 | Yaratıcılık ve tutarlılık dengesi |
| max_tokens | 220 | 3 ton × ortalama 15-20 kelime + JSON overhead |

---

## 4. Flutter Implementasyonu

### 4.1 Çift Menü Yapısı

`✨` butonu artık tek işlev yapmak yerine iki seçenek sunar:

```
┌─────────────────────────┐
│  ✨ AI Önerisi          │  → /complete endpoint
│  💬 Nasıl Söylesem?    │  → /rephrase endpoint
└─────────────────────────┘
```

Bu yapı, gelecekte yeni AI araçları eklemeye hazır bir genişletilebilir menü sağlar.

### 4.2 Rephrase Panel Tasarımı

```
╔════════════════════════════════════════╗
║  📝 Nasıl Söylesem?               [✕] ║
╠════════════════════════════════════════╣
║  ❤️ Nazik    │  Bir şey mi oldu..   › ║
╠════════════════════════════════════════╣
║  ⚡ Doğrudan │  Böyle yapmanın..    › ║
╠════════════════════════════════════════╣
║  😄 Esprili  │  Böyle giderse..     › ║
╚════════════════════════════════════════╝
```

Smart Replies ile aynı görsel dil kullanıldı: ton etiketi | renkli ince ayraç | metin | ok ikonu. Bu tutarlılık kullanıcının iki özellik arasında öğrenme eğrisini sıfıra indirir.

### 4.3 Ton Renk Sistemi

| Ton | İkon | Renk | Psikolojik Anlam |
|-----|------|------|-----------------|
| Nazik | `favorite_rounded` | `#E91E8C` Pembe | Sıcaklık, empati |
| Doğrudan | `bolt_rounded` | `#6366F1` İndigo | Netlik, kararlılık |
| Esprili | `emoji_emotions_rounded` | `#F59E0B` Amber | Neşe, hafiflik |

---

## 5. Smart Replies vs Rephrase: Farklar

| Özellik | Smart Replies | Rephrase |
|---------|--------------|---------|
| Girdi | Karşı tarafın son mesajı | Kullanıcının kendi ham metni |
| Çıktı | 3 hazır yanıt seçeneği | Ham metnin 3 versiyonu |
| Amaç | Ne söyleyeyim? | Bunu nasıl söyleyeyim? |
| Bağlam kullanımı | Son 1 mesaj | Son 5 mesaj + ilişki metrikleri + sentiment |
| Kullanım senaryosu | Hızlı tepki | Düşünülmüş mesaj kalitesi artırma |

---

## 6. Neden Değer Katıyor?

**İletişim verimliliği:** Kullanıcı "nasıl söylesem" sorusunu zihninde 2-3 dakika düşünmek yerine 3 saniyede üç seçenek görüp istediğini seçiyor. Bu iletişim sürtünmesini (communication friction) dramatik biçimde azaltır.

**İlişki farkındalığı:** Sistemin ilişki metriklerini ton üretimine yansıtması, kullanıcıya "bu kişiyle ilişkim nasıl?" sorusunu sezgisel olarak hatırlatır. Yakın arkadaşa yazdığı tonla uzak tanıdığa yazması gerektiğinin farkına varmasını sağlar.

**Akademik katkı:** Bağlam farkındalıklı metin yeniden yazma (context-aware text rewriting) ve ilişki metriği güdümlü dil adaptasyonu (relationship-metric-driven language adaptation) bu özelliğin dayandığı iki araştırma alanıdır. Proje bu kavramları çalışan bir mobil uygulama bileşeni olarak somutlaştırmaktadır.
