# Duygu Durum Tahmini (Mood Forecasting) Entegrasyon Raporu

SmartChat projesinin "Akıllı Asistan" yeteneklerini geliştirmek amacıyla, kullanıcıların geçmiş etkileşimlerine bakarak karşı tarafın ruh halini tahmin eden proaktif bir özellik entegre edildi.

## Neler Yapıldı?

1. **Özelleştirilmiş Veritabanı Sorgusu (`db_service.py`)**: 
   Sohbete giren kullanıcının, konuştuğu kişinin ruh halini anlayabilmesi için, veritabanından yalnızca karşı tarafın gönderdiği son mesajları getiren yeni bir fonksiyon (`get_recent_messages_from_user`) yazıldı.

2. **Backend API Endpoint Eklendi (`app.py`)**: 
   `/mood_forecast/<sender_id>/<receiver_id>` adında, `GET` isteğiyle çalışan yeni bir uç nokta oluşturuldu. Bu sistem, yukarıdaki veritabanı fonksiyonunu çağırarak son 3 mesajı alır.

3. **Türkçe NLP (Doğal Dil İşleme) Optimizasyonu**:
   İlk etapta mesajların duygu analizi için İngilizce tabanlı `vaderSentiment` kütüphanesi kullanıldı. Ancak "Nefret ediyorum" gibi Türkçe kelimelerin 0.0 (Nötr) puan almasına sebep olan bu dil bariyeri tespit edilerek sistem hemen güncellendi.
   Analiz işlemi, projenin mevcut kütüphanesindeki **Türkçe destekli `predict_sentiment` (TF-IDF veya BERT)** metoduna entegre edildi. Böylece agresif Türkçe kelimeler eksiksiz şekilde "Negative" olarak algılanmaya başlandı.

4. **Flutter Mobil Uygulama (Önyüz) Arayüzü**:
   - `api_service.dart` içerisine `getMoodForecast` servisi eklendi.
   - `chat_screen.dart` açıldığında bu servis otomatik olarak çağrılarak karşı tarafın o anki ruh hali öğreniliyor.
   - Eğer karşı taraf gerginse ekranın en üstünde **Turuncu** bir arka planla uyarı ikonlu _"Bugün biraz gergin görünüyor, daha dikkatli yazmak ister misin?"_ bilgi bandı (banner) beliriyor.
   - Karşı tarafın ruh hali pozitifse **Yeşil** renkli bir bilgi bandı gösteriliyor.
   - Banner ekranı daraltmadan yerleşiyor ve üzerindeki "X" ikonuna tıklanarak kapatılabiliyor.

> [!TIP]
> Testlerin daha kolay yapılabilmesi için algoritma geçici olarak **oldukça hassas** ayarlandı. Yani son 3 mesajdan **sadece 1 tanesinin bile** negatif olması, turuncu uyarıyı anında tetikler.

## Nasıl Test Edeceksiniz?

**Manuel Doğrulama Adımları:**
1. Flutter uygulamasında `Hot Restart` yapın.
2. Backend uygulamasını (`app.py`) terminalden yeniden başlatın.
3. İki farklı hesaptan (A ve B kişisi) giriş yapın.
4. **A kişisi**, B kişisine arka arkaya olumsuz/agresif kelimeler barındıran ("Sinir bozucu", "Nefret ediyorum", "Berbat") 3 mesaj göndersin.
5. **B kişisi**, A kişisi ile olan sohbet ekranına tıklayıp girdiğinde sayfanın en üstünde turuncu "Gergin" uyarı banner'ını görecektir!
6. Aynı işlemi olumlu mesajlar ("Harikasın", "Çok mutluyum") ile yaparak yeşil banner'ı da test edebilirsiniz.
