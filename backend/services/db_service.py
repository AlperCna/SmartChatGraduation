import mysql.connector
from dotenv import load_dotenv
import os

from mysql.connector import pooling

load_dotenv()  # ..env dosyasını yükle

db_pool = None

def get_db_connection():
    global db_pool
    if db_pool is None:
        db_pool = pooling.MySQLConnectionPool(
            pool_name="smartchat_pool",
            pool_size=5,
            pool_reset_session=True,
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "smartchat"),
            port=int(os.getenv("DB_PORT", 3306))
        )
    return db_pool.get_connection()


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


def insert_message(sender_id, receiver_id, content, group_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if group_id:
        sql = "INSERT INTO messages (sender_id, receiver_id, content, group_id) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql, (sender_id, None, content, group_id))
    else:
        sql = "INSERT INTO messages (sender_id, receiver_id, content) VALUES (%s, %s, %s)"
        cursor.execute(sql, (sender_id, receiver_id, content))
    message_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    conn.close()
    return message_id


def get_messages(sender_id, receiver_id=None, group_id=None):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if group_id:
        sql = """
            SELECT m.*, media.file_path, media.media_type, u.username as sender_username
            FROM messages m
            LEFT JOIN media ON m.message_id = media.message_id
            JOIN users u ON m.sender_id = u.user_id
            WHERE m.group_id = %s
            ORDER BY m.timestamp ASC
        """
        cursor.execute(sql, (group_id,))
    else:
        sql = """
            SELECT m.*, media.file_path, media.media_type, u.username as sender_username
            FROM messages m
            LEFT JOIN media ON m.message_id = media.message_id
            JOIN users u ON m.sender_id = u.user_id
            WHERE (m.sender_id = %s AND m.receiver_id = %s AND m.group_id IS NULL)
               OR (m.sender_id = %s AND m.receiver_id = %s AND m.group_id IS NULL)
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
    # Daha gelişmiş sorgu: Son mesajı ve zamanını da getirir, grup ve normal sohbetleri birleştirir
    sql = """
        SELECT u.user_id, u.username,
               (SELECT content FROM messages
                WHERE ((sender_id = %s AND receiver_id = u.user_id)
                   OR (sender_id = u.user_id AND receiver_id = %s))
                   AND group_id IS NULL
                ORDER BY timestamp DESC LIMIT 1) as last_message,
               (SELECT timestamp FROM messages
                WHERE ((sender_id = %s AND receiver_id = u.user_id)
                   OR (sender_id = u.user_id AND receiver_id = %s))
                   AND group_id IS NULL
                ORDER BY timestamp DESC LIMIT 1) as last_time,
               0 as is_group
        FROM users u
        WHERE u.user_id IN (
            SELECT DISTINCT CASE WHEN sender_id = %s THEN receiver_id ELSE sender_id END
            FROM messages
            WHERE (sender_id = %s OR receiver_id = %s) AND group_id IS NULL
        )
        UNION
        SELECT g.group_id as user_id, g.group_name as username,
               (SELECT content FROM messages
                WHERE messages.group_id = g.group_id
                ORDER BY timestamp DESC LIMIT 1) as last_message,
               (SELECT timestamp FROM messages
                WHERE messages.group_id = g.group_id
                ORDER BY timestamp DESC LIMIT 1) as last_time,
               1 as is_group
        FROM `groups` g
        JOIN group_members gm ON g.group_id = gm.group_id
        WHERE gm.user_id = %s
        ORDER BY last_time DESC
    """
    cursor.execute(sql, (user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id))
    result = cursor.fetchall()
    
    # Zaman formatını UI için düzenle (isteğe bağlı)
    for row in result:
        if row["last_time"]:
            row["last_time"] = str(row["last_time"])
            
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

def insert_relationship_history(user1_id, user2_id, closeness_score):
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = """
        INSERT INTO relationship_history (user1_id, user2_id, closeness_score, timestamp)
        VALUES (%s, %s, %s, NOW())
    """
    cursor.execute(sql, (user1_id, user2_id, closeness_score))
    conn.commit()
    cursor.close()
    conn.close()

def get_relationship_history(user1_id, user2_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql = """
        SELECT closeness_score, timestamp 
        FROM relationship_history
        WHERE (user1_id = %s AND user2_id = %s)
           OR (user1_id = %s AND user2_id = %s)
        ORDER BY timestamp ASC
    """
    cursor.execute(sql, (user1_id, user2_id, user2_id, user1_id))
    history = cursor.fetchall()
    
    for row in history:
        if row["timestamp"]:
            row["timestamp"] = str(row["timestamp"])
            
    cursor.close()
    conn.close()
    return history


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
        
        # Sadece skor gerçekten değiştiyse geçmişi güncelle
        if new_score != relationship["closeness_score"]:
            insert_relationship_history(user1_id, user2_id, new_score)
    else:
        create_relationship(user1_id, user2_id, "neutral", 50)
        insert_relationship_history(user1_id, user2_id, 50)
        adjust_closeness(user1_id, user2_id, delta)

# Group Functions
def create_group(group_name, admin_id, member_ids, group_picture=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = "INSERT INTO `groups` (group_name, group_picture, admin_id) VALUES (%s, %s, %s)"
    cursor.execute(sql, (group_name, group_picture, admin_id))
    group_id = cursor.lastrowid
    
    # Add members including admin
    members = set(member_ids)
    members.add(admin_id)
    
    member_sql = "INSERT INTO group_members (group_id, user_id) VALUES (%s, %s)"
    cursor.executemany(member_sql, [(group_id, m) for m in members])
    conn.commit()
    cursor.close()
    conn.close()
    return group_id

def get_group(group_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM `groups` WHERE group_id = %s", (group_id,))
    group = cursor.fetchone()
    
    if group:
        cursor.execute("SELECT u.user_id, u.username FROM users u JOIN group_members gm ON u.user_id = gm.user_id WHERE gm.group_id = %s", (group_id,))
        group['members'] = cursor.fetchall()
        
    cursor.close()
    conn.close()
    return group

def update_group(group_id, group_name=None, group_picture=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    fields = []
    values = []
    if group_name is not None:
        fields.append("group_name = %s")
        values.append(group_name)
    if group_picture is not None:
        fields.append("group_picture = %s")
        values.append(group_picture)
        
    if fields:
        sql = f"UPDATE `groups` SET {', '.join(fields)} WHERE group_id = %s"
        values.append(group_id)
        cursor.execute(sql, tuple(values))
        conn.commit()
    cursor.close()
    conn.close()

def remove_group_member(group_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM group_members WHERE group_id = %s AND user_id = %s", (group_id, user_id))
    conn.commit()
    cursor.close()
    conn.close()
