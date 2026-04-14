import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

def migrate():
    print("Connecting to database...")
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "smartchat"),
        port=int(os.getenv("DB_PORT", 3306))
    )
    cursor = conn.cursor(dictionary=True)

    print("Creating relationship_history table if not exists...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS relationship_history (
            history_id INT AUTO_INCREMENT PRIMARY KEY,
            user1_id INT NOT NULL,
            user2_id INT NOT NULL,
            closeness_score INT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user1_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (user2_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)
    
    print("Fetching existing relationships...")
    cursor.execute("SELECT * FROM user_relationships")
    relationships = cursor.fetchall()

    if relationships:
        print(f"Found {len(relationships)} relationships. Initializing history for them...")
        insert_sql = "INSERT INTO relationship_history (user1_id, user2_id, closeness_score) VALUES (%s, %s, %s)"
        for r in relationships:
            # Sadece bir adet başlangıç verisi ekliyoruz
            cursor.execute(insert_sql, (r["user1_id"], r["user2_id"], r["closeness_score"]))
    
    conn.commit()
    print("Migration successful!")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    migrate()
