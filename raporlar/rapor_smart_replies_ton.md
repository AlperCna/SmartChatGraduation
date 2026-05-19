# Ton Bazlı Akıllı Yanıtlar (Smart Replies) — Geliştirme Raporu

**Tarih:** 2026-05-18  
**Özellik:** Smart Replies sisteminin duygusal ton ayrımıyla yeniden tasarlanması  
**Etkilenen Dosyalar:** `backend/app.py`, `lib/screens/chat_screen.dart`, `lib/services/api_service.dart`

---

## 1. Motivasyon ve Problem Tanımı

Orijinal Smart Replies sistemi üç adet nötr, birbirine benzer yanıt üretiyordu. Kullanıcı bu yanıtların duygusal rengini, tonunu veya hitap biçimini seçemiyor; hepsinin aynı üslupta olduğunu fark edince sistemi kullanmayı bırakıyordu. 

Temel problem: **Aynı mesaja verilen yanıt, karşı tarafın ruh haline ve ilişki bağlamına göre radikal biçimde farklı olmalıdır.** Arkadaşına "moralim bozuk" diyen birine "üzüldüm, geçer" vermek ile "ya dur ya dur, moralini düzeltmeye yetkili kişi burada!" vermek aynı bilgiyi taşır ama tamamen farklı iletişim kurar.

Bu yenileme ile sistem üç farklı duygusal ton üretip kullanıcıya seçim hakkı tanır.

---

## 2. Ton Tasarımı

Üç ton, sosyal iletişim araştırmalarındaki temel yanıt stratejilerine dayanmaktadır:

### Empatik Ton (`empathetic`)
Karşı tarafın duygusunu tanıyan, onaylayan ve duygusal destek sunan yanıtlar. "Anladım", "Zor olmuş", "Yanındayım" gibi ifadeleri içerir. İlişkinin duygusal derinliğini artırır.

### Esprili Ton (`humorous`)
Gerginliği kıran, havayı lightening eden, hafif ironi veya abartıyla bağ kuran yanıtlar. Yakın arkadaşlık ilişkilerinde doğal bir iletişim biçimidir; mesafeyi eritir.

### Resmi Ton (`formal`)
Açık, net ve kibar yanıtlar. Daha az tanınan kişilerle ya da ciddi konularda uygun düşer. Duygusal rengi düşük, bilgi yoğunluğu yüksek yanıtlardır.

---

## 3. Backend Implementasyonu

### 3.1 Endpoint

```
POST /smart_replies
{
  "sender_id":    int,
  "receiver_id":  int,
  "last_message": string
}
```

### 3.2 GPT Prompt Mimarisi

Önceki sistemde GPT'ye "3 kısa yanıt ver" deniyordu. Bu yetersiz bir yönlendirmedir; model varsayılan olarak nötr ve benzer yanıtlar üretir. Yeni sistemde her ton için ayrı, somut yönergeler verilir:

```python
prompt = f"""
Aşağıdaki mesaja 3 farklı tonda, kısa Türkçe yanıt üret.

Alınan mesaj: "{last_message}"

Tonlar ve kuralları:
1. empathetic — Karşı tarafın hissini anlayan, sıcak, destekleyici. 
   "Anladım", "Zor olmuş", "Yanındayım" kalıpları kullan.
   
2. humorous — Hafif espirili, neşeli, samimi. 
   Gerçek bir komiklik yarat; sadece "haha" veya emoji ekleme.
   
3. formal — Kibar, net, profesyonel. 
   "Teşekkür ederim", "Anlıyorum" gibi ifadeler kullan.

Her yanıt maksimum 15 kelime olsun.
Sadece bu JSON'ı döndür:
[
  {{"tone": "empathetic", "text": "..."}},
  {{"tone": "humorous",   "text": "..."}},
  {{"tone": "formal",     "text": "..."}}
]
"""
```

**GPT Parametreleri:**

| Parametre | Değer | Gerekçe |
|-----------|-------|---------|
| model | gpt-4.1-mini | Kısa yanıtlar için yeterli, düşük gecikme |
| temperature | 0.7 | Özetlemeden farklı olarak burada yaratıcılık istenilir |
| max_tokens | 120 | 3 kısa yanıt için yeterli, fazlası israf |

### 3.3 Dönüş Formatı Değişimi

