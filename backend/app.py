import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import Flask, jsonify, request, send_from_directory, redirect
from backend.services import db_service
from flask_cors import CORS
import bcrypt
import os
import secrets
import urllib.parse
import requests
from werkzeug.utils import secure_filename
from ai_module.punctuation_fixer import suggest_punctuation
from ai_module.style_adapter import detect_style, adapt_style
from openai import OpenAI
from dotenv import load_dotenv
import os
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
analyzer = SentimentIntensityAnalyzer()
from ai_module.ml_model import predict_sentiment, predict_style, load_sentiment_model, load_style_model
import threading
from datetime import datetime


load_dotenv(override=True)
print("API Key test:", os.getenv("OPENAI_API_KEY")[:6], "...")  # sadece ilk 6 karakter

# ── SSO CONFIG ──────────────────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:9000/auth/google/callback")

MICROSOFT_CLIENT_ID     = os.getenv("MICROSOFT_CLIENT_ID")
MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET")
MICROSOFT_REDIRECT_URI  = os.getenv("MICROSOFT_REDIRECT_URI", "http://localhost:9000/auth/microsoft/callback")

_oauth_states: set = set()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _build_style_instructions(closeness: int, politeness: int) -> str:
    rules = []
    if closeness >= 75:
        rules += [
            "- Hitap: 'sen' kullan, 'siz' KULLANMA",
            "- 'ya', 'kanka', 'abi/abla', 'be' gibi samimi ekler kullanabilirsin",
            "- Cümleler kısa ve doğal olsun, gereksiz resmiyet ekleme",
        ]
    elif closeness >= 40:
        rules += [
            "- Hitap: 'sen' kullan",
            "- Samimi ama saygılı bir ton",
            "- Argo kelimeler kullanma",
        ]
    else:
        rules += [
            "- Hitap: 'siz' kullan",
            "- Resmi ve mesafeli bir dil kullan",
            "- Kısa ve öz ol",
        ]

    if politeness >= 75:
        rules += [
            "- Kibar ifadeler kullan, teşekkür veya nezaket vurgusunu koru",
            "- Sert veya doğrudan eleştiri içeren ifadeler KULLANMA",
        ]
    elif politeness <= 30:
        rules += [
            "- Gereksiz nezaket kalıpları (teşekkürler, rica ederim vb.) EKLEME",
            "- Doğrudan ve sade bir dil kullan",
        ]

    return "\n".join(rules)


def _build_style_example(closeness: int) -> str:
    if closeness >= 75:
        return '"toplantıya katılabilir misiniz?" → "ya toplantıda mısın"'
    elif closeness >= 40:
        return '"ne zaman gelcen" → "Ne zaman gelebilirsin?"'
    else:
        return '"yarın görüşelim" → "Yarın görüşebilir miyiz?"'
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

#  Medya dosyalarının kaydedileceği klasör
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "..", "docs")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -------------------------------------------------------------------
# ML MODELLERİNİ ÖN BELLEĞE YÜKLE (PRE-LOADING)
# -------------------------------------------------------------------
print(">> Başlatılıyor: ML Modelleri RAM'e yükleniyor (Pre-loading)...")
try:
    load_sentiment_model()
    load_style_model()
    print(">> BAŞARILI: ML Modelleri kullanıma hazır!")
except Exception as e:
    print(f">> HATA: ML Modelleri yüklenemedi: {e}")
# -------------------------------------------------------------------

@app.route("/hello", methods=["GET"])
def hello():
    return {"message": "SmartChat Flask sunucusu çalışıyor."}

