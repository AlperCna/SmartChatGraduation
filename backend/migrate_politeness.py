import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

def migrate():
    print("Connecting to database...")
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "smartchat"),
            port=int(os.getenv("DB_PORT", 3306)),
            auth_plugin='mysql_native_password'
        )
        cursor = conn.cursor()

        print("Checking for politeness_score column in user_relationships table...")
        cursor.execute("SHOW COLUMNS FROM user_relationships")
        columns = [column[0] for column in cursor.fetchall()]

        if "politeness_score" not in columns:
            print("Adding politeness_score column to user_relationships table...")
            cursor.execute("ALTER TABLE user_relationships ADD COLUMN politeness_score INT DEFAULT 50")
            conn.commit()
            print("Column added successfully!")
        else:
            print("politeness_score column already exists. No migration needed.")

        print("Fixing style column length for suggestions and user_relationships tables...")
        cursor.execute("ALTER TABLE suggestions MODIFY COLUMN style VARCHAR(100)")
        cursor.execute("ALTER TABLE user_relationships MODIFY COLUMN style VARCHAR(100)")
        conn.commit()

        cursor.close()
        conn.close()
        print("Migration process finished.")
    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    migrate()
