"""耗用操作服务

创建耗用记录并同步到平台。
"""

import json
import urllib.parse
from typing import Dict, List, Optional
from datetime import datetime

from src.api.client import api_client


class ConsumeService:
    """耗用操作服务"""
    
    def create_consume_record(
        self,
        store_id: int,
        product_ids: List[int],
        quantity: float,
        consume_time: str
    ) -> Dict:
        """创建耗用记录
        
        Args:
            store_id: 门店ID
            product_ids: 商品ID列表
            quantity: 耗用数量
            consume_time: 耗用时间（格式：2026-06-04 10:43:29）
        
        Returns:
            API 响应结果
        """
        # 将商品ID列表转为 JSON 字符串
        product_id_str = json.dumps([str(pid) for pid in product_ids])
        
        # 构建表单数据
        data = {
            "storeId": store_id,
            "productIdStr": product_id_str,
            "used": quantity,
            "createTime": consume_time
        }
        
        try:
            # 使用 form 表单方式提交
            result = api_client.post_form("/restful/shasha/supply/storeConsume", data=data)
            print(f"创建耗用记录 API 响应: {result}")
            
            if result.get("code") == 1:
                return {"success": True, "message": "创建成功", "data": result.get("data")}
            else:
                return {"success": False, "message": result.get("msg", "创建失败")}
                
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def batch_create_consume_records(self, records: List[Dict]) -> Dict:
        """批量创建耗用记录
        
        Args:
            records: 耗用记录列表，每条记录包含：
                - store_id: 门店ID
                - product_id: 商品ID
                - quantity: 耗用数量
                - consume_time: 耗用时间
        
        Returns:
            批量创建结果
        """
        success_count = 0
        failed_count = 0
        errors = []
        
        for record in records:
            result = self.create_consume_record(
                store_id=record["store_id"],
                product_ids=[record["product_id"]],
                quantity=record["quantity"],
                consume_time=record["consume_time"]
            )
            
            if result["success"]:
                success_count += 1
            else:
                failed_count += 1
                errors.append({
                    "record": record,
                    "error": result["message"]
                })
        
        return {
            "success": failed_count == 0,
            "success_count": success_count,
            "failed_count": failed_count,
            "errors": errors[:10],  # 只返回前10个错误
            "message": f"成功 {success_count} 条，失败 {failed_count} 条"
        }


consume_service = ConsumeService()
