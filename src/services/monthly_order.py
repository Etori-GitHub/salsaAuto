"""月订货统计服务

统计门店月度订货数据，按档口和类型汇总。
"""

from typing import Optional, Dict, List
from collections import defaultdict

from src.api.client import api_client
from src.services.database import db


class MonthlyOrderService:
    """月订货统计服务"""
    
    def query_supply_orders(
        self,
        store_code: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        page: int = 1,
        page_size: int = 100
    ) -> Dict:
        """查询单个门店的要货记录"""
        params = [
            ("page", page),
            ("pageSize", page_size),
            ("deliveryCode", ""),
            ("detailCode", ""),
            ("storeCode", store_code or ""),
            ("storeName", ""),
            ("categoryCode", ""),
            ("categoryName", ""),
            ("subCategoryCode", ""),
            ("subCategoryName", ""),
            ("cangSubCategoryName", ""),
            ("productCode", ""),
            ("productName", ""),
            ("deliveryId", ""),
            ("startTime", start_time or ""),
            ("endTime", end_time or ""),
        ]
        
        try:
            result = api_client.get_raw("supplyorders", params=params)
            
            if result.get("code") != 1:
                return {
                    "success": False,
                    "total": 0,
                    "records": [],
                    "message": result.get("msg", "API 返回错误")
                }
            
            data = result.get("data", {})
            
            return {
                "success": True,
                "total": data.get("total", 0),
                "records": data.get("records", []),
                "message": "OK"
            }
            
        except Exception as e:
            return {
                "success": False,
                "total": 0,
                "records": [],
                "message": str(e)
            }
    
    def query_all_supply_orders(
        self,
        store_code: str,
        start_time: str,
        end_time: str,
        page_size: int = 100
    ) -> Dict:
        """分页查询所有要货记录"""
        first_result = self.query_supply_orders(
            store_code=store_code,
            start_time=start_time,
            end_time=end_time,
            page=1,
            page_size=page_size
        )
        
        if not first_result["success"]:
            return first_result
        
        total = first_result["total"]
        if total == 0:
            return {"success": True, "total": 0, "records": [], "message": "OK"}
        
        total_pages = (total // page_size) + (1 if total % page_size > 0 else 0)
        all_records = first_result["records"]
        page = 2
        
        while page <= total_pages:
            result = self.query_supply_orders(
                store_code=store_code,
                start_time=start_time,
                end_time=end_time,
                page=page,
                page_size=page_size
            )
            
            if not result["success"]:
                page += 1
                continue
            
            records = result["records"]
            all_records.extend(records)
            
            if len(records) < page_size:
                break
            
            page += 1
        
        return {
            "success": True,
            "total": total,
            "records": all_records,
            "message": "OK"
        }
    
    def calculate_statistics(
        self,
        store_ids: List[str],
        start_time: str,
        end_time: str
    ) -> Dict:
        """计算月订货统计
        
        每个门店一行，档口和类型作为列横向展示
        """
        # 获取商品分类类型映射
        goods_sub_cates = db.get_goods_sub_cate()
        goods_cate_type_map = {}
        for c in goods_sub_cates:
            name = c.get("sub_category_name", "")
            cate_type = c.get("type", "")
            if name:
                goods_cate_type_map[name] = cate_type
        
        # 获取所有档口分类（用于列）
        cang_sub_cates = db.get_cang_sub_cate()
        all_cang_names = sorted([c.get("sub_category_name", "") for c in cang_sub_cates if c.get("sub_category_name")])
        
        # 获取门店名称映射
        from src.config import config
        stores = config.get("stores", {})
        store_name_map = {sid: s.get("name", "") for sid, s in stores.items()}
        
        # 结果数据
        store_stats = []  # 每个门店一行
        type_totals = defaultdict(float)  # 全局类型汇总
        cang_totals = defaultdict(float)  # 全局档口汇总
        total_amount = 0.0
        
        for store_id in store_ids:
            store_name = store_name_map.get(store_id, f"门店{store_id}")
            
            # 查询该门店的要货记录
            result = self.query_all_supply_orders(
                store_code=store_id,
                start_time=start_time,
                end_time=end_time
            )
            
            # 该门店的档口汇总和类型汇总
            store_cang_amounts = defaultdict(float)
            store_type_amounts = defaultdict(float)
            
            if result["success"]:
                records = result["records"]
                print(f"门店 {store_name}: {len(records)} 条记录")
                
                for r in records:
                    cang_name = r.get("cangSubCategoryName", "") or "未分类"
                    goods_cate_name = r.get("productSubcategoryName", "")
                    amount = float(r.get("totalPriceD", 0) or 0)
                    
                    # 获取类型
                    cate_type = goods_cate_type_map.get(goods_cate_name, "未分类")
                    
                    # 门店档口汇总
                    store_cang_amounts[cang_name] += amount
                    
                    # 门店类型汇总
                    store_type_amounts[cate_type] += amount
                    
                    # 全局汇总
                    cang_totals[cang_name] += amount
                    type_totals[cate_type] += amount
                    total_amount += amount
            else:
                print(f"门店 {store_name} 查询失败: {result['message']}")
            
            # 构建该门店的统计行
            store_row = {
                "store_id": store_id,
                "store_name": store_name,
                "food": round(store_type_amounts.get("食品", 0), 2),
                "non_food": round(store_type_amounts.get("非食品", 0), 2),
                "drink": round(store_type_amounts.get("饮料", 0), 2),
                "uncategorized": round(store_type_amounts.get("未分类", 0), 2),
                "total": round(sum(store_cang_amounts.values()), 2)
            }
            
            # 添加每个档口的金额
            for cang_name in all_cang_names:
                store_row[cang_name] = round(store_cang_amounts.get(cang_name, 0), 2)
            
            store_stats.append(store_row)
        
        # 类型统计
        type_stats = sorted(
            [{"type": k, "amount": round(v, 2)} for k, v in type_totals.items()],
            key=lambda x: x["amount"],
            reverse=True
        )
        
        # 档口统计
        cang_stats = sorted(
            [{"name": k, "amount": round(v, 2)} for k, v in cang_totals.items()],
            key=lambda x: x["amount"],
            reverse=True
        )
        
        return {
            "success": True,
            "store_stats": store_stats,  # 每个门店一行，档口作为列
            "cang_names": all_cang_names,  # 所有档口名称列表（用于表头）
            "cang_stats": cang_stats,  # 全局档口汇总
            "type_stats": type_stats,  # 全局类型统计
            "total_amount": round(total_amount, 2),
            "message": "OK"
        }


monthly_order_service = MonthlyOrderService()
