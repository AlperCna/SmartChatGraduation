# 📊 Bitirme Projesi 2: İlişki Dinamiği Analiz Paneli (Feature 2) - Uygulama Özeti

Bu belge, SmartChat projesinde gerçekleştirilen **İlişki Dinamiği Analiz Paneli** özelliğinin teknik detaylarını ve yapılan çalışmaları özetlemektedir.

---

## 🎯 Amaç
Kullanıcı ile sohbet ettiği kişiler arasındaki samimiyet düzeyini (Closeness Score) sadece anlık bir sayı olmaktan çıkarıp, zaman içindeki değişimini akademik bir yaklaşımla **görselleştirmek** (Data Visualization) ve jüriye projenin "Yapay Zeka Destekli Analiz" gücünü kanıtlamak.

---

## 🛠️ Yapılan Teknik Çalışmalar

### 1. Veritabanı ve Migration (Veri Mimarisi)
- **Yeni Tablo:** `relationship_history` tablosu oluşturuldu. (Kolonlar: `history_id`, `user1_id`, `user2_id`, `closeness_score`, `timestamp`).
- **Migration Script:** `migrate_relationship_history.py` yazılarak var olan tüm ilişkilerin başlangıç noktaları (anlık skorları) tarihçeye işlendi.
- **Otomatik Tetikleyiciler:** `db_service.py` içinde `adjust_closeness` fonksiyonu güncellendi. Artık her skor değiştiğinde (pozitif/negatif mesaj sonrası), bu değişim otomatik olarak tarihçe tablosuna bir "log" olarak kaydediliyor.

### 2. Backend (Python & Flask) Geliştirmeleri
- **Geçmiş API'si:** `GET /relationships/<user1_id>/<user2_id>/history` endpoint'i yazıldı. Bu servis, iki kullanıcı arasındaki tüm skor değişimlerini kronolojik sırada döndürüyor.
- **Dinamik Duygu Analizi Entegrasyonu:** `app.py` içindeki WebSocket (`send_message`) ve REST API (`/messages`) kısımları güncellendi. Artık kullanıcı normal bir mesaj attığında:
    1. Arka planda yerel (local) **Sentiment Analysis (ML)** modeli çalışıyor.
    2. Pozitif mesajlar skoru **+5** artırıyor, negatifler **-5** azaltıyor.
    3. Bu değişim anlık olarak tarihçeye işleniyor.

### 3. Frontend (Flutter) ve Görselleştirme
- **Paket Entegrasyonu:** Projeye `fl_chart` kütüphanesi eklendi.
- **Yeni Ekran:** `relationship_dashboard_screen.dart` oluşturuldu. 
    - **Tasarım:** Modern Turquoise & Blue gradient kart yapısı.
    - **Grafik:** Zaman eksenli (X-axis) ve skor eksenli (Y-axis) kavisli (curved) çizgi grafiği.
- **Navigasyon:** Birebir sohbet ekranında (ChatScreen) üst kısımdaki profil alanına tıklama özelliği eklendi; böylece kullanıcı doğrudan bu analitik sayfasına yönlendiriliyor.

---

## 🚀 Öne Çıkan Mühendislik Detayı
Bu özellik, projenizin klasöründe yer alan **yerel Makine Öğrenmesi modelinizle (`predict_sentiment`)** tam entegre çalışmaktadır. Dış bir servise ihtiyaç duymadan, her mesaj yerel olarak analiz edilip grafiklere yansıtılmaktadır.

---
**Durum:** ✅ Tamamlandı ve Test Edildi.
**Oluşturulma Tarihi:** 14 Nisan 2026
