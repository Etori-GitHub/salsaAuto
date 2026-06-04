"""订单查询服务

从平台 API 查询订单（订单级别，非订单明细）
"""

from typing import Optional, Dict, List
from src.api.client import api_client


class OrderService:
    """订单查询服务"""

    def query_orders(
        self,
        page: int = 1,
        page_size: int = 15,
        order_code: Optional[str] = None,
        store_id: Optional[int] = None,
        pay_channel: Optional[str] = None
    ) -> Dict:
        """查询订单列表

        Args:
            page: 页码
            page_size: 每页数量
            order_code: 订单号
            store_id: 门店ID
            pay_channel: 支付渠道
        """
        params = [
            ("page", page),
            ("pageSize", page_size),
            ("orderCode", order_code or ""),
            ("storeId", store_id if store_id else ""),
            ("payChannel", pay_channel or ""),
        ]

        try:
            result = api_client.get_raw("/restful/shasha/orders/orderinfo", params=params)

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

    def get_pay_channels(self) -> List[Dict]:
        """获取支付渠道列表（从字典配置）

        Returns:
            [{"key": "抖音团购", "value": "抖音团购"}, ...]
        """
        params = [
            ("page", 1),
            ("pageSize", 100),  # 获取足够多
        ]

        try:
            result = api_client.get_raw("/restful/shasha/dict/dict", params=params)

            if result.get("code") != 1:
                return []

            # data 是字典格式，如 {"21": {...}, "22": {...}}
            data = result.get("data", {})

            channels = []
            for item in data.values():
                if item.get("dictType") == "paychannel" and item.get("status") == 1:
                    channels.append({
                        "key": item.get("dictKey"),
                        "value": item.get("dictValue")
                    })

            return channels

        except Exception as e:
            print(f"获取支付渠道失败: {e}")
            return []


order_service_v2 = OrderService()
