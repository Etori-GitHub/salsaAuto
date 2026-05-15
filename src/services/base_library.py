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


base_library_service = BaseLibraryService()