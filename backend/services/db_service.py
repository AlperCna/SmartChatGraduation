import mysql.connector
from dotenv import load_dotenv
import os
import logging
from contextlib import contextmanager
from mysql.connector import pooling

load_dotenv(override=True)

logger = logging.getLogger(__name__)

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


@contextmanager
def _db_cursor(dictionary=False):
    """
    Context manager: bağlantı ve cursor'ı otomatik açar/kapatır.
    Hata olursa rollback yapar, her durumda connection pool'a geri verir.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=dictionary)
        yield conn, cursor
    except mysql.connector.Error as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.error(f"DB Error: {e}")
        raise
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# -------------------------------------------------------------------
# USER FUNCTIONS
# -------------------------------------------------------------------

def insert_user(username, email, password_hash):
    with _db_cursor() as (conn, cursor):
        sql = "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)"
        cursor.execute(sql, (username, email, password_hash))
        conn.commit()


def get_users():
    with _db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute("SELECT * FROM users")
        return cursor.fetchall()


def get_user_by_email(email):
    with _db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        return cursor.fetchone()


def get_user_by_username(username):
    with _db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        return cursor.fetchone()


def get_user_by_id(user_id):
    with _db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        return cursor.fetchone()


# -------------------------------------------------------------------
# MESSAGE FUNCTIONS
# -------------------------------------------------------------------

def insert_message(sender_id, receiver_id, content, group_id=None):
    with _db_cursor() as (conn, cursor):
        if group_id:
            sql = "INSERT INTO messages (sender_id, receiver_id, content, group_id) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (sender_id, None, content, group_id))
        else:
            sql = "INSERT INTO messages (sender_id, receiver_id, content) VALUES (%s, %s, %s)"
            cursor.execute(sql, (sender_id, receiver_id, content))
        message_id = cursor.lastrowid
        conn.commit()
        return message_id


def get_messages(sender_id, receiver_id=None, group_id=None):
    with _db_cursor(dictionary=True) as (conn, cursor):
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
        return cursor.fetchall()


def get_recent_messages_from_user(sender_id, receiver_id, limit=5):
    """Belirli bir göndericiden, belirli bir alıcıya gönderilen son N mesajı getirir."""
    with _db_cursor(dictionary=True) as (conn, cursor):
        sql = """
            SELECT content, timestamp
            FROM messages
            WHERE sender_id = %s AND receiver_id = %s AND group_id IS NULL
              AND content IS NOT NULL AND content != ''
            ORDER BY timestamp DESC
            LIMIT %s
        """
        cursor.execute(sql, (sender_id, receiver_id, limit))
        return cursor.fetchall()


def get_chat_partners(user_id):
    with _db_cursor(dictionary=True) as (conn, cursor):
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
        cursor.execute(sql, (user_id,) * 8)
        result = cursor.fetchall()

    for row in result:
        if row.get("last_time"):
            row["last_time"] = str(row["last_time"])
    return result


# -------------------------------------------------------------------
# MEDIA
# -------------------------------------------------------------------

def insert_media(message_id, media_type, file_path):
    with _db_cursor() as (conn, cursor):
        sql = """
            INSERT INTO media (message_id, media_type, file_path, uploaded_at)
            VALUES (%s, %s, %s, NOW())
        """
        cursor.execute(sql, (message_id, media_type, file_path))
        conn.commit()


# -------------------------------------------------------------------
# SUGGESTIONS
# -------------------------------------------------------------------

def insert_suggestion(user_id, original_text, suggested_text, style):
    with _db_cursor() as (conn, cursor):
        sql = """
            INSERT INTO suggestions (user_id, original_text, suggested_text, style, accepted, timestamp)
            VALUES (%s, %s, %s, %s, NULL, NOW())
        """
        cursor.execute(sql, (user_id, original_text, suggested_text, style))
        conn.commit()
        return cursor.lastrowid


def update_suggestion_acceptance(suggestion_id, accepted):
    with _db_cursor() as (conn, cursor):
        sql = "UPDATE suggestions SET accepted = %s WHERE suggestion_id = %s"
        cursor.execute(sql, (int(accepted), suggestion_id))
        conn.commit()


# -------------------------------------------------------------------
# RELATIONSHIP FUNCTIONS
# -------------------------------------------------------------------

def get_relationship(user1_id, user2_id):
    with _db_cursor(dictionary=True) as (conn, cursor):
        sql = """
            SELECT * FROM user_relationships
            WHERE (user1_id = %s AND user2_id = %s)
               OR (user1_id = %s AND user2_id = %s)
        """
        cursor.execute(sql, (user1_id, user2_id, user2_id, user1_id))
        return cursor.fetchone()


def create_relationship(user1_id, user2_id, style="neutral", closeness_score=50, politeness_score=50):
    with _db_cursor() as (conn, cursor):
        sql = """
            INSERT INTO user_relationships (user1_id, user2_id, style, closeness_score, politeness_score)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (user1_id, user2_id, style, closeness_score, politeness_score))
        conn.commit()


