"""订单查询服务

从平台 API 实时查询订单数据，供分析使用。
"""

from datetime import datetime
from typing import Optional, Dict

from src.api.client import api_client


class OrderQueryService:
    """订单查询服务"""
    
    def query_orders(
        self,
        store_id: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        order_code: Optional[str] = None,
        dish_code: Optional[str] = None,
        dish_name: Optional[str] = None,
        page: int = 1,
        page_size: int = 100
    ) -> Dict:
        """从 API 查询订单"""
        # 构建参数
        params = [
            ("page", page),
            ("pageSize", page_size),
            ("orderCode", order_code or ""),
            ("dishCode", dish_code or ""),
            ("dishName", dish_name or ""),
            ("storeCode", ""),
            ("storeId", store_id if store_id else ""),
            ("memberCode", ""),
            ("username", ""),
            ("phone", ""),
            ("payChannel", ""),
            ("orderId", ""),
        ]
        
        # 时间参数（数组形式）
        if start_time and end_time:
            params.append(("createTime", start_time))
            params.append(("createTime", end_time))
        elif start_time:
            params.append(("createTime", start_time))
            params.append(("createTime", "2099-12-31 23:59:59"))
        elif end_time:
            params.append(("createTime", "2000-01-01 00:00:00"))
            params.append(("createTime", end_time))
        
        # 调用 API
        try:
            result = api_client.get_raw("orderdish", params=params)
            
            if result.get("code") != 1:
                return {
                    "success": False,
                    "total": 0,
                    "pages": 0,
                    "current": page,
                    "records": [],
                    "message": result.get("msg", "API 返回错误")
                }
            
            data = result.get("data", {})
            
            return {
                "success": True,
                "total": data.get("total", 0),
                "pages": data.get("pages", 0),
                "current": data.get("current", page),
                "records": data.get("records", []),
                "message": "OK"
            }
            
        except Exception as e:
            return {
                "success": False,
                "total": 0,
                "pages": 0,
                "current": page,
                "records": [],
                "message": str(e)
            }
    
    def query_all_orders(
        self,
        store_id: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        page_size: int = 100
    ) -> Dict:
        """分页查询所有订单
        
        先查询一次获取总数，再根据总数计算需要拉取的页数
        """
        # 第一次查询：获取总数
        first_result = self.query_orders(
            store_id=store_id,
            start_time=start_time,
            end_time=end_time,
            page=1,
            page_size=page_size
        )
        
        if not first_result["success"]:
            return first_result
        
        total = first_result["total"]
        if total == 0:
            return {
                "success": True,
                "total": 0,
                "records": [],
                "message": "OK"
            }
        
        # 计算需要的页数
        total_pages = (total // page_size) + (1 if total % page_size > 0 else 0)
        print(f"查询订单: 总数 {total}, 页数 {total_pages}")
        
        # 开始拉取所有数据
        all_records = first_result["records"]
        page = 2
        
        while page <= total_pages:
            result = self.query_orders(
                store_id=store_id,
                start_time=start_time,
                end_time=end_time,
                page=page,
                page_size=page_size
            )
            
            if not result["success"]:
                print(f"查询第 {page} 页失败: {result['message']}")
                page += 1
                continue
            
            records = result["records"]
            all_records.extend(records)
            
            if len(records) < page_size:
                break
            
            page += 1
        
        print(f"查询完成: 共拉取 {len(all_records)} 条记录")
        
        return {
            "success": True,
            "total": total,
            "records": all_records,
            "message": "OK"
        }


order_query_service = OrderQueryService()