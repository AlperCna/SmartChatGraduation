import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()  # .env dosyasını yükle


def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        port=int(os.getenv("DB_PORT"))
    )


def insert_user(username, email, password_hash):
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)"
    cursor.execute(sql, (username, email, password_hash))
    conn.commit()
    cursor.close()
    conn.close()


def get_users():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return users


def insert_message(sender_id, receiver_id, content):
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = "INSERT INTO messages (sender_id, receiver_id, content) VALUES (%s, %s, %s)"
    cursor.execute(sql, (sender_id, receiver_id, content))
    message_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()
    return message_id


def get_messages(sender_id, receiver_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql = """
        SELECT m.*, media.file_path, media.media_type
        FROM messages m
        LEFT JOIN media ON m.message_id = media.message_id
        WHERE (m.sender_id = %s AND m.receiver_id = %s)
           OR (m.sender_id = %s AND m.receiver_id = %s)
        ORDER BY m.timestamp ASC
    """
    cursor.execute(sql, (sender_id, receiver_id, receiver_id, sender_id))
    messages = cursor.fetchall()
    cursor.close()
    conn.close()
    return messages


def get_user_by_email(email):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user


def get_user_by_username(username):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user


def get_chat_partners(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT DISTINCT u.user_id, u.username
        FROM users u
        JOIN messages m ON (u.user_id = m.sender_id OR u.user_id = m.receiver_id)
        WHERE %s IN (m.sender_id, m.receiver_id) AND u.user_id != %s
    """, (user_id, user_id))
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return result


def insert_media(message_id, media_type, file_path):
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = """
        INSERT INTO media (message_id, media_type, file_path, uploaded_at)
        VALUES (%s, %s, %s, NOW())
    """
    cursor.execute(sql, (message_id, media_type, file_path))
    conn.commit()
    cursor.close()
    conn.close()


def insert_suggestion(user_id, original_text, suggested_text, style):
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = """
        INSERT INTO suggestions (user_id, original_text, suggested_text, style, accepted, timestamp)
        VALUES (%s, %s, %s, %s, NULL, NOW())
    """
    cursor.execute(sql, (user_id, original_text, suggested_text, style))
    conn.commit()
    suggestion_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return suggestion_id


def update_suggestion_acceptance(suggestion_id, accepted):
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = "UPDATE suggestions SET accepted = %s WHERE suggestion_id = %s"
    cursor.execute(sql, (int(accepted), suggestion_id))
    conn.commit()
    cursor.close()
    conn.close()


def get_relationship(user1_id, user2_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql = """
        SELECT * FROM user_relationships
        WHERE (user1_id = %s AND user2_id = %s)
           OR (user1_id = %s AND user2_id = %s)
    """
    cursor.execute(sql, (user1_id, user2_id, user2_id, user1_id))
    relationship = cursor.fetchone()
    cursor.close()
    conn.close()
    return relationship


def create_relationship(user1_id, user2_id, style="neutral", closeness_score=50):
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = """
        INSERT INTO user_relationships (user1_id, user2_id, style, closeness_score)
        VALUES (%s, %s, %s, %s)
    """
    cursor.execute(sql, (user1_id, user2_id, style, closeness_score))
    conn.commit()
    cursor.close()
    conn.close()


def update_relationship(user1_id, user2_id, style=None, closeness_score=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    fields = []
    values = []
    if style is not None:
        fields.append("style = %s")
        values.append(style)
    if closeness_score is not None:
        fields.append("closeness_score = %s")
        values.append(closeness_score)

    if not fields:
        return

    sql = f"""
        UPDATE user_relationships
        SET {', '.join(fields)}
        WHERE (user1_id = %s AND user2_id = %s)
           OR (user1_id = %s AND user2_id = %s)
    """
    values.extend([user1_id, user2_id, user2_id, user1_id])
    cursor.execute(sql, tuple(values))
    conn.commit()
    cursor.close()
    conn.close()


def adjust_closeness(user1_id, user2_id, delta):
    relationship = get_relationship(user1_id, user2_id)
    if relationship:
        new_score = max(0, min(100, relationship["closeness_score"] + delta))

        if new_score <= 30:
            style = "formal"
        elif new_score >= 71:
            style = "informal"
        else:
            style = "neutral"

        update_relationship(user1_id, user2_id, style=style, closeness_score=new_score)
    else:
        create_relationship(user1_id, user2_id, "neutral", 50)
        adjust_closeness(user1_id, user2_id, delta)
