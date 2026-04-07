# 🚀 SmartChat: Bitirme Projesi 2 Vizyon Belgesi ve Yol Haritası (Genişletilmiş Sürüm)

Birinci dönemin (Bitirme 1) amacı altyapıyı oturtmaktı. **Bitirme Projesi 2** de ise projeye *yenilikçi, akademik ağırlıklı ve startup prototipi sayılabilecek "Wow Faktörü" yüksek* özellikler katmamız gerekiyor.

İşte projeyi zirveye taşıyacak, jüriyi etkileyecek **10 Güçlü Fikir**:

---

## 🏗️ 1. Temel Modernizasyon: Gerçek Zamanlı İletişim (WebSockets) ⚡
**Yapılacak:** Python backend'e `Flask-SocketIO`, Flutter'a ise WebSocket entegre etmek. 
**Jüri Değeri:** Mesajların yenileme yapmadan anında düşmesi ve *"Yazıyor..."* (Typing) ibarelerinin eklenmesi bir sohbet uygulamasının olmazsa olmaz mühendislik kuralıdır.

## 📊 2. İlişki Dinamiği Analiz Paneli (Relationship Dashboard)
**Yapılacak:** Flutter'da kişinin profiline tıklandığında "Samimiyet Skoru (Closeness)"nun aylar içindeki grafiğini (Line Chart) çıkarma.
**Jüri Değeri:** Eldeki saklı verinin **Veri Görselleştirme (Data Visualization)** ile kullanıcıya sunulması akademik puanı çok yüksek olan bir detaydır.

## 🤖 3. Akıllı Yanıt Çekmecesi (Smart Auto-Reply)
**Yapılacak:** Yapay zeka, gelen son mesaja ve aradaki '*closeness*' stiline uygun **3 farklı anında yanıt butonu** (örn. "Eyvallah kanka", "Teşekkür ederim", "Çok sağ ol canım") üretecek.
**Jüri Değeri:** Modern NLP (Natural Language Processing) yeteneklerinin son kullanıcı deneyimine (UX) müthiş bir yansıması.

## 🎙️ 4. Sesli Mesajların AI ile "Yumuşatılması" (Speech-Style Transfer)
**Yapılacak:** Sese basılı tutularak ses kaydedilecek. Backend bu sesi metne dönüştürecek (Whisper API), kaba veya uygunsuz sözleri o anki *style_adapter*'a göre düzeltecek ve karşıya formalize edilmiş metni (veya yeni TTS sesi) yollayacak.
**Jüri Değeri:** Sadece metin değil, ses analizinin de projeye dahil olması (*Multimodal AI*) jüriyi hayran bırakır.

## 🛡️ 5. Siber Zorbalık ve Öfke Kalkanı (Toxicity & Harassment Shield)
**Yapılacak:** Duygu (Sentiment) modelini bir adım öteye taşıyıp kaba/saldırgan mesajı tespit etmek. Kötü bir mesaj geldiğinde Flutter ekranında **flu (blurlu) veya sansürlü** görünecek, kişi "Yine de gör" tuşuna basarsa açılacak. Ayrıca bu olay *"Closeness Score"*u anında dibe çekecek.
**Jüri Değeri:** Günümüzün popüler "dijital refah (digital wellbeing)" konularına değindiği için çok sosyal ve değerli bir eklenti.

## 📝 6. Yapay Zeka ile Okunmayan Mesajları Özetleme (TL;DR Catch-up)
**Yapılacak:** Kişi gruba veya kişiye uzun süre bakmadığında okunmamış 20-30 mesaj varsa, tepede "**Özetle**" butonu çıkacak. Yapay zeka: *"Efe genelde olumlu konuştu, saat 8'de nerede buluşacağınızı soruyor"* gibi akıllı özet çıkaracak.
**Jüri Değeri:** LLM’in (Large Language Model) en başarılı olduğu "Metin Özetleme" kabiliyetinin fonksiyonel kullanımı!

## 🌍 7. Samimiyet Korumalı Canlı Çeviri (Style-Aware Translation)
**Yapılacak:** Kişiler farklı dillerde yazışsa bile "O anki üsluba" göre çeviri yapılacak. Örneğin samimi bir Fransızca mesaj, Türkçeye Google Çeviri gibi resmi bir dille değil; *"Naber abi?"* gibi argolu/samimi çevrilecek. 
**Jüri Değeri:** Makine çevirisi (Machine Translation) üzerine büyük bir vizyon atılımı. Sadece çeviri değil, "Karakterli Çeviri".

## ⏳ 8. Duygu Odaklı Mesaj Erteleme (Mood-Aware Cooldown)
**Yapılacak:** Göndericinin mesajı aşırı negatif/öfkeli ("negative" sentiment) çıktığında telefon titreyecek ve *"Şu an öfkeli görünüyorsunuz. Bu mesaj aranızdaki samimiyet skorunu düşürecek. Yine de göndermek istiyor musunuz?"* uyarısı çıkararak 5 saniyelik bir geri sayım yapacak.
**Jüri Değeri:** İnsan psikolojisini koruyan önleyici yapay zeka özelliği.

## 🧑‍🤝‍🧑 9. Grup Sohbetlerinde "Grup Atmosferi" Analizi
**Yapılacak:** Closeness sadece 1v1 kişilere özeldi. "Grup Sohbeti" ekleyerek, gruptaki herkesin ortak duygusuna (Sentiment) göre "**Grubun o anki Havası/Gerginliği**" (Tense, Happy, Formal) tepede ikonlarla (🔥, ❄️, 😊) gösterilecek.
**Jüri Değeri:** Sosyal ağ analizi ve multi-user dinamiği katılmış olacak.

## ⚙️ 10. Mühendislik ve Performans Kurumsallaştırması
**Yapılacak:** Arkaplandaki 20 saniyelik ML modeli yüklenme donmasını engellemek için **Pre-loading** yazılacak. Mimari **Docker container**'i içine alınıp, sunumda "hocam tek tuşla her cihazda ayağa kalkıyor" denebilecek seviyeye getirilecek. Veritabanına *Connection Pool* entegre edilecek.

---
**Öneri:** Bu 10 fikrin tamamını yapmak yüksek zaman alır, ancak aralarından en göze batan ve sana en cazip gelen **3-4 tanesini seçip (örneğin 1, 3, 5 ve 10)** onlara odaklanırsak mükemmel bir Bitirme 2 projesi çıkartırız!
