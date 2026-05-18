"""测试 API 查询"""

from src.api.client import api_client
from src.config import config

# 查询 2026-03-25
print("=== 查询 2026-03-25 ===")
params1 = [
    ('page', 1), ('pageSize', 500), ('storeCode', '11'),
    ('startTime', '2026-03-25'), ('endTime', '2026-03-25')
]
result1 = api_client.get_raw("/restful/shasha/supply/sordersDetail", params=params1)
if result1.get('code') == 1:
    records1 = result1.get('data', {}).get('records', [])
    print(f"记录数: {len(records1)}")
    if records1:
        print(f"deliveryCode: {records1[0].get('deliveryCode')}")
        print(f"storeName: {records1[0].get('storeName')}")
else:
    print(f"查询失败: {result1}")

print()

# 查询 2026-03-02
print("=== 查询 2026-03-02 ===")
params2 = [
    ('page', 1), ('pageSize', 500), ('storeCode', '11'),
    ('startTime', '2026-03-02'), ('endTime', '2026-03-02')
]
result2 = api_client.get_raw("/restful/shasha/supply/sordersDetail", params=params2)
if result2.get('code') == 1:
    records2 = result2.get('data', {}).get('records', [])
    print(f"记录数: {len(records2)}")
    if records2:
        print(f"deliveryCode: {records2[0].get('deliveryCode')}")
        print(f"storeName: {records2[0].get('storeName')}")
else:
    print(f"查询失败: {result2}")
