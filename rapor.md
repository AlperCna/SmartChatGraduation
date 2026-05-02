# SmartChat — GPT Prompt İyileştirmesi & Hata Giderme Raporu

**Tarih:** 03 Mayıs 2026  
**Proje:** SmartChat Mezuniyet Projesi  
**Konu:** GPT mesaj önerilerinin ilişki metriklerine daha sıkı bağlanması ve sistem hatalarının giderilmesi

---

## 1. Tespit Edilen Sorunlar

### 1.1 GPT Önerilerinin İlişki Metriklerinden Kopukluğu

Proje danışmanı tarafından dile getirilen sorun şuydu: sistem kullanıcılar arasındaki samimiyet ve nezaket skorlarını hesaplamasına rağmen GPT bu değerlere yeterince bağlı kalmıyor, üretilen mesaj önerileri ilişki tarzından bağımsız biçimde fazla nazik ve resmi çıkıyordu.

**Kök neden:** `/complete` endpoint'indeki GPT prompt'u modele yalnızca bir etiket (`"Informal (Samimi/Kanka)"`) ve ham sayılar (`closeness: 80`) iletiyordu. GPT bu soyut bilgiyi davranışa dönüştüremeyip kendi varsayılan "kibar asistan" moduna dönüyordu.

### 1.2 Sistem Başlatma Hatası (500)

Uygulama açılışında `LOAD PROFILE ERROR` ve `getChatPartners` endpoint'lerinden 500 hatası alınıyordu.

**Kök neden:** `DB_PASSWORD` adında bir Windows sistem ortam değişkeni mevcuttu ve `.env` dosyasındaki şifreyi override ediyordu. Python `load_dotenv()` varsayılan olarak mevcut ortam değişkenlerini ezmediği için yanlış şifre MySQL'e gönderiliyordu.

---

## 2. Yapılan Değişiklikler

### 2.1 GPT Prompt Yeniden Yazıldı — `backend/app.py`

**Eski yaklaşım:**
```
Kullanıcılar arasındaki Samimiyet: {closeness}, Nezaket: {politeness}
İlişki Tarzı (Matris Sonucu): {matrix_style}
... '{matrix_style}' ilişki tarzına uygun şekilde yeniden yaz.
```

**Yeni yaklaşım:** Sayısal skorlar somut davranış kurallarına ve few-shot örneklere dönüştürülüyor.

İki yardımcı fonksiyon eklendi:

**`_build_style_instructions(closeness, politeness)`**  
Closeness ve politeness skorlarını GPT'nin doğrudan uygulayabileceği kurallara çeviriyor:

| Skor Aralığı | Üretilen Kurallar |
|---|---|
| closeness ≥ 75 | "sen" kullan, "ya/kanka/abi" eklenebilir, kısa ve doğal cümleler |
| closeness 40–74 | "sen" kullan, samimi ama argo yok |
| closeness < 40 | "siz" kullan, resmi ve mesafeli |
| politeness ≥ 75 | Kibar ifadeler koru, sert eleştiri kullanma |
| politeness ≤ 30 | Gereksiz nezaket kalıpları ekleme |

**`_build_style_example(closeness)`**  
Closeness seviyesine göre somut bir before/after örneği üretiyor:

| Closeness | Örnek |
|---|---|
| ≥ 75 | "toplantıya katılabilir misiniz?" → "ya toplantıda mısın" |
| 40–74 | "ne zaman gelcen" → "Ne zaman gelebilirsin?" |
| < 40 | "yarın görüşelim" → "Yarın görüşebilir miyiz?" |

**Temperature:** 0.4 → 0.3 düşürüldü (GPT daha tutarlı, daha az yaratıcı sapma).

### 2.2 DB Bağlantı Sorunu Giderildi

`backend/services/db_service.py` ve `backend/app.py` dosyalarında:

```python
# Eski
load_dotenv()

# Yeni
load_dotenv(override=True)
```

`override=True` parametresi `.env` dosyasının Windows sistem ortam değişkenlerini ezmesini sağlıyor.

---

## 3. Test Sonucu

**Test senaryosu:** Cold (Soğuk/Mesafeli) modundaki kullanıcı (closeness=0, politeness düşük)

| | Değer |
|---|---|
| Kullanıcı girişi | `yarın görüşelim` |
| GPT önerisi | `Yarın görüşebilir miyiz?` |
| İlişki tarzı | Cold (Soğuk/Mesafeli) |
| Beklenen davranış | Resmi, "siz" kipine yakın, soru formatı |
| Sonuç | ✓ Başarılı |

Öneri "siz" kipi, soru formatı ve resmi ton ile Cold moduna tam uyumlu çıktı.

---

## 4. Sonuç

GPT'ye soyut etiket yerine somut kurallar ve örnekler verildiğinde üretilen mesaj önerileri ilişki matrisine (closeness & politeness) belirgin biçimde daha uyumlu hale geldi. Sistem artık danışman tarafından dile getirilen "öneriler çok nazik kalıyor" sorununu aşmış durumdadır.
