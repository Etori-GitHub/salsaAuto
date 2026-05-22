import sqlite3
conn = sqlite3.connect('data/orders.db')
cursor = conn.cursor()

# 检查商品库的 supplier_code
cursor.execute("SELECT supplier_code, supplier_name, COUNT(*) FROM goods WHERE category_name = '贸易品' GROUP BY supplier_code ORDER BY COUNT(*) DESC LIMIT 10")
print('贸易品供应商分布:')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]} ({row[2]}个)')

conn.close()