# Konuşma Özetleyici (Conversation Summarizer) — Geliştirme Raporu

**Tarih:** 2026-05-18  
**Özellik:** AI destekli otomatik konuşma özeti  
**Etkilenen Dosyalar:** `backend/app.py`, `lib/screens/chat_screen.dart`, `lib/services/api_service.dart`

---

## 1. Motivasyon ve Problem Tanımı

Uzun süreli yazışmalarda kullanıcılar zamanla konuşmanın ana hatlarını, tartışılan konuları ve genel tonunu unutabilmektedir. Özellikle birkaç gündür devam eden bir sohbete geri döndüğünde "ne konuşmuştuk?" sorusu sık karşılaşılan bir durumdur. Geleneksel arama ve kaydırma yöntemleri bu sorunu çözmemekte; kullanıcı onlarca mesajı tek tek okumak zorunda kalmaktadır.

Bu özellik, kullanıcıya tek bir dokunuşla son 50 mesajın yapay zeka tarafından üretilmiş anlamlı bir özetini sunar. Amaç yalnızca mesajları kısaltmak değil; konuşmanın ruhunu, ana başlıklarını ve öne çıkan anlarını yakalayen bir analiz sunmaktır.

---

## 2. Sistem Mimarisi

```
Flutter (Chat Ekranı)
    │
    │  POST /conversation_summary
    │  {sender_id, receiver_id, limit}
    ▼
Flask Backend (app.py)
    │
    ├─ db_service.get_messages()        → Son N mesajı çek
    ├─ db_service.get_user_by_id()      → Kullanıcı adlarını çöz
    ├─ Mesajları formatlı metne dönüştür
    │
    ├─ OpenAI GPT-4.1-mini
    │      prompt: Yapılandırılmış JSON isteği
    │      temperature: 0.3
    │      max_tokens: 300
    │
    └─ JSON parse + tarih/sayı zenginleştirmesi
         │
         ▼
    Flutter → Modal Bottom Sheet göster
```

---

## 3. Backend Implementasyonu

### 3.1 Endpoint

```
POST /conversation_summary
```

**Parametreler:**

| Alan | Tip | Varsayılan | Açıklama |
|------|-----|-----------|----------|
| sender_id | int | zorunlu | Giriş yapmış kullanıcı |
| receiver_id | int | zorunlu | Karşı taraf |
| limit | int | 50 | Kaç mesaj analiz edilsin |

### 3.2 Veri Hazırlama

Veritabanından çekilen mesajlar doğrudan GPT'ye gönderilmez. Önce okunabilir bir format oluşturulur:

```
alper: harika bir gün geçirdim bugün
efe: nasıl yani ne yaptın
alper: arkadaşlarla çıktık, sonra sinemaya gittik
```

Bu format GPT'nin kim ne söyledi bilgisini kayıp olmadan işlemesini sağlar. Kullanıcı ID'leri yerine gerçek kullanıcı adları kullanılır — böylece özet "kullanıcı_6 şunu söyledi" yerine "alper şunu söyledi" şeklinde okunabilir çıktı üretir.

### 3.3 GPT Prompt Yapısı

GPT'ye rastgele özet üretmesi istenmez. Yapılandırılmış bir JSON şeması zorunlu kılınır:

```python
prompt = f"""
Aşağıdaki Türkçe sohbeti analiz et ve şu JSON formatında yanıt ver:
{{
  "summary":   "2-3 cümlelik genel özet",
  "topics":    ["konu1", "konu2", "konu3"],
  "mood":      "pozitif | negatif | nötr | karışık",
  "highlight": "Konuşmadan öne çıkan bir alıntı veya an"
}}

Sadece JSON döndür, başka hiçbir şey yazma.

Konuşma:
{formatted_messages}
"""
```

**Temperature 0.3 seçiminin gerekçesi:** Yüksek temperature değerlerinde GPT özette olmayan bilgiler üretebilir (hallucination). 0.3, tutarlı ve konuya sadık çıktılar için en uygun değerdir. Yaratıcılık burada bir değer değil, doğruluk değerdir.

### 3.4 Zenginleştirme Katmanı

GPT'nin döndürdüğü JSON üzerine Python katmanında ek bilgiler eklenir:

```python
result["message_count"] = len(messages)
result["date_from"]     = str(messages[0]["timestamp"])[:10]
result["date_to"]       = str(messages[-1]["timestamp"])[:10]
```