def update_relationship(user1_id, user2_id, style=None, closeness_score=None, politeness_score=None):
    fields, values = [], []
    if style is not None:
        fields.append("style = %s")
        values.append(style)
    if closeness_score is not None:
        fields.append("closeness_score = %s")
        values.append(closeness_score)
    if politeness_score is not None:
        fields.append("politeness_score = %s")
        values.append(politeness_score)

    if not fields:
        return

    with _db_cursor() as (conn, cursor):
        sql = f"""
            UPDATE user_relationships
            SET {', '.join(fields)}
            WHERE (user1_id = %s AND user2_id = %s)
               OR (user1_id = %s AND user2_id = %s)
        """
        values.extend([user1_id, user2_id, user2_id, user1_id])
        cursor.execute(sql, tuple(values))
        conn.commit()


def insert_relationship_history(user1_id, user2_id, closeness_score):
    with _db_cursor() as (conn, cursor):
        sql = """
            INSERT INTO relationship_history (user1_id, user2_id, closeness_score, timestamp)
            VALUES (%s, %s, %s, NOW())
        """
        cursor.execute(sql, (user1_id, user2_id, closeness_score))
        conn.commit()


def get_relationship_history(user1_id, user2_id):
    with _db_cursor(dictionary=True) as (conn, cursor):
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
        if row.get("timestamp"):
            row["timestamp"] = str(row["timestamp"])
    return history


def calculate_matrix_style(closeness, politeness):
    if politeness > 50 and closeness <= 50:
        return "Formal (Resmi)"
    elif politeness > 50 and closeness > 50:
        return "Respectful-Close (Candan/Saygılı)"
    elif politeness <= 50 and closeness > 50:
        return "Informal (Samimi/Kanka)"
    else:
        return "Cold (Soğuk/Mesafeli)"


def update_relationship_metrics(user1_id, user2_id, sentiment="neutral"):
    try:
        with _db_cursor(dictionary=True) as (conn, cursor):
            sql_count = """
                SELECT COUNT(*) as total FROM messages
                WHERE (sender_id = %s AND receiver_id = %s)
                   OR (sender_id = %s AND receiver_id = %s)
            """
            cursor.execute(sql_count, (user1_id, user2_id, user2_id, user1_id))
            result = cursor.fetchone()
            total_messages = result['total'] if result else 0

        # TEST AMAÇLI: Hızlı test edebilmek için her mesaj başına yakınlığı 5 puan artırıyoruz.
        # Normalde bu değer 'total_messages // 10' veya benzeri yavaş bir orandı.
        new_closeness = min(100, total_messages * 5)
        relationship = get_relationship(user1_id, user2_id)

        current_politeness = (
            relationship["politeness_score"]
            if relationship and "politeness_score" in relationship
            else 50
        )
        politeness_delta = 5 if sentiment == "positive" else (-5 if sentiment == "negative" else 0)
        new_politeness = max(0, min(100, current_politeness + politeness_delta))
        new_style = calculate_matrix_style(new_closeness, new_politeness)

        if relationship:
            if (new_closeness != relationship["closeness_score"]
                    or new_politeness != relationship["politeness_score"]
                    or new_style != relationship.get("style")):
                update_relationship(user1_id, user2_id,
                                    style=new_style,
                                    closeness_score=new_closeness,
                                    politeness_score=new_politeness)
                if new_closeness != relationship["closeness_score"]:
                    insert_relationship_history(user1_id, user2_id, new_closeness)
        else:
            create_relationship(user1_id, user2_id,
                                style=new_style,
                                closeness_score=new_closeness,
                                politeness_score=new_politeness)
            insert_relationship_history(user1_id, user2_id, new_closeness)

    except Exception as e:
        # Metrik güncelleme kritik değil — mesaj gönderimini engelleme
        logger.warning(f"update_relationship_metrics failed (non-critical): {e}")


# -------------------------------------------------------------------
# MOOD FORECAST & EMPATHY SCORER
# -------------------------------------------------------------------

