import sqlite3
conn = sqlite3.connect('data/orders.db')
cursor = conn.cursor()

# 检查论外主体下的贸易品价格
cursor.execute('''
SELECT g.id, g.product_name, g.unit_price, g.supplier_name, g.cang_sub_category_name
FROM goods g
JOIN suppliers s ON g.supplier_code = s.supplier_code
WHERE s.summary_entity = '论外主体'
AND g.category_name = '贸易品'
ORDER BY g.unit_price ASC
LIMIT 50
''')
print('论外主体的贸易品 (按价格排序):')
for row in cursor.fetchall():
    print(f'  ID={row[0]}, 价格={row[2]}, 名称={row[1]}, 档口={row[4]}')

conn.close()