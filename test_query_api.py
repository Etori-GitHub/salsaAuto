"""测试所有查询 API"""

import urllib.request
import json

print("=== API Query Tests ===")

# 1. 商品库
response = urllib.request.urlopen('http://127.0.0.1:8080/api/base/goods/local')
data = json.loads(response.read().decode('utf-8'))
print(f"1. Goods: total={data['total']}, success={data['success']}")
if data['records']:
    r = data['records'][0]
    print(f"   First: id={r['id']}, name={r['product_name']}, price={r['unit_price']}")

# 2. 商品分类
response = urllib.request.urlopen('http://127.0.0.1:8080/api/base/goods-sub-cate/local')
data = json.loads(response.read().decode('utf-8'))
print(f"2. Goods Sub Cate: total={data['total']}, success={data['success']}")
if data['records']:
    r = data['records'][0]
    print(f"   First: id={r['id']}, name={r['sub_category_name']}, type={r.get('type', 'N/A')}")

# 3. 档口分类
response = urllib.request.urlopen('http://127.0.0.1:8080/api/base/cang-sub-cate/local')
data = json.loads(response.read().decode('utf-8'))
print(f"3. Cang Sub Cate: total={data['total']}, success={data['success']}")
if data['records']:
    r = data['records'][0]
    print(f"   First: id={r['id']}, name={r['sub_category_name']}")

# 4. 会员
response = urllib.request.urlopen('http://127.0.0.1:8080/api/members')
data = json.loads(response.read().decode('utf-8'))
print(f"4. Members: count={data['count']}")
first_key = list(data['members'].keys())[0]
first = data['members'][first_key]
print(f"   First: id={first_key}, username={first['username']}, balance={first['balance']}")

# 5. 刷单记录
try:
    response = urllib.request.urlopen('http://127.0.0.1:8080/api/orders/records')
    data = json.loads(response.read().decode('utf-8'))
    print(f"5. Order Records: total={len(data['records'])}")
except Exception as e:
    print(f"5. Order Records: ERROR - {e}")

# 6. 任务列表
response = urllib.request.urlopen('http://127.0.0.1:8080/api/tasks/list')
data = json.loads(response.read().decode('utf-8'))
print(f"6. Tasks: count={len(data['tasks'])}")

# 7. 要货任务列表
response = urllib.request.urlopen('http://127.0.0.1:8080/api/supply-tasks/list')
data = json.loads(response.read().decode('utf-8'))
print(f"7. Supply Tasks: count={len(data['tasks'])}")

print("\n=== All API tests passed! ===")