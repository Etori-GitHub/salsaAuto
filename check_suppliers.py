import sqlite3
conn = sqlite3.connect('data/orders.db')
cursor = conn.cursor()

# 检查供应商表的汇总主体分布
cursor.execute('SELECT summary_entity, COUNT(*) FROM suppliers GROUP BY summary_entity')
print('汇总主体分布:')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]}')

# 检查外部供应商下的供应商
cursor.execute("SELECT supplier_code, supplier_name FROM suppliers WHERE summary_entity = '外部供应商'")
print('\n外部供应商下的供应商:')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]}')

# 检查商品的 supplier_code 和 supplier_name 对应关系
cursor.execute('''
SELECT DISTINCT g.supplier_code, g.supplier_name 
FROM goods g 
WHERE g.category_name = '贸易品' 
AND g.supplier_code IN (
  SELECT supplier_code FROM suppliers WHERE summary_entity = '外部供应商'
)
LIMIT 10
''')
print('\n外部供应商+贸易品的商品:')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]}')

conn.close()
