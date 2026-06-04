from src.auth.service import auth_service
from src.services.consume_query import consume_query_service

auth_service.load_token()

# 测试带时间参数查询
result = consume_query_service.query_consume_records(
    start_time="2026-01-01",
    page=1,
    page_size=5
)

print('查询结果:', result.get('success'))
print('总数:', result.get('total'))
print('记录数:', len(result.get('records', [])))

if result.get('records'):
    for r in result['records'][:3]:
        print(f"  usedTime: {r.get('usedTime')}")