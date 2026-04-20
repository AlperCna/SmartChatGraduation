import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import Flask, jsonify, request, send_from_directory
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
from ai_module.ml_model import predict_sentiment, predict_style, load_sentiment_model, load_style_model
import threading
from datetime import datetime


load_dotenv()
print("API Key test:", os.getenv("OPENAI_API_KEY")[:6], "...")  # sadece ilk 6 karakter

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
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

@app.route("/relationships/<int:user1_id>/<int:user2_id>/history", methods=["GET"])
def get_relationship_history_route(user1_id, user2_id):
    history = db_service.get_relationship_history(user1_id, user2_id)
    relationship = db_service.get_relationship(user1_id, user2_id)
    current_score = relationship["closeness_score"] if relationship else 50
    return jsonify({
        "success": True,
        "current_score": current_score,
        "history": history
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

        if politeness > 50 and closeness <= 50:
            matrix_style = "Formal (Resmi)"
        elif politeness > 50 and closeness > 50:
            matrix_style = "Respectful-Close (Candan/Saygılı)"
        elif politeness <= 50 and closeness > 50:
            matrix_style = "Informal (Samimi/Kanka)"
        else:
            matrix_style = "Cold (Soğuk/Mesafeli)"

        relationship_style = matrix_style

        # --------------------------------------------------
        # 5️⃣ GPT İLE MESAJ TAMAMLAMA / ÖNERİ
        # --------------------------------------------------
        prompt = f"""
Görev:
Kullanıcılar arasındaki Samimiyet: {closeness}, Nezaket: {politeness}
İlişki Tarzı (Matris Sonucu): {matrix_style}

Aşağıdaki konuşma geçmişini dikkate alarak,
kullanıcının son mesajını yazım hataları düzeltilmiş,
ve yukarıda belirtilen '{matrix_style}' ilişki tarzına (örneğin kankaysa daha argo, hocasıysa daha kibar ama yakın) uygun şekilde yeniden yaz.

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

        # We need the relationship style
        style_res = detect_style(sender_id, receiver_id, last_message)
        relationship_style = style_res.get("relationship_style", "Formal")

        prompt = f"""
Görev:
Karşı taraf şu mesajı gönderdi: "{last_message}"
Sen, {sender_id} numaralı kullanıcısın ve aranızdaki iletişim tarzı (closeness stili): '{relationship_style}'.
Buna uygun, cevap olarak gönderilebilecek 3 farklı, KISA (2-5 kelime), doğal, Türkçe "anında yanıt" (quick reply) alternatifi üret.
Lütfen sadece JSON formatında bir liste (array) döndür. Başka hiçbir açıklama veya markdown ekleme.
Örnek:
["Teşekkürler", "Harika fikir!", "Daha sonra konuşalım"]
"""
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=60
        )

        content = response.choices[0].message.content.strip()
        
        # Parse output
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
            
        try:
            replies = json.loads(content)
        except json.JSONDecodeError:
            import re
            matches = re.findall(r'"([^"]*)"', content)
            replies = matches if len(matches) > 0 else []

        if not isinstance(replies, list):
            replies = []
            
        return jsonify({"replies": replies[:3]}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


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
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)