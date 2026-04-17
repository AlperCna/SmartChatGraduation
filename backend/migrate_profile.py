"""
Migration: users tablosuna profile_picture ve about alanları ekler.
Kullanım: python backend/migrate_profile.py
"""
import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()

def migrate():
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "smartchat"),
        port=int(os.getenv("DB_PORT", 3306))
    )
    cursor = conn.cursor()

    # profile_picture alanı
    try:
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN profile_picture VARCHAR(255) DEFAULT NULL
        """)
        print("[OK] profile_picture kolonu eklendi.")
    except mysql.connector.errors.ProgrammingError as e:
        if "Duplicate column" in str(e):
            print("[INFO] profile_picture kolonu zaten mevcut.")
        else:
            raise e

    # about alanı
    try:
        cursor.execute("""
            ALTER TABLE users 
            ADD COLUMN about VARCHAR(255) DEFAULT 'Merhaba, SmartChat kullanıyorum!'
        """)
        print("[OK] about kolonu eklendi.")
    except mysql.connector.errors.ProgrammingError as e:
        if "Duplicate column" in str(e):
            print("[INFO] about kolonu zaten mevcut.")
        else:
            raise e

    conn.commit()
    cursor.close()
    conn.close()
    print("[DONE] Migration tamamlandi!")

if __name__ == "__main__":
    migrate()
