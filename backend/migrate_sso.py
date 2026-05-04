import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import mysql.connector
from dotenv import load_dotenv

load_dotenv(override=True)

conn = mysql.connector.connect(
    host=os.getenv("DB_HOST", "localhost"),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", "bc748596"),
    database=os.getenv("DB_NAME", "smartchat"),
    port=int(os.getenv("DB_PORT", 3306))
)
cursor = conn.cursor()

migrations = [
    "ALTER TABLE users ADD COLUMN sso_provider VARCHAR(50) DEFAULT NULL",
    "ALTER TABLE users ADD COLUMN sso_id VARCHAR(255) DEFAULT NULL",
    "ALTER TABLE users MODIFY COLUMN password_hash VARCHAR(255) DEFAULT NULL",
]

for sql in migrations:
    try:
        cursor.execute(sql)
        print(f"✓ {sql}")
    except mysql.connector.Error as e:
        if e.errno == 1060:  # Duplicate column name — already exists, skip
            print(f"⚠ ALREADY EXISTS, skipping: {sql}")
        else:
            print(f"✗ ERROR ({e})")

conn.commit()
cursor.close()
conn.close()
print("\nSSO migration tamamlandı.")
