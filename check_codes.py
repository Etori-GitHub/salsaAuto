import sqlite3
conn = sqlite3.connect('data/orders.db')
cursor = conn.cursor()

# 检查 G00011 是否在供应商表
cursor.execute("SELECT supplier_code, supplier_name FROM suppliers WHERE supplier_code = 'G00011'")
result = cursor.fetchall()
print(f'G00011 in suppliers: {result}')

# 检查供应商表里有哪些 G000xx 编码
cursor.execute("SELECT supplier_code FROM suppliers ORDER BY supplier_code LIMIT 20")
print('\n供应商编码 (前20):')
for row in cursor.fetchall():
    print(f'  {row[0]}')

# 检查商品表里有但供应商表里没有的编码
cursor.execute('''
SELECT DISTINCT g.supplier_code 
FROM goods g 
WHERE g.supplier_code NOT IN (SELECT supplier_code FROM suppliers)
LIMIT 10
''')
print('\n商品表有但供应商表没有的编码:')
for row in cursor.fetchall():
    print(f'  {row[0]}')

conn.close()