# 2 Boyutlu İlişki Matrisi (Samimiyet ve Nezaket)

**Asıl Probleminiz Neydi?**
Eskiden sisteminizde tek boyutlu bir "Yakınlık Skoru (Closeness)" vardı. İki kişi birbirine sadece nazik konuştuğu (örneğin "Teşekkür ederim" yazdığı için) sistem onları otomatik olarak "yakın/kanka" zannediyordu ve bu da gerçek dünya kurallarına aykırıydı. Çünkü tanımadığımız insanlara da nazik konuşabiliriz, bu onlarla samimi olduğumuz anlamına gelmez.

**1. Yeni Bir Metrik Ekledik: Nezaket (Politeness)**
Veritabanınızdaki ilişki tablomuza `politeness_score` adında yepyeni bir sütun ekledik. Böylece artık sistem insanları iki boyutlu analiz ediyor:

- **Samimiyet (Closeness Skoru 0 - 100):** 
  Sadece "ne kadar sık ve ne kadar çok konuştuklarına" (Mesajlaşma hacmine) bakarak artıyor. Her **10 karşılıklı mesajda** skor 1 puan yükseliyor (Örn: 500 mesaja ulaşanların skoru 50 puan bandını geçer). Hiç mesajlaşmamış kişilerin samimiyeti 0'da başlar.

- **Nezaket (Politeness Skoru 0 - 100):** 
  Gönderilen mesajın "duygu durumuna (sentiment)" göre artıp azalıyor. Negatif veya agresif bir iletişim varsa Nezaket skoru -5 azalıyor, pozitif/iyi niyetli bir dil varsa +5 puan ekleniyor (Varsayılan başlangıç 50 puandır).

**2. Yeni "İlişki Matrisi" Oluşturduk**
Bu iki oranı (Nezaket ve Samimiyet) birbiriyle çarpıştırarak 4 farklı karakter/stil yapısı kurduk. Her stil 50 puan barajına göre keskin olarak belirlenir:

- **Formal (Resmi):** 
  `Samimiyet ≤ 50 | Nezaket > 50`
  Çok az mesajlaşmışlar ama çok nazikler. (Örn: Yeni tanışanlar, iş arkadaşları).
- **Respectful-Close (Saygılı/Candan):** 
  `Samimiyet > 50 | Nezaket > 50`
  Hem çok nazikler hem de aralarında çok fazla mesaj dönmüş. (Örn: Hoca-öğrenci, veya saygısını yitirmeyen uzun süreli ilişkiler).
- **Informal (Samimi/Kanka):** 
  `Samimiyet > 50 | Nezaket ≤ 50`
  Mesajlaşma hacmi çok yüksek (en az 500 mesaj dönmüş) ama kelimeler pek nazik değil. Zaten iki kanka birbiriyle konuşurken nezaket kurallarını gözetmez, küfür/argo veya lakayt şakalaşma döner.
- **Cold (Soğuk/Mesafeli):** 
  `Samimiyet ≤ 50 | Nezaket ≤ 50`
  Hem az konuşmuşlar hem de kelimeler agresif/kaba. Çatışmalı, gergin veya soğuk bir ilk iletişim var.

**3. Yapay Zekayı (GPT-4) Bu Matrise Uyarladık**
Kullanıcılarınız karşı taraftan bir mesaj aldığında ve klavyeden otomatik yanıtlama (Smart Reply / Complete) istediğinde, GPT'ye gönderilen "Prompt" metnini tüm sisteme uyan bu 2D Matrise entegre ettik. 

Artık GPT'ye sadece "şu mesaja cevap ver" demiyoruz. Şunu diyoruz:
> *"Görev: İki kullanıcının Samimiyet derecesi X, Nezaket derecesi Y. İki kullanıcı arasındaki hesaplanan İlişki Tarzı (Matris): 'Cold (Soğuk/Mesafeli)'. Bu mesaja soğuk/mesafeli ilişki yapısını koruyarak çok kısa bir yapay zeka önerisi oluştur."*

**Sonuç ve Akademik Kazanım:**
Bu yapı sayesinde kullanıcılar artık sadece yapay ve "neşeli" kelimeler seçtiği için yakın arkadaş olmuyor, sadece efor sarf edip bolca iletişim kurduklarında "samimi" sınıfına yükseliyorlar. Otomatik mesaj önerileri ve analitik verileri artık kullanıcıların *gerçek sosyolojik etkileşim ve insan doğası dinamiklerini* kusursuz şekilde matematiksel bir matrise dökerek taklit edebilecek vizyona ulaştı!