Bu sayede frontend ek API çağrısı yapmadan tarih aralığını ve analiz kapsamını gösterebilir.

### 3.5 Tam Yanıt Formatı

```json
{
  "summary": "alper ve efe bugün yaptıkları plan hakkında konuşmuş, akşam buluşma kararı almışlar. Genel ton samimi ve olumlu.",
  "topics": ["buluşma planı", "sinema", "akşam yemeği"],
  "mood": "pozitif",
  "highlight": "alper: 'harika bir gün geçirdim bugün'",
  "message_count": 48,
  "date_from": "2026-05-10",
  "date_to": "2026-05-18"
}
```

---

## 4. Flutter Implementasyonu

### 4.1 API Katmanı

`api_service.dart` dosyasına eklenen metod:

```dart
Future<Map<String, dynamic>> getConversationSummary({
  required int senderId,
  required int receiverId,
  int limit = 50,
}) async { ... }
```

### 4.2 Kullanıcı Arayüzü Akışı

Özellik `chat_screen.dart` içinde üç aşamada çalışır:

**Aşama 1 — Tetikleme:**  
AppBar'daki ikon `more_vert` yerine `summarize` ikonuna dönüştürüldü. Kullanıcı buna bastığında `_fetchConversationSummary()` çağrılır, ikon yerinde küçük bir `CircularProgressIndicator` gösterilir (kullanıcı bekleme süresini algılar).

**Aşama 2 — API Çağrısı:**  
Backend'e istek atılır. Hata durumunda `SnackBar` ile bilgi verilir, sayfa çökmez.

**Aşama 3 — Gösterim:**  
Yanıt gelince `_showSummarySheet()` ile modal bottom sheet açılır:

```
┌─────────────────────────────────────────────┐
│  📋 Konuşma Özeti                           │
│  48 mesaj  •  10 May – 18 May               │
│                                             │
│  [😊 Pozitif]                               │
│                                             │
│  "alper ve efe bugün yaptıkları plan        │
│   hakkında konuşmuş..."                     │
│                                             │
│  Konular:  [Buluşma]  [Sinema]  [Yemek]    │
│                                             │
│  ❝ 'Harika bir gün geçirdim bugün' ❞        │
└─────────────────────────────────────────────┘
```

### 4.3 Grup Sohbeti Kısıtlaması

Grup sohbetlerinde `summarize` ikonu devre dışı bırakılır. Grup konuşmaları çok taraflı olduğundan mevcut `sender_id/receiver_id` yapısı yetersiz kalır.

---

## 5. Teknik Kararlar ve Gerekçeler

| Karar | Alternatif | Gerekçe |
|-------|-----------|---------|
| GPT-4.1-mini kullanımı | GPT-4o | Özet için yeterli kalite, daha düşük maliyet ve gecikme |
| Temperature 0.3 | 0.7+ | Tutarlılık ve hallucination riski azaltma |
| Limit 50 mesaj | Tüm geçmiş | Token limiti ve maliyet yönetimi |
| JSON zorunlu format | Serbest metin | Frontend parse güvenilirliği |
| Kullanıcı adı çözümleme | ID gösterimi | Okunabilir özet kalitesi |

---

## 6. Neden Değer Katıyor?

**Kullanıcı deneyimi açısından:** Uzun bir yokluğun ardından sohbete dönen kullanıcı 2 saniyede konuşmanın özetini görebilir. Bu, WhatsApp veya Telegram'da bulunmayan ve uygulamayı rakiplerinden ayıran somut bir özelliktir.

**Akademik katkı açısından:** Konuşma analizi (conversation analysis) NLP literatüründe önemli bir alan olup bu özellik, üretken yapay zekanın günlük iletişim uygulamalarına entegrasyonuna pratik bir örnek oluşturmaktadır. Özetleme + konu çıkarımı + duygu tonu tespiti üçlüsü, tek bir API çağrısında birleştirilmiştir.

**Teknik katkı açısından:** Mevcut veritabanı altyapısı (get_messages, get_user_by_id) ve GPT entegrasyonu yeniden kullanıldı; sıfırdan yeni bir altyapı kurulmadı. Bu, yazılım mühendisliğinde yeniden kullanılabilirlik (reusability) ilkesinin somut uygulamasıdır.
