"""耗用查询服务

从平台 API 查询门店耗用记录。
"""

import json
from typing import Optional, Dict, List

from src.api.client import api_client


class ConsumeQueryService:
    """耗用查询服务"""
    
    def query_consume_records(
        self,
        store_id: Optional[int] = None,
        store_name: Optional[str] = None,
        category_code: Optional[str] = None,
        category_name: Optional[str] = None,
        sub_category_code: Optional[str] = None,
        sub_category_name: Optional[str] = None,
        product_code: Optional[str] = None,
        product_name: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        page: int = 1,
        page_size: int = 100
    ) -> Dict:
        """查询耗用记录
        
        Args:
            store_id: 门店ID（直接传整数ID）
            store_name: 门店名称
            category_code: 分类编码
            category_name: 分类名称
            sub_category_code: 子分类编码
            sub_category_name: 子分类名称
            product_code: 商品编码
            product_name: 商品名称
            start_time: 开始时间
            end_time: 结束时间
            page: 页码
            page_size: 每页数量
        
        Returns:
            API 响应结果
        """
        # API 参数使用 storeCode（根据原始 API 文档）
        # storeCode 格式可能是 M00008 或直接传空字符串获取全部
        store_code_param = ""
        if store_id:
            # 尝试两种格式：整数 ID 或 M00008 格式
            store_code_param = str(store_id)  # 先试试直接用整数
        
        params = [
            ("page", page),
            ("pageSize", page_size),
            ("storeCode", store_code_param),
            ("storeName", store_name or ""),
            ("categoryCode", category_code or ""),
            ("categoryName", category_name or ""),
            ("subCategoryCode", sub_category_code or ""),
            ("subCategoryName", sub_category_name or ""),
            ("productCode", product_code or ""),
            ("productName", product_name or ""),
        ]
        
        # 打印调试信息
        from src.config import config
        debug_url = f"{config.api_base_url}/restful/shasha/supply/storeConsume"
        print(f"[DEBUG] 耗用 API URL: {debug_url}")
        print(f"[DEBUG] 参数: {params}")
        
        # 时间参数 - 使用正确的参数名
        if start_time:
            params.append(("startTime", f"{start_time} 00:00:00"))
        if end_time:
            params.append(("endTime", f"{end_time} 23:59:59"))
        
        try:
            result = api_client.get_raw("/restful/shasha/supply/storeConsume", params=params)
            
            # 打印 API 响应
            print(f"[DEBUG] 耗用 API 响应: {result}")
            
            # 打印第一条记录的结构
            data = result.get("data", {})
            records = data.get("records", [])
            if records:
                print(f"[DEBUG] 第一条耗用记录: {json.dumps(records[0], ensure_ascii=False, indent=2)}")
            
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
    
    def query_all_consume_records(
        self,
        store_id: Optional[int] = None,
        store_name: Optional[str] = None,
        category_name: Optional[str] = None,
        sub_category_name: Optional[str] = None,
        product_name: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        page_size: int = 10000
    ) -> Dict:
        """分页查询所有耗用记录
        
        Args:
            同 query_consume_records
        
        Returns:
            所有记录的汇总结果
        """
        # 第一次查询获取总数
        first_result = self.query_consume_records(
            store_id=store_id,
            store_name=store_name,
            category_name=category_name,
            sub_category_name=sub_category_name,
            product_name=product_name,
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
        
        # 计算页数
        total_pages = (total // page_size) + (1 if total % page_size > 0 else 0)
        print(f"查询耗用记录: 总数 {total}, 页数 {total_pages}")
        
        # 拉取所有数据
        all_records = first_result["records"]
        page = 2
        
        while page <= total_pages:
            result = self.query_consume_records(
                store_id=store_id,
                store_name=store_name,
                category_name=category_name,
                sub_category_name=sub_category_name,
                product_name=product_name,
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
        
        print(f"查询完成: 共拉取 {len(all_records)} 条耗用记录")
        
        return {
            "success": True,
            "total": total,
            "records": all_records,
            "message": "OK"
        }
    
    def parse_consume_record(self, record: Dict) -> Dict:
        """解析单条耗用记录，提取关键字段
        
        Args:
            record: API 返回的原始记录
        
        Returns:
            解析后的记录
        """
        stores = record.get("stores", {})
        product = record.get("supProduct", {})
        used = record.get("used", {})
        
        # 打印调试信息
        print(f"[DEBUG] 耗用记录原始数据: used={used}, product={product}")
        
        # 解析 used 数量
        used_quantity = 0
        if isinstance(used, dict):
            used_quantity = used.get("parsedValue", 0) or float(used.get("source", "0") or 0)
        elif isinstance(used, (int, float)):
            used_quantity = used
        
        unit_price = product.get("unitPrice", 0) or 0
        
        print(f"[DEBUG] 解析结果: used_quantity={used_quantity}, unit_price={unit_price}")
        
        return {
            "id": record.get("id"),
            "store_id": stores.get("id"),
            "store_name": stores.get("storeName", ""),
            "product_id": record.get("productId"),  # 从 record 顶层获取
            "product_code": product.get("productCode", ""),
            "product_name": product.get("productName", ""),
            "category_code": product.get("categoryCode", ""),
            "category_name": product.get("categoryName", ""),
            "sub_category_code": product.get("subCategoryCode", ""),
            "sub_category_name": product.get("subCategoryName", ""),
            "cang_sub_category_code": product.get("cangSubCategoryCode", ""),
            "cang_sub_category_name": product.get("cangSubCategoryName", ""),
            "spec_name": product.get("specName", ""),
            "unit": product.get("unit", ""),
            "unit_price": unit_price,
            "quantity": used_quantity,
            "total_amount": used_quantity * unit_price,
            "used_time": record.get("usedTime", ""),
            "used_source": record.get("usedSource", ""),
            "used_by": record.get("usedBy"),
            "create_time": record.get("createTime", ""),
        }


consume_query_service = ConsumeQueryService()