def get_messages_for_mood_forecast(user_id: int, partner_id: int, limit: int = 30):
    """
    Receiver (user_id)'in son N mesajını timestamp ile döndürür.
    Sadece ikili konuşmadan, grup dışı mesajlar.
    """
    with _db_cursor(dictionary=True) as (conn, cursor):
        sql = """
            SELECT content, timestamp, sender_id
            FROM messages
            WHERE sender_id = %s AND receiver_id = %s
              AND group_id IS NULL
              AND content IS NOT NULL AND content != ''
              AND content NOT IN ('image', 'video', 'audio', 'file', 'location')
              AND LENGTH(content) > 2
            ORDER BY timestamp DESC
            LIMIT %s
        """
        cursor.execute(sql, (user_id, partner_id, limit))
        rows = cursor.fetchall()

    for r in rows:
        if r.get("timestamp"):
            r["timestamp"] = r["timestamp"] if isinstance(r["timestamp"], str) else str(r["timestamp"])
    return rows


def get_hourly_sentiment_pattern(user_id: int, partner_id: int):
    """
    Kullanıcının farklı saatlerde gönderdiği mesaj sayısını döndürür.
    Mood forecast için gece/gündüz pattern analizi.
    """
    with _db_cursor(dictionary=True) as (conn, cursor):
        sql = """
            SELECT HOUR(timestamp) AS hour, COUNT(*) AS msg_count
            FROM messages
            WHERE sender_id = %s AND receiver_id = %s
              AND group_id IS NULL
              AND timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            GROUP BY HOUR(timestamp)
            ORDER BY hour
        """
        cursor.execute(sql, (user_id, partner_id))
        return cursor.fetchall()


def get_message_frequency(user_id: int, partner_id: int):
    """
    Son 7 günlük mesaj yoğunluğunu gün bazında döndürür (sıklık düşüşü tespiti için).
    """
    with _db_cursor(dictionary=True) as (conn, cursor):
        sql = """
            SELECT DATE(timestamp) AS day, COUNT(*) AS msg_count
            FROM messages
            WHERE sender_id = %s AND receiver_id = %s
              AND group_id IS NULL
              AND timestamp >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY DATE(timestamp)
            ORDER BY day DESC
        """
        cursor.execute(sql, (user_id, partner_id))
        return cursor.fetchall()


def get_recent_receiver_messages(sender_id: int, receiver_id: int, limit: int = 5):
    """Empathy scorer için: alıcının son N mesajını bağlam olarak döndürür."""
    with _db_cursor(dictionary=True) as (conn, cursor):
        sql = """
            SELECT content, timestamp
            FROM messages
            WHERE sender_id = %s AND receiver_id = %s
              AND group_id IS NULL
              AND content IS NOT NULL AND content != ''
              AND LENGTH(content) > 2
            ORDER BY timestamp DESC
            LIMIT %s
        """
        cursor.execute(sql, (receiver_id, sender_id, limit))
        return list(reversed(cursor.fetchall()))


# -------------------------------------------------------------------
# GROUP FUNCTIONS
# -------------------------------------------------------------------

def create_group(group_name, admin_id, member_ids, group_picture=None):
    with _db_cursor() as (conn, cursor):
        sql = "INSERT INTO `groups` (group_name, group_picture, admin_id) VALUES (%s, %s, %s)"
        cursor.execute(sql, (group_name, group_picture, admin_id))
        group_id = cursor.lastrowid

        members = set(member_ids)
        members.add(admin_id)
        member_sql = "INSERT INTO group_members (group_id, user_id) VALUES (%s, %s)"
        cursor.executemany(member_sql, [(group_id, m) for m in members])
        conn.commit()
        return group_id


def get_group(group_id):
    with _db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute("SELECT * FROM `groups` WHERE group_id = %s", (group_id,))
        group = cursor.fetchone()
        if group:
            cursor.execute(
                "SELECT u.user_id, u.username FROM users u "
                "JOIN group_members gm ON u.user_id = gm.user_id WHERE gm.group_id = %s",
                (group_id,)
            )
            group['members'] = cursor.fetchall()
        return group


def update_group(group_id, group_name=None, group_picture=None):
    fields, values = [], []
    if group_name is not None:
        fields.append("group_name = %s")
        values.append(group_name)
    if group_picture is not None:
        fields.append("group_picture = %s")
        values.append(group_picture)

    if not fields:
        return

    with _db_cursor() as (conn, cursor):
        sql = f"UPDATE `groups` SET {', '.join(fields)} WHERE group_id = %s"
        values.append(group_id)
        cursor.execute(sql, tuple(values))
        conn.commit()


def remove_group_member(group_id, user_id):
    with _db_cursor() as (conn, cursor):
        cursor.execute(
            "DELETE FROM group_members WHERE group_id = %s AND user_id = %s",
            (group_id, user_id)
        )
        conn.commit()


# -------------------------------------------------------------------
# PROFILE FUNCTIONS
# -------------------------------------------------------------------

