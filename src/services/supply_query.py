"""要货查询服务

从平台 API 查询门店要货记录。
"""

from typing import Optional, Dict, List

from src.api.client import api_client


class SupplyQueryService:
    """要货查询服务"""
    
    def query_supply_orders(
        self,
        store_code: Optional[str] = None,
        store_name: Optional[str] = None,
        category_code: Optional[str] = None,
        category_name: Optional[str] = None,
        sub_category_code: Optional[str] = None,
        sub_category_name: Optional[str] = None,
        cang_sub_category_name: Optional[str] = None,
        product_code: Optional[str] = None,
        product_name: Optional[str] = None,
        delivery_code: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        page: int = 1,
        page_size: int = 100
    ) -> Dict:
        """查询要货记录"""
        # API 返回的 storeCode 格式是 M00011，需要转换
        api_store_code = None
        if store_code:
            api_store_code = f"M{store_code.zfill(5)}" if not store_code.startswith("M") else store_code
        
        params = [
            ("page", page),
            ("pageSize", page_size),
            ("deliveryCode", delivery_code or ""),
            ("detailCode", ""),
            ("storeCode", api_store_code or ""),
            ("storeName", store_name or ""),
            ("categoryCode", category_code or ""),
            ("categoryName", category_name or ""),
            ("subCategoryCode", sub_category_code or ""),
            ("subCategoryName", sub_category_name or ""),
            ("cangSubCategoryName", cang_sub_category_name or ""),
            ("productCode", product_code or ""),
            ("productName", product_name or ""),
            ("deliveryId", ""),
        ]
        
        # 时间参数用 createTime（同名参数传两次）
        if start_time:
            params.append(("createTime", f"{start_time} 00:00:00"))
        if end_time:
            params.append(("createTime", f"{end_time} 23:59:59"))
        
        try:
            result = api_client.get_raw("supplyorders", params=params)
            
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
    
    def query_all_supply_orders(
        self,
        store_code: Optional[str] = None,
        store_name: Optional[str] = None,
        cang_sub_category_name: Optional[str] = None,
        category_name: Optional[str] = None,
        product_name: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        page_size: int = 10000
    ) -> Dict:
        """分页查询所有要货记录"""
        # 第一次查询获取总数
        first_result = self.query_supply_orders(
            store_code=store_code,
            store_name=store_name,
            cang_sub_category_name=cang_sub_category_name,
            category_name=category_name,
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
        print(f"查询要货记录: 总数 {total}, 页数 {total_pages}")
        
        # 拉取所有数据
        all_records = first_result["records"]
        page = 2
        
        while page <= total_pages:
            result = self.query_supply_orders(
                store_code=store_code,
                store_name=store_name,
                cang_sub_category_name=cang_sub_category_name,
                category_name=category_name,
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
        
        print(f"查询完成: 共拉取 {len(all_records)} 条记录")
        
        return {
            "success": True,
            "total": total,
            "records": all_records,
            "message": "OK"
        }


supply_query_service = SupplyQueryService()