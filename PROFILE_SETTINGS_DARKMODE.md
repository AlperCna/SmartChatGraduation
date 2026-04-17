# Profil, Ayarlar ve Karanlık Mod — Yeni Özellikler Özeti

Bu döküman, SmartChat uygulamasına eklenen **Profil Yönetimi**, **Ayarlar Ekranı** ve **Karanlık Mod** özelliklerini açıklamaktadır.

---

## 1. Profil Yönetimi

### Neler Eklendi?
- Kullanıcılar **profil fotoğrafı** yükleyebilir (kamera veya galeriden)
- **"Hakkımda"** metni düzenlenebilir (maks. 140 karakter)
- Profil bilgileri (kullanıcı adı, e-posta) görüntülenebilir

### Nasıl Çalışır?

**Backend:**
- `users` tablosuna `profile_picture` ve `about` kolonları eklendi (migration: `migrate_profile.py`)
- 3 yeni API endpoint oluşturuldu:
  - `GET /profile/<user_id>` → Profil bilgilerini getirir
  - `PATCH /profile/<user_id>` → "Hakkımda" metnini günceller
  - `POST /profile/<user_id>/picture` → Profil fotoğrafını yükler (multipart/form-data)
- Yüklenen fotoğraflar `docs/` klasörüne `profile_{user_id}_{dosya_adı}` formatında kaydedilir

**Flutter:**
- `ProfileScreen` → Büyük yuvarlak avatar, kamera ikonu ile fotoğraf değiştirme, bilgi kartları
- `AuthProvider` → Login sonrası profil otomatik yüklenir, `loadProfile()`, `updateAbout()`, `updateProfilePicture()` metodları
- `ApiService` → `getProfile()`, `updateAbout()`, `uploadProfilePicture()` API çağrıları

### Değiştirilen/Eklenen Dosyalar
| Dosya | Değişiklik |
|-------|-----------|
| `backend/migrate_profile.py` | Yeni — DB migration scripti |
| `backend/app.py` | 3 yeni endpoint eklendi |
| `backend/services/db_service.py` | 3 yeni fonksiyon eklendi |
| `lib/screens/profile_screen.dart` | Yeni — Profil ekranı |
| `lib/providers/auth_provider.dart` | Profil alanları ve metodlar eklendi |
| `lib/services/api_service.dart` | 3 yeni API metodu eklendi |

---

## 2. Ayarlar Ekranı

### Neler Eklendi?
- WhatsApp benzeri **ayarlar sayfası**
- En üstte profil kartı (avatar + isim + hakkımda) → dokunulunca profil ekranına gider
- Karanlık Mod toggle (Switch)
- Bildirimler, Gizlilik, Sohbet Ayarları, AI Asistan Ayarları menü satırları (gelecek sürüm)
- Uygulama hakkında ve versiyon bilgisi
- Çıkış yap butonu (onay dialog'u ile)

### Nasıl Erişilir?
- Chat listesi ekranında sağ üstteki **⋮** menüsünden → **"Ayarlar"** seçeneği

### Değiştirilen/Eklenen Dosyalar
| Dosya | Değişiklik |
|-------|-----------|
| `lib/screens/settings_screen.dart` | Yeni — Ayarlar ekranı |
| `lib/screens/chat_list_screen.dart` | Popup menüye "Ayarlar" seçeneği eklendi |
| `lib/main.dart` | `/settings` ve `/profile` route'ları eklendi |

---

## 3. Karanlık Mod (Dark Mode)

### Neler Eklendi?
- Tam karanlık tema desteği (koyu arka planlar, uyumlu metin renkleri)
- Kullanıcı tercihi **kalıcı olarak** kaydedilir (uygulama kapatılıp açılsa bile hatırlar)
- Ayarlar ekranındaki **Switch** ile anlık olarak açılıp kapatılabilir

### Nasıl Çalışır?

**ThemeProvider** (`lib/providers/theme_provider.dart`):
- `ThemeMode` state'i tutar (light / dark)
- `toggleTheme()` → Karanlık mod aç/kapat
- `FlutterSecureStorage` ile tercih kaydedilir
- Uygulama başlangıcında `loadThemePreference()` ile kaydedilmiş tercih yüklenir

**AppTheme** (`lib/theme/app_theme.dart`):
- `lightTheme` → Açık tema (teal tonları, beyaz yüzeyler)
- `darkTheme` → Koyu tema (koyu yüzeyler, teal vurgular)
- Context-aware yardımcı fonksiyonlar eklendi:
  - `AppTheme.cardColor(context)` → Light'ta beyaz, dark'ta koyu gri
  - `AppTheme.textColor(context)` → Temaya göre doğru metin rengi
  - `AppTheme.chatBgColor(context)` → Sohbet arka plan rengi
  - `AppTheme.sentBubbleColor(context)` → Gönderilen mesaj balonu rengi
  - `AppTheme.receivedBubbleColor(context)` → Gelen mesaj balonu rengi
  - `AppTheme.surfaceColor(context)` → Yüzey rengi
  - `AppTheme.secondaryTextColor(context)` → İkincil metin rengi

**Dark Mod Renk Paleti:**
| Öğe | Light | Dark |
|-----|-------|------|
| Arka plan | `#F0F4F8` | `#121218` |
| Kart | `#FFFFFF` | `#1E1E2A` |
| Sohbet arka plan | `#E8EDF2` | `#0B0B10` |
| Gönderilen balon | `#D4F5E9` | `#005C54` |
| Gelen balon | `#FFFFFF` | `#1E1E2A` |
| Birincil metin | `#1A1D26` | `#E8E8EE` |
| İkincil metin | `#6B7280` | `#9CA3AF` |

### Değiştirilen/Eklenen Dosyalar
| Dosya | Değişiklik |
|-------|-----------|
| `lib/providers/theme_provider.dart` | Yeni — Dark mode state yönetimi |
| `lib/theme/app_theme.dart` | `darkTheme` ve context-aware renk yardımcıları eklendi |
| `lib/main.dart` | `ThemeProvider` eklendi, `darkTheme` ve `themeMode` bağlandı |

---

## Özet: Tüm Değiştirilen Dosyalar

| # | Dosya | Tip |
|---|-------|-----|
| 1 | `backend/migrate_profile.py` | Yeni |
| 2 | `backend/app.py` | Güncellendi |
| 3 | `backend/services/db_service.py` | Güncellendi |
| 4 | `lib/providers/theme_provider.dart` | Yeni |
| 5 | `lib/screens/profile_screen.dart` | Yeni |
| 6 | `lib/screens/settings_screen.dart` | Yeni |
| 7 | `lib/theme/app_theme.dart` | Güncellendi |
| 8 | `lib/main.dart` | Güncellendi |
| 9 | `lib/providers/auth_provider.dart` | Güncellendi |
| 10 | `lib/services/api_service.dart` | Güncellendi |
| 11 | `lib/screens/chat_list_screen.dart` | Güncellendi |
