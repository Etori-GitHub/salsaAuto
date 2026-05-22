"""基础库查询服务

从平台 API 查询商品库、档口分类等基础数据。
"""

import json
from pathlib import Path
from typing import Optional, Dict, List

from src.api.client import api_client
from src.services.database import db


class BaseLibraryService:
    """基础库查询服务"""
    
    def query_product_sub_cate(self, page: int = 1, page_size: int = 100) -> Dict:
        """查询档口分类（仓库分类）"""
        params = [
            ("page", page),
            ("pageSize", page_size),
            ("categoryCode", ""),
            ("categoryName", ""),
            ("subCategoryCode", ""),
            ("subCategoryName", ""),
            ("categoryId", ""),
        ]
        
        try:
            result = api_client.get_raw("productsubcate", params=params)
            
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
    
    def query_all_product_sub_cate(self) -> Dict:
        """查询所有档口分类"""
        result = self.query_product_sub_cate(page=1, page_size=100)
        
        if not result["success"]:
            return result
        
        return {
            "success": True,
            "total": result["total"],
            "records": result["records"],
            "message": "OK"
        }
    
    def query_goods_sub_cate(self, page: int = 1, page_size: int = 100) -> Dict:
        """查询商品分类"""
        params = [
            ("page", page),
            ("pageSize", page_size),
            ("categoryCode", ""),
            ("categoryName", ""),
            ("subCategoryCode", ""),
            ("subCategoryName", ""),
            ("categoryId", ""),
        ]
        
        try:
            result = api_client.get_raw("goodssubcate", params=params)
            
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
    
    def query_all_goods_sub_cate(self) -> Dict:
        """查询所有商品分类"""
        result = self.query_goods_sub_cate(page=1, page_size=100)
        
        if not result["success"]:
            return result
        
        return {
            "success": True,
            "total": result["total"],
            "records": result["records"],
            "message": "OK"
        }
    
    def query_goods(self, page: int = 1, page_size: int = 100) -> Dict:
        """查询商品库"""
        params = [
            ("page", page),
            ("pageSize", page_size),
            ("categoryCode", ""),
            ("categoryName", ""),
            ("subCategoryCode", ""),
            ("subCategoryName", ""),
            ("cangSubCategoryCode", ""),
            ("cangSubCategoryName", ""),
            ("shopcode", ""),
            ("productName", ""),
            ("productCode", ""),
            ("productId", ""),
        ]
        
        try:
            result = api_client.get_raw("goods", params=params)
            
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
    
    def query_all_goods(self) -> Dict:
        """查询所有商品（分页拉取）"""
        # 第一次查询获取总数
        first_result = self.query_goods(page=1, page_size=100)
        
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
        total_pages = (total // 100) + (1 if total % 100 > 0 else 0)
        print(f"查询商品库: 总数 {total}, 页数 {total_pages}")
        
        # 开始拉取所有数据
        all_records = first_result["records"]
        page = 2
        
        while page <= total_pages:
            result = self.query_goods(page=page, page_size=100)
            
            if not result["success"]:
                print(f"查询第 {page} 页失败: {result['message']}")
                page += 1
                continue
            
            records = result["records"]
            all_records.extend(records)
            
            if len(records) < 100:
                break
            
            page += 1
        
        print(f"查询完成: 共拉取 {len(all_records)} 条商品记录")
        
        return {
            "success": True,
            "total": total,
            "records": all_records,
            "message": "OK"
        }
    
    def update_goods_config(self) -> Dict:
        """更新本地商品配置"""
        result = self.query_all_goods()
        
        if not result["success"]:
            return result
        
        records = result["records"]
        
        # 同步到数据库
        count = db.sync_goods(records)
        
        # 同时更新 JSON 配置
        new_goods = {}
        for record in records:
            product_id = record.get("id")
            product_name = record.get("productName", "")
            unit_price = record.get("unitPrice", 0) or record.get("truePrice", 0)
            unit = record.get("unit", "")
            spec_name = record.get("specName", "")
            
            if product_id:
                new_goods[str(product_id)] = {
                    "name": product_name,
                    "price": float(unit_price) if unit_price else 0,
                    "unit": unit,
                    "spec": spec_name,
                    "code": record.get("productCode", ""),
                    "category": record.get("categoryName", ""),
                    "sub_category": record.get("subCategoryName", ""),
                    "cang_sub_category": record.get("cangSubCategoryName", ""),
                }
        
        config_path = Path(__file__).parent.parent.parent / "config" / "goods.json"
        
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(new_goods, f, indent=2, ensure_ascii=False)
            
            return {
                "success": True,
                "total": count,
                "message": f"已同步 {count} 个商品到数据库",
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": str(e)
            }
    
    def update_cang_sub_cate_config(self) -> Dict:
        """更新本地档口分类配置"""
        result = self.query_all_product_sub_cate()
        
        if not result["success"]:
            return result
        
        records = result["records"]
        
        # 同步到数据库
        count = db.sync_cang_sub_cate(records)
        
        # 同时更新 JSON 配置
        new_cates = {}
        for record in records:
            cate_id = record.get("id")
            cate_name = record.get("subCategoryName", "")
            cate_code = record.get("subCategoryCode", "")
            
            if cate_id:
                new_cates[str(cate_id)] = {
                    "name": cate_name,
                    "code": cate_code,
                    "category_id": record.get("categoryId"),
                    "category_name": record.get("categoryName", ""),
                }
        
        config_path = Path(__file__).parent.parent.parent / "config" / "cang_sub_cate.json"
        
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(new_cates, f, indent=2, ensure_ascii=False)
            
            return {
                "success": True,
                "total": count,
                "message": f"已同步 {count} 个档口分类到数据库"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": str(e)
            }
    
    def update_goods_sub_cate_config(self) -> Dict:
        """更新本地商品分类配置"""
        result = self.query_all_goods_sub_cate()
        
        if not result["success"]:
            return result
        
        records = result["records"]
        
        # 同步到数据库
        count = db.sync_goods_sub_cate(records)
        
        # 同时更新 JSON 配置
        new_cates = {}
        for record in records:
            cate_id = record.get("id")
            cate_name = record.get("subCategoryName", "")
            cate_code = record.get("subCategoryCode", "")
            
            if cate_id:
                new_cates[str(cate_id)] = {
                    "name": cate_name,
                    "code": cate_code,
                    "category_id": record.get("categoryId"),
                    "category_name": record.get("categoryName", ""),
                }
        
        config_path = Path(__file__).parent.parent.parent / "config" / "goods_sub_cate.json"
        
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(new_cates, f, indent=2, ensure_ascii=False)
            
            return {
                "success": True,
                "total": count,
                "message": f"已同步 {count} 个商品分类到数据库"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": str(e)
            }
    
    def query_suppliers(self, page: int = 1, page_size: int = 100) -> Dict:
        """查询供应商"""
        params = [
            ("page", page),
            ("pageSize", page_size),
            ("supplierCode", ""),
            ("supplierName", ""),
            ("phone", ""),
        ]
        
        try:
            result = api_client.get_raw("/restful/shasha/supply/supplys", params=params)
            print(f"供应商 API 响应: {result}")
            
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
    
    def query_all_suppliers(self) -> Dict:
        """查询所有供应商"""
        first_result = self.query_suppliers(page=1, page_size=100)
        
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
        
        total_pages = (total // 100) + (1 if total % 100 > 0 else 0)
        print(f"查询供应商: 总数 {total}, 页数 {total_pages}")
        
        all_records = first_result["records"]
        page = 2
        
        while page <= total_pages:
            result = self.query_suppliers(page=page, page_size=100)
            
            if not result["success"]:
                print(f"查询第 {page} 页失败: {result['message']}")
                page += 1
                continue
            
            records = result["records"]
            all_records.extend(records)
            
            if len(records) < 100:
                break
            
            page += 1
        
        print(f"查询完成: 共拉取 {len(all_records)} 条供应商记录")
        
        return {
            "success": True,
            "total": total,
            "records": all_records,
            "message": "OK"
        }
    
    def update_suppliers_config(self) -> Dict:
        """更新本地供应商配置"""
        result = self.query_all_suppliers()
        
        if not result["success"]:
            return result
        
        records = result["records"]
        count = db.sync_suppliers(records)
        
        return {
            "success": True,
            "total": count,
            "message": f"已同步 {count} 个供应商到数据库"
        }
    
    def query_purchase_orders(self, page: int = 1, page_size: int = 100, **filters) -> Dict:
        """查询采购明细"""
        params = [
            ("page", page),
            ("pageSize", page_size),
            ("detailCode", filters.get("detailCode", "")),
            ("supplierCode", filters.get("supplierCode", "")),
            ("supplierName", filters.get("supplierName", "")),
            ("purchaseCode", filters.get("purchaseCode", "")),
            ("purchaser", filters.get("purchaser", "")),
            ("categoryCode", filters.get("categoryCode", "")),
            ("categoryName", filters.get("categoryName", "")),
            ("subCategoryCode", filters.get("subCategoryCode", "")),
            ("subCategoryName", filters.get("subCategoryName", "")),
            ("cangSubCategoryCode", filters.get("cangSubCategoryCode", "")),
            ("cangSubCategoryName", filters.get("cangSubCategoryName", "")),
            ("productCode", filters.get("productCode", "")),
            ("productName", filters.get("productName", "")),
            ("inboundStatus", filters.get("inboundStatus", "")),
            ("inOrderId", filters.get("inOrderId", "")),
            ("startTime", filters.get("startTime", "")),
            ("endTime", filters.get("endTime", "")),
            ("purchaseStartTime", filters.get("purchaseStartTime", "")),
            ("purchaseEndTime", filters.get("purchaseEndTime", "")),
        ]
        
        try:
            result = api_client.get_raw("/restful/shasha/supply/ordersDetail", params=params)
            print(f"采购明细 API 响应: {result}")
            
            if result.get("code") != 1:
                return {
                    "success": False,
                    "message": result.get("msg", "查询失败"),
                    "records": [],
                    "total": 0
                }
            
            return {
                "success": True,
                "records": result.get("data", {}).get("records", []),
                "total": result.get("data", {}).get("total", 0)
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "records": [],
                "total": 0
            }
    
    def query_purchase_order_list(self, page: int = 1, page_size: int = 100, **filters) -> Dict:
        """查询采购订单列表"""
        params = [
            ("page", page),
            ("pageSize", page_size),
            ("supplierCode", filters.get("supplierCode", "")),
            ("supplierName", filters.get("supplierName", "")),
            ("purchaseCode", filters.get("purchaseCode", "")),
            ("purchaser", filters.get("purchaser", "")),
        ]
        
        try:
            result = api_client.get_raw("/restful/shasha/supply/orders", params=params)
            print(f"采购订单 API 响应: {result}")
            
            if result.get("code") != 1:
                return {
                    "success": False,
                    "message": result.get("msg", "查询失败"),
                    "records": [],
                    "total": 0
                }
            
            return {
                "success": True,
                "records": result.get("data", {}).get("records", []),
                "total": result.get("data", {}).get("total", 0)
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "records": [],
                "total": 0
            }
    
    def add_purchase_detail(self, purchase_code: str, product_ids: List[str], quantity: int = 1, purchaser: str = "system", purchase_time: str = None) -> Dict:
        """增加采购明细
        
        Args:
            purchase_code: 采购单编号（如 JH260522987）
            product_ids: 商品 ID 列表
            quantity: 数量
            purchaser: 进货人
            purchase_time: 进货时间（格式：2026-01-01 00:00:00）
        
        Returns:
            API 响应结果
        """
        # 1. 通过采购单编号查订单 ID
        order_result = self.query_purchase_order_list(purchaseCode=purchase_code)
        if not order_result["success"] or not order_result["records"]:
            return {"success": False, "message": "未找到采购订单"}
        
        order_id = order_result["records"][0].get("id")
        if not order_id:
            return {"success": False, "message": "订单缺少 ID 字段"}
        
        # 2. 从商品库获取商品信息
        goods_result = self.query_all_goods()
        if not goods_result["success"]:
            return {"success": False, "message": "查询商品库失败"}
        
        goods_list = goods_result["records"]
        goods_map = {str(g.get("id")): g for g in goods_list}
        
        # 3. 组装 productIdStr
        product_id_str_list = []
        in_prices = []
        for pid in product_ids:
            if pid not in goods_map:
                return {"success": False, "message": f"商品 ID {pid} 不存在于商品库"}
            g = goods_map[pid]
            category_id = g.get("categoryId", "")
            sub_category_id = g.get("subCategoryId", "")
            product_id = g.get("id", "")
            product_id_str_list.append(str(category_id))
            product_id_str_list.append(str(sub_category_id))
            product_id_str_list.append(str(product_id))
            in_prices.append(g.get("inPrice", 0))
        
        import json
        from urllib.parse import quote
        
        product_id_str = json.dumps(product_id_str_list)
        
        # 4. 默认进货时间
        if not purchase_time:
            from datetime import datetime
            purchase_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 5. 进货价格取第一个商品的价格
        in_price = in_prices[0] if in_prices else 0
        
        # 6. 调用 API
        data = {
            "orderId": order_id,
            "productIdStr": product_id_str,
            "quantity": quantity,
            "location": "",
            "purchaser": purchaser,
            "purchaseTime": purchase_time,
            "inPrice": in_price,
            "thumb": json.dumps([]),
        }
        
        try:
            result = api_client.post("/restful/shasha/supply/ordersDetail", data=data)
            print(f"增加采购明细 API 响应: {result}")
            
            if result.get("code") == 1:
                return {"success": True, "message": "添加成功"}
            else:
                return {"success": False, "message": result.get("msg", "添加失败")}
                
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def add_inbound_detail(self, purchase_code: str, product_ids: List[str], quantity: int = 1, purchaser: str = "system", purchase_time: str = None) -> Dict:
        """添加采购明细并入库
        
        流程：
        1. 查采购订单获取 orderId
        2. 添加采购明细
        3. 查采购明细获取 detailId
        4. 添加入库明细
        
        Args:
            purchase_code: 采购单编号
            product_ids: 商品 ID 列表
            quantity: 数量
            purchaser: 进货人
            purchase_time: 进货时间
        
        Returns:
            API 响应结果
        """
        # 1. 先添加采购明细
        add_result = self.add_purchase_detail(
            purchase_code=purchase_code,
            product_ids=product_ids,
            quantity=quantity,
            purchaser=purchaser,
            purchase_time=purchase_time,
        )
        
        if not add_result["success"]:
            return add_result
        
        # 2. 查询采购明细获取 detailId
        detail_result = self.query_purchase_orders(purchaseCode=purchase_code, page_size=100)
        if not detail_result["success"]:
            return {"success": False, "message": "查询采购明细失败"}
        
        # 3. 从商品库获取商品名称映射
        goods_result = self.query_all_goods()
        if not goods_result["success"]:
            return {"success": False, "message": "查询商品库失败"}
        goods_map = {str(g.get("id")): g for g in goods_result["records"]}
        
        # 4. 默认时间
        if not purchase_time:
            from datetime import datetime
            purchase_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 5. 为每个商品添加入库明细
        import json
        from urllib.parse import quote
        
        success_count = 0
        for pid in product_ids:
            # 找到对应的采购明细记录
            detail_record = None
            for d in detail_result["records"]:
                if str(d.get("productId")) == pid:
                    detail_record = d
                    break
            
            if not detail_record:
                continue
            
            detail_id = detail_record.get("id")
            product_name = goods_map.get(pid, {}).get("productName", "") or detail_record.get("productName", "")
            
            # 调用入库 API
            data = {
                "detailId": detail_id,
                "productName": product_name,
                "quantity": quantity,
                "location": "",
                "purchaser": purchaser,
                "purchaseTime": purchase_time,
                "birthTime": purchase_time,
                "inPrice": "",
                "thumb": json.dumps([]),
            }
            
            try:
                result = api_client.post("/restful/shasha/supply/ordersDetailInpark", data=data)
                print(f"入库明细 API 响应: {result}")
                
                if result.get("code") == 1:
                    success_count += 1
            except Exception as e:
                print(f"入库失败: {e}")
        
        if success_count > 0:
            return {"success": True, "message": f"成功入库 {success_count} 个商品"}
        else:
            return {"success": False, "message": "入库失败"}
    
    def create_purchase_order(self, supplier_id: int, purchase_time: str, purchaser: str = "system") -> Dict:
        """创建采购订单
        
        Args:
            supplier_id: 供应商 ID
            purchase_time: 采购时间（格式：2026-01-01 00:00:00）
            purchaser: 采购人
        
        Returns:
            API 响应结果
        """
        import json
        
        data = {
            "supplierId": supplier_id,
            "purchaseTime": purchase_time,
            "purchaser": purchaser,
            "thumbs": json.dumps([]),
        }
        
        try:
            result = api_client.post("/restful/shasha/supply/orders", data=data)
            print(f"创建采购订单 API 响应: {result}")
            
            if result.get("code") == 1:
                return {"success": True, "message": "创建成功", "data": result.get("data")}
            else:
                return {"success": False, "message": result.get("msg", "创建失败")}
                
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def close_purchase_detail(self, detail_id: int, can_show: int = 0) -> Dict:
        """更新采购明细显示状态
        
        Args:
            detail_id: 采购明细 ID
            can_show: 显示状态 0=隐藏 1=显示
        
        Returns:
            API 响应结果
        """
        try:
            # 构建带查询参数的 URL
            url = f"/restful/shasha/supply/ordersDetail/updateField?field=can_show&value={can_show}&id={detail_id}"
            result = api_client.post(url, data={})
            print(f"更新采购明细显示状态 API 响应: {result}")
            
            if result.get("code") == 1:
                return {"success": True, "message": "更新成功"}
            else:
                return {"success": False, "message": result.get("msg", "更新失败")}
                
        except Exception as e:
            return {"success": False, "message": str(e)}


base_library_service = BaseLibraryService()