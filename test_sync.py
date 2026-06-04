"""测试同步功能"""

import time
from src.auth.service import auth_service
from src.api.client import api_client
from src.services.supply_query import supply_query_service
from src.services.consume_query import consume_query_service

# 加载 Token
print("加载 Token...")
auth_service.load_token()
print(f"Token 已加载: {api_client.get_token() is not None}")

# 测试要货查询 - 11万条数据，测试大 pagesize
print("\n" + "=" * 50)
print("测试要货查询 API (pageSize=10000)...")
print("=" * 50)
start = time.time()
result = supply_query_service.query_supply_orders(page_size=10000)
end = time.time()

print(f"耗时: {end - start:.2f} 秒")
print(f"成功: {result.get('success')}")
print(f"总记录数: {result.get('total', 0)}")
print(f"返回记录数: {len(result.get('records', []))}")

# 测试耗用查询 - 查不到数据的问题
print("\n" + "=" * 50)
print("测试耗用查询 API (不传时间参数)...")
print("=" * 50)
start = time.time()
result2 = consume_query_service.query_consume_records(page_size=100)
end = time.time()

print(f"耗时: {end - start:.2f} 秒")
print(f"成功: {result2.get('success')}")
print(f"总记录数: {result2.get('total', 0)}")
print(f"返回记录数: {len(result2.get('records', []))}")
if result2.get('message'):
    print(f"消息: {result2.get('message')}")
