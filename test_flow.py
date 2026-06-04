from src.auth.service import auth_service
from src.services.stock_flow import stock_flow_service

auth_service.load_token()

result = stock_flow_service.get_stock_flows(store_id=1, limit=10)

print('成功:', result.get('success'))
print('流水数:', len(result.get('flows', [])))

if result.get('flows'):
    for f in result['flows'][:3]:
        print(f"  门店: {f.get('store_name')}, 商品: {f.get('product_name')}, 数量: {f.get('quantity')}")
