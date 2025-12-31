from flask import Flask, jsonify, request
from backend.services import db_service
from flask_cors import CORS
import bcrypt
import os
from werkzeug.utils import secure_filename
from ai_module.punctuation_fixer import suggest_punctuation
from ai_module.style_adapter import detect_style, adapt_style
from openai import OpenAI
from dotenv import load_dotenv
import os
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
analyzer = SentimentIntensityAnalyzer()
from ai_module.ml_model import predict_sentiment , predict_style
from datetime import datetime


load_dotenv()
print("API Key test:", os.getenv("OPENAI_API_KEY")[:6], "...")  # sadece ilk 6 karakter

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
CORS(app)

#  Medya dosyalarının kaydedileceği klasör
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "..", "docs")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/hello", methods=["GET"])
def hello():
    return {"message": "SmartChat Flask sunucusu çalışıyor."}

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
    content = data.get("content")
    if not sender_id or not receiver_id or not content:
        return jsonify({"error": "sender_id, receiver_id ve content zorunludur."}), 400

    message_id = db_service.insert_message(sender_id, receiver_id, content)
    return jsonify({
        "message": "Mesaj başarıyla gönderildi.",
        "message_id": message_id
    }), 200


@app.route("/messages", methods=["GET"])
def list_messages():
    sender_id = request.args.get("sender_id")
    receiver_id = request.args.get("receiver_id")
    if not sender_id or not receiver_id:
        return jsonify({"error": "sender_id ve receiver_id zorunludur."}), 400

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
        return jsonify({"message": "User created successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        email = data.get("email", "").strip()
        password = data.get("password", "")
        user = db_service.get_user_by_email(email)
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 401
        stored_pw = user["password_hash"]
        if not stored_pw or not stored_pw.startswith("$2"):
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

# 📤 Yeni: Fotoğraf/ses/video medya dosyası yükleme
@app.route("/upload_media", methods=["POST"])
def upload_media():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    media_type = request.form.get("media_type", "image")
    message_id = request.form.get("message_id")  # opsiyonel olabilir

    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)

    # veritabanına kayıt
    db_service.insert_media(message_id, media_type, f"docs/{filename}")

    return jsonify({"message": "Media uploaded", "file_path": f"docs/{filename}"})



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
        # 4️⃣ CLOSENESS SCORE GÜNCELLEME (SADECE BURADA)
        # --------------------------------------------------
        delta = 0
        if sentiment == "positive":
            delta = 5
        elif sentiment == "negative":
            delta = -5

        if delta != 0:
            db_service.adjust_closeness(sender_id, receiver_id, delta)

        # --------------------------------------------------
        # 5️⃣ GPT İLE MESAJ TAMAMLAMA / ÖNERİ
        # --------------------------------------------------
        prompt = f"""
Görev:
Aşağıdaki konuşma geçmişini dikkate alarak,
kullanıcının son mesajını yazım hataları düzeltilmiş,
'{relationship_style}' üsluba uygun şekilde yeniden yaz.

Konuşma Geçmişi:
{history}

Kullanıcının Mesajı:
{text}

Sadece önerilen cümleyi döndür.
"""

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
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





if __name__ == "__main__":
    app.run(debug=True)