def get_profile(user_id):
    with _db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            "SELECT user_id, username, email, profile_picture, about FROM users WHERE user_id = %s",
            (user_id,)
        )
        return cursor.fetchone()


def update_about(user_id, about):
    with _db_cursor() as (conn, cursor):
        cursor.execute(
            "UPDATE users SET about = %s WHERE user_id = %s",
            (about, user_id)
        )
        conn.commit()


def update_profile_picture(user_id, picture_path):
    with _db_cursor() as (conn, cursor):
        cursor.execute(
            "UPDATE users SET profile_picture = %s WHERE user_id = %s",
            (picture_path, user_id)
        )
        conn.commit()


# -------------------------------------------------------------------
# SSO FUNCTIONS
# -------------------------------------------------------------------

def get_user_by_sso(provider, sso_id):
    with _db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            "SELECT * FROM users WHERE sso_provider = %s AND sso_id = %s",
            (provider, sso_id)
        )
        return cursor.fetchone()


def insert_sso_user(username, email, sso_provider, sso_id, profile_picture=None):
    with _db_cursor() as (conn, cursor):
        sql = """
            INSERT INTO users (username, email, password_hash, sso_provider, sso_id, profile_picture)
            VALUES (%s, %s, NULL, %s, %s, %s)
        """
        cursor.execute(sql, (username, email, sso_provider, sso_id, profile_picture))
        conn.commit()
        return cursor.lastrowid


def link_sso_to_user(user_id, provider, sso_id):
    with _db_cursor() as (conn, cursor):
        cursor.execute(
            "UPDATE users SET sso_provider = %s, sso_id = %s WHERE user_id = %s",
            (provider, sso_id, user_id)
        )
        conn.commit()


# -------------------------------------------------------------------
# SUGGESTION ANALYTICS
# -------------------------------------------------------------------

def get_suggestion_analytics(user_id):
    with _db_cursor(dictionary=True) as (conn, cursor):
        # Genel özet
        cursor.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN accepted = 1 THEN 1 ELSE 0 END) AS accepted_count,
                SUM(CASE WHEN accepted = 0 THEN 1 ELSE 0 END) AS rejected_count,
                SUM(CASE WHEN accepted IS NULL THEN 1 ELSE 0 END) AS pending_count
            FROM suggestions
            WHERE user_id = %s
        """, (user_id,))
        summary = cursor.fetchone()

        # Stil bazlı kabul oranı
        cursor.execute("""
            SELECT
                style,
                COUNT(*) AS total,
                SUM(CASE WHEN accepted = 1 THEN 1 ELSE 0 END) AS accepted,
                SUM(CASE WHEN accepted = 0 THEN 1 ELSE 0 END) AS rejected
            FROM suggestions
            WHERE user_id = %s AND accepted IS NOT NULL AND style IS NOT NULL AND style != ''
            GROUP BY style
            ORDER BY total DESC
        """, (user_id,))
        by_style = cursor.fetchall()

        return {"summary": summary, "by_style": by_style}


# -------------------------------------------------------------------
# CONVERSATION STATS
# -------------------------------------------------------------------

def get_conversation_stats(user1_id, user2_id):
    with _db_cursor(dictionary=True) as (conn, cursor):
        base = """
            (sender_id = %s AND receiver_id = %s AND group_id IS NULL)
            OR (sender_id = %s AND receiver_id = %s AND group_id IS NULL)
        """
        params = (user1_id, user2_id, user2_id, user1_id)

        # Toplam + ilk/son mesaj tarihi
        cursor.execute(f"""
            SELECT COUNT(*) AS total,
                   MIN(timestamp) AS first_msg,
                   MAX(timestamp) AS last_msg
            FROM messages
            WHERE {base}
        """, params)
        overview = cursor.fetchone()

        # Kişi başı mesaj sayısı
        cursor.execute(f"""
            SELECT sender_id, COUNT(*) AS msg_count
            FROM messages
            WHERE {base}
            GROUP BY sender_id
        """, params)
        per_user = cursor.fetchall()

        # En aktif saat
        cursor.execute(f"""
            SELECT HOUR(timestamp) AS hour, COUNT(*) AS cnt
            FROM messages
            WHERE {base}
            GROUP BY hour
            ORDER BY cnt DESC
            LIMIT 1
        """, params)
        active_hour = cursor.fetchone()

        # Tüm mesaj içerikleri (kelime frekansı + sentiment için)
        cursor.execute(f"""
            SELECT sender_id, content
            FROM messages
            WHERE {base}
              AND content IS NOT NULL AND content != ''
            ORDER BY timestamp ASC
        """, params)
        all_messages = cursor.fetchall()

        return {
            "overview": overview,
            "per_user": per_user,
            "active_hour": active_hour,
            "all_messages": all_messages,
        }
