"""配置管理模块"""

import json
from pathlib import Path
from typing import Any, Optional


class Config:
    """配置管理器"""
    
    _instance: Optional["Config"] = None
    _config_path: Path
    _data: dict
    
    def __new__(cls) -> "Config":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance
    
    def _init(self) -> None:
        """初始化配置"""
        self._config_path = self._find_config()
        self._data = self._load_config()
    
    def _find_config(self) -> Path:
        """查找配置文件"""
        candidates = [
            Path.cwd() / "config" / "settings.json",
            Path(__file__).parent.parent / "config" / "settings.json",
        ]
        
        for path in candidates:
            if path.exists():
                return path
        
        raise FileNotFoundError(f"配置文件未找到: {candidates}")
    
    def _load_config(self) -> dict:
        """加载配置文件"""
        with open(self._config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def reload(self) -> None:
        """重新加载配置"""
        self._data = self._load_config()
    
    @property
    def api_base_url(self) -> str:
        return self._data["api"]["base_url"]
    
    def get_endpoint(self, name: str) -> str:
        return self._data["api"]["endpoints"][name]
    
    def get_api_url(self, endpoint_name: str) -> str:
        return f"{self.api_base_url}{self.get_endpoint(endpoint_name)}"
    
    @property
    def username(self) -> str:
        return self._data["user"]["username"]
    
    @property
    def password(self) -> str:
        return self._data["user"]["password"]
    
    def get_store(self, store_id: str) -> dict:
        """获取门店信息，key 就是 ID"""
        return self._data["stores"].get(store_id, {})
    
    def get_all_stores(self) -> dict:
        """获取所有门店，key 是 ID"""
        return self._data["stores"]
    
    def get_store_name(self, store_id: str) -> str:
        """获取门店名称"""
        store = self.get_store(store_id)
        return store.get("name", "")
    
    def get_dish(self, dish_id: str) -> dict:
        """获取菜品信息，key 就是 ID"""
        return self._data["dishes"].get(dish_id, {})
    
    def get_all_dishes(self) -> dict:
        """获取所有菜品，key 是 ID"""
        return self._data["dishes"]
    
    def get_dish_name(self, dish_id: str) -> str:
        """获取菜品名称"""
        dish = self.get_dish(dish_id)
        return dish.get("name", "")
    
    def get_dish_price(self, dish_id: str) -> float:
        """获取菜品价格"""
        dish = self.get_dish(dish_id)
        return dish.get("price", 0.0)
    
    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value
    
    def _save(self) -> None:
        """保存配置文件"""
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
        print(f"配置已保存到: {self._config_path}")
    
    def add_dish(self, dish_id: str, name: str, price: float, time_range: str = "00:00-23:59") -> bool:
        """添加菜品"""
        if dish_id in self._data.get("dishes", {}):
            return False
        self._data.setdefault("dishes", {})
        self._data["dishes"][dish_id] = {
            "name": name, "price": price, "time_range": time_range
        }
        self._save()
        return True
    
    def update_dish(self, dish_id: str, name: str, price: float, time_range: str = "00:00-23:59") -> bool:
        """更新菜品"""
        if dish_id not in self._data.get("dishes", {}):
            return False
        self._data["dishes"][dish_id] = {
            "name": name, "price": price, "time_range": time_range
        }
        self._save()
        return True
    
    def delete_dish(self, dish_id: str) -> bool:
        """删除菜品"""
        if dish_id not in self._data.get("dishes", {}):
            return False
        del self._data["dishes"][dish_id]
        self._save()
        return True
    
    def get_dish_time_range(self, dish_id: str) -> str:
        """获取菜品可用时间区间"""
        dish = self.get_dish(dish_id)
        return dish.get("time_range", "00:00-23:59")


config = Config()