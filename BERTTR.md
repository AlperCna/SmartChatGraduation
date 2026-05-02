# BERTurk Modeli Entegrasyonu Tamamlandı!

SmartChat projesine "Hugging Face Transformers" tabanlı Türkçe BERT modeli entegre edildi. Mevcut çalışan sistemi ve Logistic Regression (TF-IDF) modelinizi bozmadan, test yapabileceğiniz opsiyonel (Toggle) bir yapı oluşturuldu.

## Neler Yapıldı?

1. **Jupyter Defteri Oluşturuldu**: Root dizinine [Sentiment_Model_BERT.ipynb](file:///c:/Users/Alper/PycharmProjects/SmartChatGraduation/Sentiment_Model_BERT.ipynb) adında yeni bir defter oluşturuldu. Bu defter hem `train.csv` hem de `test.csv` dosyanızı kullanarak **Google Colab** üzerinde kolayca test yapmanızı ve modeli veri setinizle eğitmenizi (Fine-Tune) sağlar.
2. **Kütüphaneler Eklendi**: `requirements.txt` dosyanızın sonuna `transformers` ve `torch` kütüphaneleri eklendi. (Docker imajınızı daha sonra yeniden inşa etmeniz gerekecek: `docker-compose up --build`)
3. **Toggle (Anahtar) Eklendi**: `.env` dosyasına `USE_BERT_SENTIMENT=False` satırı eklendi. Bu satır `False` olduğunda sisteminiz eskisi gibi hızlıca açılır ve `sentiment_model.pkl` dosyanızı okur. Eğer bunu `True` yapıp backend'i başlatırsanız;
4. **Yapay Zeka Modülü Güncellendi**: `ai_module/ml_model.py` güncellendi. Eğer `.env` dosyasını `USE_BERT_SENTIMENT=True` yaparsanız, kod arka planda en iyi BERTurk modeli olan `savasy/bert-base-turkish-sentiment-cased` modelini internetten indirir veya Colab'da eğittiğiniz modeli okur.

> [!WARNING]  
> BERT modeli çok ağırdır (yaklaşık 400 MB RAM kullanır) ve CPU üzerinde tahminde bulunması TF-IDF'ye göre 10-20 kat daha yavaş çalışır. Ancak kelimelerin arasındaki anlamları (context) anlama konusunda TF-IDF'i ezip geçer!

## Nasıl Test Edeceksiniz?

**Modeli Eğitmek / Test Etmek İçin:**
1. Bilgisayarınızın kaynak durumuna göre lokal olarak Jupyter'da veya [Google Colab](https://colab.research.google.com)'da `Sentiment_Model_BERT.ipynb`, `train.csv` ve `test.csv` dosyalarını kullanarak defteri çalıştırabilirsiniz.
2. Oradaki tüm blokları sorunsuz bitirdiğinizde Hugging Face modeliniz kaydedilmiş olacaktır.

**Backend'de Canlı Olarak Denemek İçin:**
1. Öncesinde projenize eklenen yeni kütüphaneleri kurmalısınız:
   ```bash
   pip install transformers torch
   ```
2. `.env` dosyanızdaki ayarı açın:
   ```env
   USE_BERT_SENTIMENT=True
   ```
3. Backend uygulamanızı çalıştırın. Konsolunuzda modelin indirme yüzdelerini (`>>> LOADING BERT SENTIMENT MODEL...`) ve tahmin sonuçlarını (`>>> PREDICTING SENTIMENT WITH BERT`) göreceksiniz.

Eğer Colab'da eğittiğiniz "kendi BERT modelinizi" bağlamak isterseniz, indirdiğiniz klasörü projenin içine koyup, `ml_model.py` dosyasında yazdığım `pipeline(..., model="savasy/...")` kısmındaki yol adını oluşturduğunuz `smartchat_berturk_duygu/` klasör yoluna ayarlamanız yeterlidir.
