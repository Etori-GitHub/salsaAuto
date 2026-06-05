"""耗用操作服务

创建耗用记录并同步到平台。
"""

import json
import urllib.parse
from typing import Dict, List, Optional
from datetime import datetime

from src.api.client import api_client
from src.services.database import db


class ConsumeService:
    """耗用操作服务"""
    
    def create_consume_record(
        self,
        store_id: int,
        product_id: int,
        quantity: float,
        consume_time: str,
        category_id: int = None,
        sub_category_id: int = None
    ) -> Dict:
        """创建耗用记录
        
        Args:
            store_id: 门店ID
            product_id: 商品ID
            quantity: 耗用数量
            consume_time: 耗用时间（格式：2026-06-04 10:43:29）
            category_id: 分类ID（可选，会从商品库查询）
            sub_category_id: 子分类ID（可选，会从商品库查询）
        
        Returns:
            API 响应结果
        """
        # 如果没有传入分类ID，从商品库查询
        if category_id is None or sub_category_id is None:
            goods_info = db.get_goods_by_ids([product_id])
            goods = goods_info.get(product_id, {})
            category_id = goods.get("category_id", "")
            sub_category_id = goods.get("sub_category_id", "")
        
        # productIdStr 格式：[category_id, sub_category_id, product_id]
        product_id_str = json.dumps([str(category_id), str(sub_category_id), str(product_id)])
        
        # 构建表单数据
        data = {
            "storeId": store_id,
            "productIdStr": product_id_str,
            "used": quantity,
            "createTime": consume_time
        }
        
        print(f"[DEBUG] 创建耗用请求参数: {data}")
        
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
                product_id=record["product_id"],
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
