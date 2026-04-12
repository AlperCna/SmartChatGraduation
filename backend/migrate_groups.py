import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def migrate():
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        port=int(os.getenv("DB_PORT"))
    )
    cursor = conn.cursor()
    
    print("Creating groups table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS `groups` (
            group_id INT AUTO_INCREMENT PRIMARY KEY,
            group_name VARCHAR(255) NOT NULL,
            group_picture VARCHAR(255),
            admin_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (admin_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)

    print("Creating group_members table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            group_id INT NOT NULL,
            user_id INT NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (group_id, user_id),
            FOREIGN KEY (group_id) REFERENCES `groups`(group_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)

    print("Updating messages table...")
    cursor.execute("SHOW COLUMNS FROM messages LIKE 'group_id'")
    result = cursor.fetchone()
    if not result:
        cursor.execute("ALTER TABLE messages ADD COLUMN group_id INT NULL")
        cursor.execute("ALTER TABLE messages ADD FOREIGN KEY (group_id) REFERENCES `groups`(group_id) ON DELETE CASCADE")
        
    cursor.execute("ALTER TABLE messages MODIFY receiver_id INT NULL")
    
    conn.commit()
    cursor.close()
    conn.close()
    print("Migration successful!")

if __name__ == "__main__":
    migrate()