@app.route('/docs/<path:filename>')
def serve_docs(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/users", methods=["GET"])
def list_users():
    return jsonify(db_service.get_users())

@app.route("/users", methods=["POST"])
def create_user():
    data = request.get_json()
    username = data.get("username")
    email = data.get("email")
    password_hash = data.get("password_hash")
    if not username or not email or not password_hash:
        return jsonify({"error": "username, email ve password_hash zorunludur."}), 400
    db_service.insert_user(username, email, password_hash)
    return jsonify({"message": "Kullanıcı başarıyla eklendi."})

@app.route("/messages", methods=["POST"])
def send_message():
    data = request.get_json()
    sender_id = data.get("sender_id")
    receiver_id = data.get("receiver_id")
    group_id = data.get("group_id")
    content = data.get("content")
    if not sender_id or not content:
        return jsonify({"error": "sender_id and content are required."}), 400
    if not receiver_id and not group_id:
        return jsonify({"error": "either receiver_id or group_id is required."}), 400

    message_id = db_service.insert_message(sender_id, receiver_id, content, group_id)

    if not group_id:
        sentiment_res = predict_sentiment(content)
        sentiment = sentiment_res.get("sentiment", "neutral")
        db_service.update_relationship_metrics(sender_id, receiver_id, sentiment)

    return jsonify({
        "message": "Mesaj başarıyla gönderildi.",
        "message_id": message_id
    }), 200


@app.route("/messages", methods=["GET"])
def list_messages():
    sender_id = request.args.get("sender_id")
    receiver_id = request.args.get("receiver_id")
    group_id = request.args.get("group_id")
    
    if group_id:
        messages = db_service.get_messages(sender_id=None, receiver_id=None, group_id=group_id)
    else:
        if not sender_id or not receiver_id:
            return jsonify({"error": "sender_id and receiver_id zorunludur (if not group_id)."}), 400
        messages = db_service.get_messages(sender_id, receiver_id)
        
    return jsonify({"messages": messages})
@app.route("/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json()
        username = data.get("username", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "")
        if not username or not email or not password:
            return jsonify({"error": "All fields are required"}), 400
        if db_service.get_user_by_email(email):
            return jsonify({"error": "Email is already registered"}), 409
        if db_service.get_user_by_username(username):
            return jsonify({"error": "Username is already taken"}), 409
        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        db_service.insert_user(username, email, hashed_pw)
        return jsonify({"success": True, "message": "User created successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        identifier = data.get("email", "").strip()
        password = data.get("password", "")
        
        user = db_service.get_user_by_email(identifier)
        if not user:
            user = db_service.get_user_by_username(identifier)
            
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 401
        stored_pw = user.get("password_hash")
        if not stored_pw:
            sso = user.get("sso_provider")
            if sso:
                return jsonify({"success": False, "error": f"Bu hesap {sso.capitalize()} ile kayıtlıdır. Lütfen SSO ile giriş yapınız."}), 401
            return jsonify({"success": False, "error": "Invalid password hash format"}), 500
        if not stored_pw.startswith("$2"):
            return jsonify({"success": False, "error": "Invalid password hash format"}), 500
        if not bcrypt.checkpw(password.encode("utf-8"), stored_pw.encode("utf-8")):
            return jsonify({"success": False, "error": "Invalid password"}), 401
        return jsonify({"success": True, "user_id": user["user_id"]}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/user_by_username/<username>", methods=["GET"])
def get_user_by_username_route(username):
    user = db_service.get_user_by_username(username)
    if user:
        return jsonify({
            "success": True,
            "user": {
                "id": user["user_id"],
                "username": user["username"],
                "email": user["email"]
            }
        }), 200

    return jsonify({
        "success": False,
        "error": "User not found"
    }), 404


@app.route("/user_by_id/<int:user_id>", methods=["GET"])
def get_user_by_id(user_id):
    user = db_service.get_user_by_id(user_id)
    if user:
        return jsonify(user)
    return jsonify({"error": "User not found"}), 404

@app.route("/chat_partners/<int:user_id>", methods=["GET"])
def chat_partners(user_id):
    return jsonify(db_service.get_chat_partners(user_id))

@app.route("/relationships/<int:user1_id>/<int:user2_id>/history", methods=["GET"])
def get_relationship_history_route(user1_id, user2_id):
    history = db_service.get_relationship_history(user1_id, user2_id)
    relationship = db_service.get_relationship(user1_id, user2_id)
    current_score     = relationship["closeness_score"]  if relationship else 50
    current_politeness= relationship["politeness_score"] if relationship else 50
    current_style     = relationship.get("style", "Formal (Resmi)") if relationship else "Formal (Resmi)"
    return jsonify({
        "success":           True,
        "current_score":     current_score,
        "current_politeness":current_politeness,
        "current_style":     current_style,
        "history":           history
    })

@app.route("/mood_forecast/<int:sender_id>/<int:receiver_id>", methods=["GET"])
def get_mood_forecast(sender_id, receiver_id):
    """
    Zaman ağırlıklı sentiment ortalaması + saatlik pattern + mesajlaşma sıklığı
    birleştirilerek karşı tarafın ruh hali tahmin edilir.

    Yanıt alanları:
      mood        : "positive" | "neutral" | "negative" | "mixed"
      score       : -1.0 … +1.0  (ağırlıklı duygu skoru)
      trend       : "rising" | "falling" | "stable"
      warning     : kullanıcıya gösterilecek kısa uyarı/öneri metni
      tip         : iletişim tüyosu
      data_points : kaç mesaj analiz edildi
    """
    import math

    messages = db_service.get_messages_for_mood_forecast(receiver_id, sender_id, limit=30)
    if not messages:
        return jsonify({"mood": "neutral", "score": 0.0, "trend": "stable",
                        "warning": "", "tip": "", "data_points": 0})

    # ── 1. ZAMAN AĞIRLIKLI SENTİMENT ───────────────────────────────
    # Üstel bozunma: λ = 0.08 → 24 saat önceki mesaj ~%15 ağırlık alır
    LAMBDA = 0.08
    now = datetime.utcnow()

    sentiment_map = {"Positive": 1.0, "Negative": -1.0, "Notr": 0.0}
    weighted_scores = []
    weights = []
    raw_sentiments = []

    for msg in messages:
        text = msg.get("content", "")
        if not text:
            continue
        ts_raw = msg.get("timestamp", "")
        try:
            ts = datetime.strptime(str(ts_raw)[:19], "%Y-%m-%d %H:%M:%S")
            age_hours = max(0, (now - ts).total_seconds() / 3600)
        except Exception:
            age_hours = 12

        result = predict_sentiment(text)
        sent = result.get("sentiment", "Notr")
        conf = result.get("confidence", 0.5)
        raw_sentiments.append(sent)

        score = sentiment_map.get(sent, 0.0) * conf
        weight = math.exp(-LAMBDA * age_hours)
        weighted_scores.append(score * weight)
        weights.append(weight)

    if not weights:
        return jsonify({"mood": "neutral", "score": 0.0, "trend": "stable",
                        "warning": "", "tip": "", "data_points": 0})

    weighted_avg = sum(weighted_scores) / sum(weights)

    # ── 2. TREND: İLK YARI vs İKİNCİ YARI ─────────────────────────
    # messages listesi DESC sıralı → ilk yarı = en yeni
    mid = max(1, len(raw_sentiments) // 2)
    score_recent = sum(sentiment_map.get(s, 0) for s in raw_sentiments[:mid]) / mid
    score_older  = sum(sentiment_map.get(s, 0) for s in raw_sentiments[mid:]) / max(1, len(raw_sentiments) - mid)
    delta = score_recent - score_older
    if delta > 0.15:
        trend = "rising"
    elif delta < -0.15:
        trend = "falling"
    else:
        trend = "stable"

    # ── 3. SAATLIK PATTERN ─────────────────────────────────────────
    current_hour = datetime.utcnow().hour
    night_hours = set(range(22, 24)) | set(range(0, 6))
    is_night = current_hour in night_hours

    hourly_data = db_service.get_hourly_sentiment_pattern(receiver_id, sender_id)
    night_msgs = sum(r["msg_count"] for r in hourly_data if r["hour"] in night_hours)
    total_msgs  = sum(r["msg_count"] for r in hourly_data) or 1
    night_ratio = night_msgs / total_msgs   # Bu kişi gece mi daha çok yazıyor?

    # ── 4. MESAJLAŞMA SIKLIĞI ──────────────────────────────────────
    freq_data = db_service.get_message_frequency(receiver_id, sender_id)
    if len(freq_data) >= 2:
        today_count     = freq_data[0]["msg_count"] if freq_data else 0
        avg_older_count = sum(r["msg_count"] for r in freq_data[1:]) / (len(freq_data) - 1)
        freq_drop = avg_older_count > 0 and (today_count / avg_older_count) < 0.4
    else:
        freq_drop = False

    # ── 5. MOOD KARAR MANTIGI ──────────────────────────────────────
    if weighted_avg <= -0.35:
        mood = "negative"
    elif weighted_avg >= 0.35:
        mood = "positive"
    elif -0.35 < weighted_avg < -0.1:
        mood = "mixed"
    else:
        mood = "neutral"

    # ── 6. UYARI & TÜYOgenerasyon ─────────────────────────────────
    warning = ""
    tip = ""

    if mood == "negative":
        if trend == "falling":
            warning = "Son mesajlarda giderek daha gergin bir ton var. Belki bugün konuyu hafif tutmak iyi olabilir."
        else:
            warning = "Biraz gergin görünüyor. Mesajını göndermeden önce bir kez daha oku."
        if is_night and night_ratio > 0.5:
            tip = "Gece saatlerinde mesajlaşmayı tercih ediyor; hassas konular için gündüz daha uygun olabilir."
        else:
            tip = "Empati gösteren kısa bir cümle konuşmayı yumuşatabilir."

    elif mood == "positive":
        if trend == "rising":
            warning = "Giderek daha iyi bir ruh halinde! Harika bir sohbet için iyi bir an."
        else:
            warning = "Bugün iyi bir ruh halinde görünüyor."
        tip = "Olumlu havayı korumak için samimi ve sıcak bir ton sürdür."

    elif mood == "mixed":
        warning = "Duyguları karışık görünüyor — hem olumlu hem olumsuz mesajlar var."
        tip = "Dikkatli ve anlayışlı bir yaklaşım benimsemek faydalı olabilir."

    else:
        warning = ""
        tip = "Nötr bir ruh halinde; rahat ve doğal bir sohbet yapabilirsin."

    if freq_drop:
        warning += " Bugün normalden çok daha az mesaj attı — belki yoğun ya da yorgun olabilir."

    return jsonify({
        "mood":        mood,
        "score":       round(weighted_avg, 3),
        "trend":       trend,
        "warning":     warning.strip(),
        "tip":         tip,
        "data_points": len(weights),
        "night_writer": night_ratio > 0.5,
        "freq_drop":    freq_drop,
    })

# 📤 Yeni: Fotoğraf/ses/video medya dosyası yükleme
@app.route("/upload_media", methods=["POST"])
def upload_media():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    media_type = request.form.get("media_type", "image")
    sender_id = request.form.get("sender_id")
    receiver_id = request.form.get("receiver_id")
    group_id = request.form.get("group_id")

    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if not sender_id:
        return jsonify({"error": "sender_id is required"}), 400
    if not receiver_id and not group_id:
        return jsonify({"error": "either receiver_id or group_id is required"}), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)

    # Auto-create a placeholder message for this media
    message_id = db_service.insert_message(
        sender_id=int(sender_id),
        receiver_id=int(receiver_id) if receiver_id else None,
        content="[Media]",
        group_id=int(group_id) if group_id != "null" and group_id else None
    )

    # Link the media record to the newly created message
    db_service.insert_media(message_id, media_type, f"docs/{filename}")

    return jsonify({
        "message": "Media uploaded",
        "file_path": f"docs/{filename}",
        "message_id": message_id
    })



@app.route("/complete", methods=["POST"])
def complete_text():
    try:
        data = request.get_json()

        text = data.get("text", "").strip()
        sender_id = data.get("sender_id")
        receiver_id = data.get("receiver_id")
        receiver_username = data.get("receiver_username", "Other")

        if not text or sender_id is None or receiver_id is None:
            return jsonify({
                "error": "text, sender_id, receiver_id are required"
            }), 400

        # --------------------------------------------------
        # 1️⃣ SON 5 MESAJI AL (KONUŞMA CONTEXT)
        # --------------------------------------------------
        messages = db_service.get_messages(sender_id, receiver_id)
        last_msgs = messages[-5:]

        history = ""
        for m in last_msgs:
            speaker = "Me" if m["sender_id"] == sender_id else receiver_username
            history += f"{speaker}: {m['content']}\n"

        # --------------------------------------------------
        # 2️⃣ STYLE DETECTION (HIBRIT – GPT + RELATIONSHIP)
        # --------------------------------------------------
        style_res = detect_style(
            sender_id=sender_id,
            receiver_id=receiver_id,
            last_message=text
        )

        message_style = style_res["message_style"]
        relationship_style = style_res["relationship_style"]

        # --------------------------------------------------
        # 3️⃣ SENTIMENT DETECTION (ML)
        # --------------------------------------------------
        sentiment_res = predict_sentiment(text)
        sentiment = sentiment_res["sentiment"]
        sentiment_confidence = sentiment_res["confidence"]

        # --------------------------------------------------
        # 4️⃣ NEZAKET VE SAMİMİYET GÜNCELLEME / MATRİS HESAPLAMA
        # --------------------------------------------------
        db_service.update_relationship_metrics(sender_id, receiver_id, sentiment)

        relationship = db_service.get_relationship(sender_id, receiver_id)
        politeness = relationship.get("politeness_score", 50) if relationship else 50
        closeness = relationship.get("closeness_score", 0) if relationship else 0
        matrix_style = relationship.get("style", "Formal (Resmi)") if relationship else "Formal (Resmi)"
        
        relationship_style = matrix_style

        # --------------------------------------------------
        # 5️⃣ GPT İLE MESAJ TAMAMLAMA / ÖNERİ
        # --------------------------------------------------
        style_instructions = _build_style_instructions(closeness, politeness)
        example = _build_style_example(closeness)

        prompt = f"""Sen bir Türkçe mesaj asistanısın. Kullanıcının mesajını aşağıdaki KURALLARA kesinlikle uyarak yeniden yaz.

KURALLAR (bunları ihlal etme):
{style_instructions}

ÖRNEK ({matrix_style} için):
{example}

Konuşma Geçmişi:
{history}

Kullanıcının Mesajı: {text}

Sadece yeniden yazılmış cümleyi döndür. Açıklama ekleme."""

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=60
        )

        completion_text = response.choices[0].message.content.strip()

        # --------------------------------------------------
        # 6️⃣ ÖNERİYİ VERİTABANINA KAYDET
        # --------------------------------------------------
        suggestion_id = db_service.insert_suggestion(
            sender_id,
            original_text=text,
            suggested_text=completion_text,
            style=relationship_style
        )

        # --------------------------------------------------
        # 7️⃣ RESPONSE
        # --------------------------------------------------
        return jsonify({
            "suggestion_id": suggestion_id,
            "original": text,
            "completion": completion_text,

            # 🔥 ANALYSIS
            "message_style": message_style,
            "relationship_style": relationship_style,
            "sentiment": sentiment,
            "sentiment_confidence": sentiment_confidence,

            "timestamp": datetime.utcnow().isoformat() + "Z"
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



@app.route("/suggestions/<int:suggestion_id>", methods=["PATCH"])
def update_suggestion(suggestion_id):
    try:
        data = request.get_json()
        accepted = data.get("accepted")

        if accepted not in [True, False]:
            return jsonify({"error": "accepted alanı true/false olmalı"}), 400

        db_service.update_suggestion_acceptance(suggestion_id, accepted)
        return jsonify({"message": "Kabul durumu güncellendi"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

#Bitirme sonrası kısım

from ai_module.ml_model import predict_sentiment

@app.route("/predict_sentiment", methods=["POST"])
def predict_sentiment_route():
    data = request.get_json()
    text = data.get("text", "")

    if not text.strip():
        return jsonify({"error": "Text is required"}), 400

    result = predict_sentiment(text)
    return jsonify(result), 200


from ai_module.style_adapter import detect_style

@app.route("/predict_style", methods=["POST"])
def predict_style_route():
    data = request.get_json()
    text = data.get("text", "").strip()
    sender_id = data.get("sender_id")
    receiver_id = data.get("receiver_id")

    if not text or sender_id is None or receiver_id is None:
        return jsonify({"error": "text, sender_id, receiver_id are required"}), 400

    # ❗ DB yoksa burada exception fırlatır (istenen davranış)
    style = detect_style(sender_id, receiver_id, last_message=text)

    return jsonify({
        "style": style,
        "source": "gpt"
    }), 200


from ai_module.style_adapter import detect_style

@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.get_json()

        text = data.get("text", "").strip()
        sender_id = data.get("sender_id")
        receiver_id = data.get("receiver_id")

        if not text or sender_id is None or receiver_id is None:
            return jsonify({
                "error": "text, sender_id, receiver_id are required"
            }), 400

        # 1️⃣ SENTIMENT (ML – KALIYOR)
        sentiment_res = predict_sentiment(text)

        # 2️⃣ STYLE (GPT + DB – HİBRİT)
        style_res = detect_style(
            sender_id=sender_id,
            receiver_id=receiver_id,
            last_message=text
        )

        # 3️⃣ PUNCTUATION FIX (KALIYOR)
        fixed = suggest_punctuation(text)

        return jsonify({
            "sentiment": sentiment_res["sentiment"],
            "sentiment_confidence": sentiment_res["confidence"],

            # 🔥 ÖNEMLİ AYRIM
            "style": style_res["message_style"],
            "relationship_style": style_res["relationship_style"],

            "punctuation_fixed": fixed,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/smart_replies", methods=["POST"])
def smart_replies():
    try:
        import json
        data = request.get_json()
        sender_id = data.get("sender_id")
        receiver_id = data.get("receiver_id")
        last_message = data.get("last_message", "").strip()

        if not sender_id or not receiver_id or not last_message:
            return jsonify({"error": "sender_id, receiver_id and last_message are required"}), 400

        style_res = detect_style(sender_id, receiver_id, last_message)
        relationship_style = style_res.get("relationship_style", "Formal")

        prompt = f"""Karşı taraf şu mesajı gönderdi: "{last_message}"
Aranızdaki iletişim tarzı: '{relationship_style}'.

Tam olarak 3 farklı tonlu, KISA (2-6 kelime), doğal Türkçe yanıt üret:
- "empathetic": Anlayışlı, sıcak, duygusal destek veren
- "humorous": Hafif espirili, neşeli, samimi
- "formal": Kibar, resmi, mesafeli

Sadece aşağıdaki JSON formatında döndür, başka hiçbir şey ekleme:
[
  {{"tone": "empathetic", "text": "..."}},
  {{"tone": "humorous", "text": "..."}},
  {{"tone": "formal", "text": "..."}}
]"""

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=120
        )

        import json, re
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```[a-z]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content)

        try:
            replies = json.loads(content)
        except json.JSONDecodeError:
            replies = []

        if not isinstance(replies, list):
            replies = []

        return jsonify({"replies": replies[:3]}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ----------------------------------------------------------
# REPHRASE — "Bunu Nasıl Söylesem?"
# ----------------------------------------------------------
def _build_rephrase_context(closeness: int, politeness: int) -> str:
    """Samimilik ve nezaket skoruna göre ilişki bağlamını açıklar."""
    if closeness >= 75:
        rel = "çok yakın, samimi arkadaşlık — argo, hitap kelimeleri, kısaltmalar doğal"
    elif closeness >= 40:
        rel = "orta düzey tanışıklık — 'sen' hitabı, samimi ama saygılı"
    else:
        rel = "resmi / az tanışıklık — 'siz' hitabı, mesafeli ve kibar"

    if politeness >= 70:
        pol = "karşılıklı nezaket yüksek, kaba ifadelerden kaçın"
    elif politeness <= 30:
        pol = "nezaket skoru düşük, aşırı kibarlık kalıpları yapay kaçar"
    else:
        pol = "orta düzey nezaket"

    return f"İlişki: {rel}. Nezaket: {pol}."


@app.route("/rephrase", methods=["POST"])
def rephrase():
    try:
        import json, re
        data = request.get_json()

        text = data.get("text", "").strip()
        sender_id = data.get("sender_id")
        receiver_id = data.get("receiver_id")
        receiver_username = data.get("receiver_username", "Karşı Taraf")

        if not text or sender_id is None or receiver_id is None:
            return jsonify({"error": "text, sender_id, receiver_id are required"}), 400

        # --------------------------------------------------
        # 1️⃣ SON 5 MESAJI AL (KONUŞMA CONTEXT)
        # --------------------------------------------------
        messages = db_service.get_messages(sender_id, receiver_id)
        last_msgs = messages[-5:]

        history = ""
        for m in last_msgs:
            speaker = "Ben" if m["sender_id"] == sender_id else receiver_username
            content = m.get("content", "").strip()
            if content:
                history += f"{speaker}: {content}\n"

        # --------------------------------------------------
        # 2️⃣ STYLE DETECTION (HİBRİT – GPT + RELATIONSHIP)
        # --------------------------------------------------
        style_res = detect_style(
            sender_id=sender_id,
            receiver_id=receiver_id,
            last_message=text
        )
        message_style = style_res["message_style"]

        # --------------------------------------------------
        # 3️⃣ SENTIMENT DETECTION (ML)
        # --------------------------------------------------
        sentiment_res = predict_sentiment(text)
        sentiment = sentiment_res["sentiment"]
        sentiment_confidence = sentiment_res["confidence"]

        # --------------------------------------------------
        # 4️⃣ İLİŞKİ METRİKLERİ GÜNCELLE / MATRİS HESAPLA
        # --------------------------------------------------
        db_service.update_relationship_metrics(sender_id, receiver_id, sentiment)

        relationship = db_service.get_relationship(sender_id, receiver_id)
        closeness  = relationship.get("closeness_score",  0)  if relationship else 0
        politeness = relationship.get("politeness_score", 50) if relationship else 50
        matrix_style = relationship.get("style", "Formal (Resmi)") if relationship else "Formal (Resmi)"

        # --------------------------------------------------
        # 5️⃣ İLİŞKİ BAĞLAMINI OLUŞTUR
        # --------------------------------------------------
        rel_context = _build_rephrase_context(closeness, politeness)
        hitap = "sen" if closeness >= 40 else "siz"

        # --------------------------------------------------
        # 6️⃣ GPT İLE 3 VERSİYON ÜRET
        # --------------------------------------------------
        prompt = f"""Sen bir Türkçe mesajlaşma asistanısın. Görevin kullanıcının ham mesajını 3 farklı tonda yeniden yazmak.

MESAJ: "{text}"

BAĞLAM:
- {rel_context}
- İlişki stili: {matrix_style}
- Mesajın duygusu: {sentiment}
- Hitap şekli: "{hitap}"

KONUŞMA GEÇMİŞİ (son mesajlar):
{history if history else "(Geçmiş yok)"}

---

3 TON İÇİN KURALLAR:

"kind" — NAZİK TON:
  AMAÇ: Mesajın özünü yumuşat, karşı tarafın duygusuna alan aç.
  YAP: Empati kur, soru soruyorsan neden merak ettiğini belirt, sıcak bir kapı bırak.
  YAPMA: Sorgulamak gibi görünme, "merak ettim" gibi jenerik ekler koyma, cümleyi uzatma.
  ÖRNEK → "neden böyle yapıyorsun?" için: "Bir şey mi oldu, anlatsana?"

"direct" — DOĞRUDAN TON:
  AMAÇ: Mesajı kısa ve net söyle, dolaşma.
  YAP: Tek cümleyle, düz ve açık ifade et. Gereksiz kelime ekleme.
  YAPMA: Kibar süsler, "lütfen", "acaba" gibi yumuşatıcılar ekleme.
  ÖRNEK → "neden böyle yapıyorsun?" için: "Böyle yapmanın sebebi ne?"

"humorous" — ESPRİLİ TON:
  AMAÇ: Mesajın özünü koru ama hafif bir ironi, abartı veya kelime oyunu kat.
  YAP: Beklenmedik bir kıyaslama, abartılı bir tepki veya güldürücü bir eklenti kullan.
  YAPMA: Sadece ünlem veya emoji ekleyerek espri yapmaya çalışma, gerçekten komik bir büküm yap.
  ÖRNEK → "neden böyle yapıyorsun?" için: "Böyle giderse seni bir kullanma kılavuzuyla anlamamız gerekecek."

---

ÇIKTI KURALLARI:
- Her versiyon maksimum 1-2 cümle olsun
- Yazım hatalarını düzelt ama anlam değiştirme
- Sadece JSON döndür:
[
  {{"tone": "kind",     "text": "..."}},
  {{"tone": "direct",   "text": "..."}},
  {{"tone": "humorous", "text": "..."}}
]"""

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=220
        )

        # --------------------------------------------------
        # 7️⃣ YANITI PARSE ET
        # --------------------------------------------------
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```[a-z]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content)

        try:
            versions = json.loads(content)
        except json.JSONDecodeError:
            versions = []

        if not isinstance(versions, list):
            versions = []

        # --------------------------------------------------
        # 8️⃣ RESPONSE
        # --------------------------------------------------
        return jsonify({
            "versions": versions[:3],

            # 🔥 ANALİZ BİLGİSİ
            "original": text,
            "message_style": message_style,
            "relationship_style": matrix_style,
            "sentiment": sentiment,
            "sentiment_confidence": sentiment_confidence,
            "closeness": closeness,
            "politeness": politeness,

            "timestamp": datetime.utcnow().isoformat() + "Z"
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ----------------------------------------------------------
# CONVERSATION SUMMARY
# ----------------------------------------------------------
@app.route("/conversation_summary", methods=["POST"])
def conversation_summary():
    try:
        data = request.get_json()
        sender_id = data.get("sender_id")
        receiver_id = data.get("receiver_id")
        limit = int(data.get("limit", 50))

        if not sender_id or not receiver_id:
            return jsonify({"error": "sender_id and receiver_id are required"}), 400

        messages = db_service.get_messages(sender_id, receiver_id)
        if not messages:
            return jsonify({"error": "Özetlenecek mesaj bulunamadı."}), 404

        recent = messages[-limit:]

        sender_info = db_service.get_user_by_id(sender_id)
        receiver_info = db_service.get_user_by_id(receiver_id)
        sender_name = sender_info.get("username", "Sen") if sender_info else "Sen"
        receiver_name = receiver_info.get("username", "Karşı taraf") if receiver_info else "Karşı taraf"

        conversation_text = ""
        for m in recent:
            speaker = sender_name if m["sender_id"] == sender_id else receiver_name
            content = m.get("content", "").strip()
            if content:
                conversation_text += f"{speaker}: {content}\n"

        if not conversation_text.strip():
            return jsonify({"error": "Metin içerikli mesaj bulunamadı."}), 404

        first_ts = recent[0].get("timestamp") or recent[0].get("created_at", "")
        last_ts = recent[-1].get("timestamp") or recent[-1].get("created_at", "")

        prompt = f"""Aşağıdaki Türkçe mesajlaşma konuşmasını analiz et ve JSON formatında özetle.

Konuşma ({len(recent)} mesaj):
{conversation_text}

Şu formatta yanıt ver (başka hiçbir şey ekleme):
{{
  "summary": "2-3 cümlelik genel özet",
  "topics": ["konu1", "konu2", "konu3"],
  "mood": "genel duygu tonu (pozitif/nötr/negatif/karışık)",
  "highlight": "Konuşmadan en önemli veya dikkat çekici bir cümle (alıntı)"
}}"""

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300
        )

        import json, re
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```[a-z]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content)

        result = json.loads(content)
        result["message_count"] = len(recent)
        result["date_from"] = str(first_ts)[:10] if first_ts else ""
        result["date_to"] = str(last_ts)[:10] if last_ts else ""

        return jsonify(result), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ----------------------------------------------------------
# SUGGESTION ANALYTICS
# ----------------------------------------------------------
@app.route("/suggestion_analytics/<int:user_id>", methods=["GET"])
def suggestion_analytics(user_id):
    try:
        data = db_service.get_suggestion_analytics(user_id)
        summary = data["summary"]
        by_style = data["by_style"]

        total = int(summary["total"] or 0)
        accepted = int(summary["accepted_count"] or 0)
        rejected = int(summary["rejected_count"] or 0)
        pending = int(summary["pending_count"] or 0)
        decided = accepted + rejected
        acceptance_rate = round(accepted / decided * 100, 1) if decided > 0 else None

        style_breakdown = []
        for row in by_style:
            row_total = int(row["total"] or 0)
            row_accepted = int(row["accepted"] or 0)
            row_rejected = int(row["rejected"] or 0)
            rate = round(row_accepted / (row_accepted + row_rejected) * 100, 1) if (row_accepted + row_rejected) > 0 else 0
            style_breakdown.append({
                "style":         row["style"],
                "total":         row_total,
                "accepted":      row_accepted,
                "rejected":      row_rejected,
                "acceptance_rate": rate,
            })

        # En çok kabul edilen stil
        best_style = max(style_breakdown, key=lambda x: x["acceptance_rate"], default=None)
        # En az kabul edilen stil
        worst_style = min(style_breakdown, key=lambda x: x["acceptance_rate"], default=None)

        return jsonify({
            "total":           total,
            "accepted":        accepted,
            "rejected":        rejected,
            "pending":         pending,
            "acceptance_rate": acceptance_rate,
            "best_style":      best_style["style"] if best_style else None,
            "worst_style":     worst_style["style"] if worst_style else None,
            "by_style":        style_breakdown,
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ----------------------------------------------------------
# CONVERSATION STATISTICS
# ----------------------------------------------------------
@app.route("/conversation_stats/<int:user1_id>/<int:user2_id>", methods=["GET"])
def conversation_stats(user1_id, user2_id):
    try:
        import re as _re
        from collections import Counter

        raw = db_service.get_conversation_stats(user1_id, user2_id)
        overview  = raw["overview"]
        per_user  = raw["per_user"]
        active_hr = raw["active_hour"]
        all_msgs  = raw["all_messages"]

        total_messages = int(overview["total"] or 0)
        first_msg = str(overview["first_msg"])[:10] if overview["first_msg"] else None
        last_msg  = str(overview["last_msg"])[:10]  if overview["last_msg"]  else None

        # Gün sayısı & günlük ortalama
        avg_per_day = None
        if first_msg and last_msg:
            from datetime import date
            d1 = date.fromisoformat(first_msg)
            d2 = date.fromisoformat(last_msg)
            days = max((d2 - d1).days, 1)
            avg_per_day = round(total_messages / days, 1)

        # Kişi başı mesaj sayısı
        user_counts = {str(r["sender_id"]): int(r["msg_count"]) for r in per_user}
        u1_count = user_counts.get(str(user1_id), 0)
        u2_count = user_counts.get(str(user2_id), 0)

        # En aktif saat
        most_active_hour = int(active_hr["hour"]) if active_hr else None

        # Duygu dağılımı — son 60 mesaj üzerinden ML çalıştır
        texts = [m["content"] for m in all_msgs if m.get("content", "").strip()]
        sample = texts[-60:]
        pos = neg = neu = 0
        for t in sample:
            try:
                res = predict_sentiment(t)
                s = res.get("sentiment", "notr").lower()
                if s == "positive":   pos += 1
                elif s == "negative": neg += 1
                else:                 neu += 1
            except Exception:
                neu += 1
        sample_total = pos + neg + neu or 1
        sentiment_dist = {
            "positive": round(pos / sample_total * 100, 1),
            "negative": round(neg / sample_total * 100, 1),
            "neutral":  round(neu / sample_total * 100, 1),
        }

        # En sık kullanılan kelimeler (Türkçe stopword filtresi)
        TR_STOPWORDS = {
            # Türkçe bağlaçlar / zamirler / edatlar
            "bir", "bu", "ve", "da", "de", "mi", "mu", "mü", "mı",
            "ile", "için", "ama", "ya", "ne", "ben", "sen", "o",
            "biz", "siz", "onlar", "gibi", "daha", "çok", "var",
            "yok", "olur", "oldu", "benim", "senin", "onun", "ki",
            "şu", "şey", "evet", "hayır", "tamam", "lan", "ya",
            "değil", "kadar", "sonra", "önce", "bile", "hep",
            "nasıl", "neden", "çünkü", "eğer", "aslında", "zaten",
            "yani", "işte", "artık", "hiç", "her", "hem", "ise",
            "mı", "mu", "ama", "fakat", "lakin", "oysa", "sanki",
            "belki", "galiba", "hala", "hâlâ", "sadece", "sadece",
            "şimdi", "şimdi", "bugün", "yarın", "dün", "bunu",
            "bana", "sana", "ona", "bunu", "şunu", "bende", "sende",
            # İngilizce yaygın kelimeler (medya / sistem mesajlarından)
            "image", "hello", "video", "audio", "file", "http",
            "https", "null", "none", "true", "false", "the", "and",
            "are", "you", "for", "this", "that", "with", "have",
            "from", "not", "but", "what", "all", "were", "when",
            # Sistem / uygulama kelimeleri
            "gönderildi", "iletildi", "okundu", "mesaj", "resim",
            "fotoğraf", "dosya", "ses", "görüntü",
        }
        all_words = []
        for t in texts:
            words = _re.findall(r'\b[a-zA-ZğüşıöçĞÜŞİÖÇ]{3,}\b', t.lower())
            all_words.extend([w for w in words if w not in TR_STOPWORDS])
        top_words = [{"word": w, "count": c} for w, c in Counter(all_words).most_common(10)]

        return jsonify({
            "total_messages":   total_messages,
            "first_message":    first_msg,
            "last_message":     last_msg,
            "avg_per_day":      avg_per_day,
            "user1_count":      u1_count,
            "user2_count":      u2_count,
            "most_active_hour": most_active_hour,
            "sentiment":        sentiment_dist,
            "top_words":        top_words,
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ── EMPATHY SCORER ─────────────────────────────────────────────────────────
# Kural tabanlı Türkçe empati kalıpları + GPT ile derin analiz
_EMPATHY_PATTERNS = {
    "high": [
        "anladım", "anlıyorum", "seni anlıyorum", "zor olmuş", "zor oldu",
        "üzgünüm", "haklısın", "haklı", "hissediyorum", "yanındayım",
        "destekliyorum", "destek olabilirim", "çok zor", "büyük acı",
        "ne kadar zor", "içten geçiyor", "ne hissettirmiş", "nasıl hissediyorsun",
        "seninle birlikte", "geçer bu", "atlarsın", "güçlüsün",
        "senin yanındayım", "ne istersen", "ne yapabilirim", "yardım edebilir miyim",
        "zaman zor olabilir", "bazen böyle olur",
    ],
    "medium": [
        "tamam", "evet", "doğru", "biliyorum", "tahmin ediyorum",
        "mantıklı", "anlaşılır", "fena değil", "olabilir",
        "bekliyorum", "iyi olacak", "sabret", "geçer",
    ],
    "low": [
        "neden", "ama", "yok öyle bir şey", "saçmalama", "abartıyorsun",
        "olmaz", "anlayamam", "anlamıyorum",
    ],
}

def _rule_based_empathy_score(text: str) -> float:
    """0.0 – 1.0 arası kural tabanlı empati skoru."""
    text_lower = text.lower()
    score = 0.4  # başlangıç nötr

    for phrase in _EMPATHY_PATTERNS["high"]:
        if phrase in text_lower:
            score = min(1.0, score + 0.15)

    for phrase in _EMPATHY_PATTERNS["medium"]:
        if phrase in text_lower:
            score = min(1.0, score + 0.05)

    for phrase in _EMPATHY_PATTERNS["low"]:
        if phrase in text_lower:
            score = max(0.0, score - 0.12)

    return score


@app.route("/empathy_score", methods=["POST"])
def empathy_score():
    """
    Gönderilmek üzere yazılan mesajın karşı tarafın duygusuna olan
    empati düzeyini ölçer.

    İstek gövdesi:
        message    : analiz edilecek metin
        sender_id  : gönderen kullanıcı
        receiver_id: alıcı kullanıcı

    Yanıt:
        score       : 0 – 100 (final skor)
        level       : "low" | "medium" | "high"
        rule_score  : kural tabanlı kısmi skor
        gpt_score   : GPT kısmi skor
        feedback    : neden bu skoru aldı
        suggestion  : nasıl daha empatik olabilir
        politeness_delta : ilişki metriğine uygulanan değişim
    """
    data = request.get_json() or {}
    message     = (data.get("message") or "").strip()
    sender_id   = data.get("sender_id")
    receiver_id = data.get("receiver_id")

    if not message:
        return jsonify({"error": "message boş olamaz"}), 400

    # ── 1. KURAL TABANLI SKOR ────────────────────────────────────
    rule_raw   = _rule_based_empathy_score(message)
    rule_score = round(rule_raw * 100)

    # ── 2. BAĞLAM: Alıcının son mesajları ────────────────────────
    context_msgs = []
    if sender_id and receiver_id:
        try:
            rows = db_service.get_recent_receiver_messages(int(sender_id), int(receiver_id), limit=4)
            context_msgs = [r["content"] for r in rows if r.get("content")]
        except Exception:
            pass

    context_block = ""
    if context_msgs:
        context_block = "Son mesajlar (alıcıdan):\n" + "\n".join(f"- {m}" for m in context_msgs) + "\n\n"

    # ── 3. GPT ANALİZİ ───────────────────────────────────────────
    prompt = f"""{context_block}Analiz edilecek mesaj: "{message}"

Görev: Yukarıdaki mesajın karşı tarafın duygularına ne kadar empati kurduğunu değerlendir.

Şu kriterlere göre puan ver (0-100):
- Duygusal tanıma: Karşıdakinin hissini fark ediyor mu?
- Doğrulama: "Haklısın", "Anladım" gibi ifadeler var mı?
- Destek sunma: Yardım teklif ediyor ya da yanında olduğunu hissettiriyor mu?
- Ton: Sıcak mı, soğuk mu, eleştirel mi?

Sadece şu JSON formatında yanıt ver, başka hiçbir şey yazma:
{{
  "gpt_score": <0-100 tam sayı>,
  "feedback": "<neden bu puan — max 1 cümle, Türkçe>",
  "suggestion": "<nasıl daha empatik yapılabilir — max 1 cümle, Türkçe, yoksa boş string>"
}}"""

    gpt_score   = 50
    feedback    = ""
    suggestion  = ""

    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200,
        )
        import json as _json
        raw = resp.choices[0].message.content.strip()
        # JSON bloğu içinden çek
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            parsed     = _json.loads(raw[start:end])
            gpt_score  = int(parsed.get("gpt_score", 50))
            feedback   = parsed.get("feedback", "")
            suggestion = parsed.get("suggestion", "")
    except Exception as e:
        feedback = "GPT analizi tamamlanamadı."

    # ── 4. FINAL SKOR (kural %35 + GPT %65) ─────────────────────
    final_score = round(rule_score * 0.35 + gpt_score * 0.65)
    final_score = max(0, min(100, final_score))

    if final_score >= 70:
        level = "high"
    elif final_score >= 40:
        level = "medium"
    else:
        level = "low"

    # ── 5. POLİTENESS DELTA (ilişki metriği) ────────────────────
    if final_score >= 70:
        politeness_delta = 4
    elif final_score >= 50:
        politeness_delta = 1
    elif final_score < 30:
        politeness_delta = -3
    else:
        politeness_delta = 0

    if sender_id and receiver_id and politeness_delta != 0:
        try:
            rel = db_service.get_relationship(int(sender_id), int(receiver_id))
            if rel:
                cur_pol = rel.get("politeness_score", 50)
                new_pol = max(0, min(100, cur_pol + politeness_delta))
                db_service.update_relationship(
                    int(sender_id), int(receiver_id), politeness_score=new_pol
                )
        except Exception:
            pass

    return jsonify({
        "score":            final_score,
        "level":            level,
        "rule_score":       rule_score,
        "gpt_score":        gpt_score,
        "feedback":         feedback,
        "suggestion":       suggestion,
        "politeness_delta": politeness_delta,
    })


# Group REST APIs
@app.route("/groups", methods=["POST"])
def create_group():
    data = request.get_json()
    group_name = data.get("group_name")
    group_picture = data.get("group_picture")
    admin_id = data.get("admin_id")
    member_ids = data.get("member_ids", [])
    
    if not group_name or not admin_id:
        return jsonify({"error": "group_name and admin_id are required"}), 400
        
    group_id = db_service.create_group(group_name, admin_id, member_ids, group_picture)
    return jsonify({"success": True, "group_id": group_id}), 201

@app.route("/groups/<int:group_id>", methods=["GET"])
def get_group(group_id):
    group = db_service.get_group(group_id)
    if not group:
        return jsonify({"error": "Group not found"}), 404
    return jsonify({"success": True, "group": group})

@app.route("/groups/<int:group_id>", methods=["PATCH"])
def update_group(group_id):
    data = request.get_json()
    group_name = data.get("group_name")
    group_picture = data.get("group_picture")
    db_service.update_group(group_id, group_name, group_picture)
    return jsonify({"success": True})

@app.route("/groups/<int:group_id>/members/<int:user_id>", methods=["DELETE"])
def remove_member(group_id, user_id):
    db_service.remove_group_member(group_id, user_id)
    return jsonify({"success": True})

# -------------------------------
# SSO HELPER
# -------------------------------

def _generate_sso_username(name: str, email: str) -> str:
    base = ''.join(c for c in name.replace(' ', '').lower() if c.isalnum())[:15]
    if not base:
        base = email.split('@')[0][:15]
    username = base
    counter = 1
    while db_service.get_user_by_username(username):
        username = f"{base}{counter}"
        counter += 1
    return username


# -------------------------------
# SSO ENDPOINTS
# -------------------------------

@app.route('/auth/google')
def auth_google():
    state = secrets.token_urlsafe(16)
    _oauth_states.add(state)
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'access_type': 'offline',
    }
    return redirect('https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(params))


@app.route('/auth/google/callback')
def auth_google_callback():
    code  = request.args.get('code')
    state = request.args.get('state')

    if not state or state not in _oauth_states:
        return redirect('smartchat://auth/callback?error=invalid_state')
    _oauth_states.discard(state)

    if not code:
        return redirect('smartchat://auth/callback?error=no_code')

    try:
        token_resp = requests.post('https://oauth2.googleapis.com/token', data={
            'code': code,
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'redirect_uri': GOOGLE_REDIRECT_URI,
            'grant_type': 'authorization_code',
        })
        token_resp.raise_for_status()
        access_token = token_resp.json().get('access_token')

        info_resp = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        info_resp.raise_for_status()
        info = info_resp.json()

        email   = info.get('email', '')
        sso_id  = str(info.get('id', ''))
        name    = info.get('name', '') or email.split('@')[0]
        picture = info.get('picture')

        user = db_service.get_user_by_sso('google', sso_id)
        if not user:
            existing = db_service.get_user_by_email(email)
            if existing:
                db_service.link_sso_to_user(existing['user_id'], 'google', sso_id)
                user = existing
            else:
                username = _generate_sso_username(name, email)
                uid = db_service.insert_sso_user(username, email, 'google', sso_id, picture)
                user = {'user_id': uid}

        return redirect(f'smartchat://auth/callback?user_id={user["user_id"]}&provider=google')
    except Exception as e:
        return redirect(f'smartchat://auth/callback?error={urllib.parse.quote(str(e))}')


@app.route('/auth/microsoft')
def auth_microsoft():
    state = secrets.token_urlsafe(16)
    _oauth_states.add(state)
    params = {
        'client_id': MICROSOFT_CLIENT_ID,
        'redirect_uri': MICROSOFT_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'openid email profile User.Read',
        'state': state,
        'response_mode': 'query',
    }
    return redirect('https://login.microsoftonline.com/common/oauth2/v2.0/authorize?' + urllib.parse.urlencode(params))


@app.route('/auth/microsoft/callback')
def auth_microsoft_callback():
    code  = request.args.get('code')
    state = request.args.get('state')

    if not state or state not in _oauth_states:
        return redirect('smartchat://auth/callback?error=invalid_state')
    _oauth_states.discard(state)

    if not code:
        return redirect('smartchat://auth/callback?error=no_code')

    try:
        token_resp = requests.post(
            'https://login.microsoftonline.com/common/oauth2/v2.0/token',
            data={
                'code': code,
                'client_id': MICROSOFT_CLIENT_ID,
                'client_secret': MICROSOFT_CLIENT_SECRET,
                'redirect_uri': MICROSOFT_REDIRECT_URI,
                'grant_type': 'authorization_code',
            }
        )
        token_resp.raise_for_status()
        access_token = token_resp.json().get('access_token')

        info_resp = requests.get(
            'https://graph.microsoft.com/v1.0/me',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        info_resp.raise_for_status()
        info = info_resp.json()

        email  = info.get('mail') or info.get('userPrincipalName', '')
        sso_id = str(info.get('id', ''))
        name   = info.get('displayName', '') or email.split('@')[0]

        user = db_service.get_user_by_sso('microsoft', sso_id)
        if not user:
            existing = db_service.get_user_by_email(email)
            if existing:
                db_service.link_sso_to_user(existing['user_id'], 'microsoft', sso_id)
                user = existing
            else:
                username = _generate_sso_username(name, email)
                uid = db_service.insert_sso_user(username, email, 'microsoft', sso_id, None)
                user = {'user_id': uid}

        return redirect(f'smartchat://auth/callback?user_id={user["user_id"]}&provider=microsoft')
    except Exception as e:
        return redirect(f'smartchat://auth/callback?error={urllib.parse.quote(str(e))}')


# -------------------------------
# PROFILE ENDPOINTS
# -------------------------------

@app.route("/profile/<int:user_id>", methods=["GET"])
def get_profile(user_id):
    profile = db_service.get_profile(user_id)
    if not profile:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"success": True, "profile": profile})


@app.route("/profile/<int:user_id>", methods=["PATCH"])
def update_profile(user_id):
    data = request.get_json()
    about = data.get("about")
    if about is not None:
        db_service.update_about(user_id, about)
    return jsonify({"success": True, "message": "Profil güncellendi."})


@app.route("/profile/<int:user_id>/picture", methods=["POST"])
def upload_profile_picture(user_id):
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    filename = f"profile_{user_id}_{secure_filename(file.filename)}"
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)

    picture_url = f"docs/{filename}"
    db_service.update_profile_picture(user_id, picture_url)

    return jsonify({
        "success": True,
        "profile_picture": picture_url,
        "message": "Profil fotoğrafı güncellendi."
    })

# -------------------------------
# SOCKET EVENTS (TEST)
# -------------------------------

@socketio.on("connect")
def handle_connect():
    print("Bir kullanıcı bağlandı")
    emit("connected", {"message": "Socket bağlantısı kuruldu"})

@socketio.on("disconnect")
def handle_disconnect():
    print("Bir kullanıcı ayrıldı")

@socketio.on("join_room")
def handle_join_room(data):
    user1 = data.get("user1")
    user2 = data.get("user2")
    if user1 and user2:
        room_name = f"room_{min(user1, user2)}_{max(user1, user2)}"
        join_room(room_name)
        print(f"Kullanıcı {room_name} odasına katıldı")

@socketio.on("send_message")
def handle_send_message(data):
    sender_id = data.get("sender_id")
    receiver_id = data.get("receiver_id")
    group_id = data.get("group_id")
    content = data.get("content")

    if not sender_id or not content:
        return
    
    try:
        from backend.services import db_service
        user = db_service.get_user_by_id(sender_id)
        sender_username = user['username'] if user else 'Unknown'
        
        message_id = db_service.insert_message(sender_id, receiver_id, content, group_id)
        
        message_data = {
            "message_id": message_id,
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "group_id": group_id,
            "content": content,
            "sender_username": sender_username,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        # Sadece özel mesajlarda puan güncelle
        if not group_id:
            from ai_module.ml_model import predict_sentiment
            sentiment_res = predict_sentiment(content)
            sentiment = sentiment_res.get("sentiment", "neutral")
            
            db_service.update_relationship_metrics(sender_id, receiver_id, sentiment)
        
        if group_id:
            # Emit to all users, client filters it
            emit("new_message", message_data, broadcast=True)
        else:
            room_name = f"room_{min(sender_id, receiver_id)}_{max(sender_id, receiver_id)}"
            emit("new_message", message_data, room=room_name)
    except Exception as e:
        print("Socket send_message error:", e)

@socketio.on("typing")
def handle_typing(data):
    sender_id = data.get("sender_id")
    receiver_id = data.get("receiver_id")
    if sender_id and receiver_id:
        room_name = f"room_{min(sender_id, receiver_id)}_{max(sender_id, receiver_id)}"
        emit("typing", {"sender_id": sender_id}, room=room_name, include_self=False)

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=9000, debug=True, allow_unsafe_werkzeug=True)