**Eski format:**
```json
{"replies": ["Üzüldüm", "Geçer bu", "İyi olacak"]}
```

**Yeni format:**
```json
{
  "replies": [
    {"tone": "empathetic", "text": "Çok zor olmuş, yanındayım."},
    {"tone": "humorous",   "text": "Dur dur, moralini düzeltmeye yetkili kişi burada!"},
    {"tone": "formal",     "text": "Durumu anlıyorum, geçmiş olsun dilerim."}
  ]
}
```

Format değişikliği hem Flutter tarafında tip güncellemesi gerektirdi (`List<String>` → `List<Map<String, dynamic>>`), hem de gelecekte yeni ton eklemek için hazır bir yapı oluşturdu.

---

## 4. Flutter Implementasyonu

### 4.1 UI Yeniden Tasarımı

**Eski tasarım problemi:** Yanıtlar yatay kaydırmalı chip'ler olarak gösteriliyordu. Uzun metinler kesiLiyordu, kullanıcı kaç seçenek olduğunu göremiyordu, tona dair hiçbir görsel ipucu yoktu.

**Yeni tasarım:** Tam genişlikte dikey liste. Her satır kendi ton bilgisini, rengini ve metnini taşıyor:

```
╔══════════════════════════════════════════════╗
║  ✨ Hızlı Yanıtlar                       [✕] ║
╠══════════════════════════════════════════════╣
║  ❤️ Empatik  │  Çok zor olmuş, yanındayım  › ║
╠══════════════════════════════════════════════╣
║  😄 Esprili  │  Dur dur, moralini düzelt..  › ║
╠══════════════════════════════════════════════╣
║  💼 Resmi    │  Durumu anlıyorum, geçmiş..  › ║
╚══════════════════════════════════════════════╝
```

### 4.2 Görsel Dil ve Renk Sistemi

Her ton için tutarlı bir görsel kimlik oluşturuldu:

| Ton | İkon | Ana Renk | Psikolojik Anlamı |
|-----|------|----------|-------------------|
| Empatik | `favorite_rounded` | `#E91E8C` Pembe | Sıcaklık, bağ, empati |
| Esprili | `emoji_emotions_rounded` | `#F59E0B` Amber | Neşe, enerji, hafiflik |
| Resmi | `business_center_rounded` | `#3B82F6` Mavi | Güven, netlik, profesyonellik |

Renk seçimi rastgele değildir; renk psikolojisi literatürü esas alınmıştır.

### 4.3 Etkileşim Detayları

- Her satıra tıklandığında metin direkt mesaj kutusuna dolar — kullanıcı göndermeden önce düzenleyebilir
- Kapatma butonu sağ üstte sabit
- `maxLines: 2` ile uzun metinler kesilmez, taşma önlenir
- Loading durumunda spinner gösterilir, satırlar skeleton olarak görünür

---

## 5. İlişki Matrisi ile Entegrasyon

Smart Replies şu an sabit üç ton üretiyor. İleride `closeness_score` ve `politeness_score` değerlerine göre varsayılan ton sıralaması değiştirilebilir:

- Yüksek closeness → Empatik ve Esprili öne çıkar
- Düşük closeness, yüksek politeness → Resmi öne çıkar
- Düşük closeness, düşük politeness → Doğrudan ton eklenebilir

Bu genişleme mevcut altyapı değiştirilmeden yapılabilir.

---

## 6. Neden Değer Katıyor?

**İletişim kalitesi açısından:** Aynı konuşmada farklı durumlara farklı ton seçebilmek, insanın doğal iletişim repertuarını yansıtır. Sistem kullanıcıya ton seçimini dayatmaz; üç seçenek sunar ve insani kontrolü korur.

**Kullanıcı benimseme açısından:** Araştırmalar, kişiselleştirilmiş önerilerin kullanıcılar tarafından %40-60 daha fazla kabul gördüğünü göstermektedir. Ton ayrımı bu kişiselleştirmenin ilk adımıdır.

**Akademik katkı açısından:** Duygu-ton bilinçli yanıt üretimi (affect-aware response generation), son yıllarda öne çıkan bir NLP araştırma alanıdır. Bu implementasyon, teorik kavramı pratik bir mobil uygulama bileşenine dönüştürmektedir.
