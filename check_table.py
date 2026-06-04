from src.services.database import db
import sqlite3

conn = sqlite3.connect(db.db_path)
cursor = conn.cursor()

# 检查表是否存在
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='supply_order_details'")
result = cursor.fetchone()
print('表存在:', result is not None)

if result:
    cursor.execute("PRAGMA table_info(supply_order_details)")
    print('表结构:')
    for row in cursor.fetchall():
        print('  ', row)
    
    cursor.execute("SELECT COUNT(*) FROM supply_order_details")
    print('记录数:', cursor.fetchone()[0])

conn.close()
