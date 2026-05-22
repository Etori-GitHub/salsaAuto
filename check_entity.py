import sqlite3
conn = sqlite3.connect('data/orders.db')
cursor = conn.cursor()

# 检查论外主体下的供应商
cursor.execute("SELECT supplier_code, supplier_name FROM suppliers WHERE summary_entity = '论外主体'")
print('论外主体下的供应商:')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]}')

# 检查这些供应商在商品库里有没有贸易品
cursor.execute('''
SELECT s.supplier_code, s.supplier_name, COUNT(g.id) as goods_count
FROM suppliers s
LEFT JOIN goods g ON g.supplier_code = s.supplier_code AND g.category_name = '贸易品'
WHERE s.summary_entity = '论外主体'
GROUP BY s.supplier_code
''')
print('\n论外主体供应商的贸易品数量:')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]} ({row[2]}个贸易品)')

conn.close()