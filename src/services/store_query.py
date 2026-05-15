"""门店查询服务

从平台 API 查询门店列表，更新本地配置。
"""

from typing import Optional, Dict

from src.api.client import api_client


class StoreQueryService:
    """门店查询服务"""
    
    def query_stores(self, page: int = 1, page_size: int = 100) -> Dict:
        """查询门店列表"""
        params = [
            ("page", page),
            ("pageSize", page_size),
            ("storeCode", ""),
            ("storeName", ""),
            ("phone", ""),
            ("franchiseeId", ""),
        ]
        
        try:
            result = api_client.get_raw("stores", params=params)
            
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
    
    def query_all_stores(self) -> Dict:
        """查询所有门店"""
        # 门店数量通常不多，一次查询即可
        result = self.query_stores(page=1, page_size=100)
        
        if not result["success"]:
            return result
        
        return {
            "success": True,
            "total": result["total"],
            "records": result["records"],
            "message": "OK"
        }
    
    def update_config(self) -> Dict:
        """更新本地门店配置"""
        import json
        from pathlib import Path
        
        result = self.query_all_stores()
        
        if not result["success"]:
            return result
        
        records = result["records"]
        
        # 构建新的门店配置
        new_stores = {}
        for record in records:
            store_id = record.get("id")
            store_name = record.get("storeName", "")
            if store_id:
                new_stores[str(store_id)] = {"name": store_name}
        
        # 更新配置文件
        config_path = Path(__file__).parent.parent.parent / "config" / "settings.json"
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            config["stores"] = new_stores
            
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            # 重新加载配置
            from src.config import config as config_instance
            config_instance.reload()
            
            return {
                "success": True,
                "total": len(new_stores),
                "message": f"已更新 {len(new_stores)} 个门店配置"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": str(e)
            }


store_query_service = StoreQueryService()