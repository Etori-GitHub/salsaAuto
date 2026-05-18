"""数据库服务"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict


class Database:
    """数据库服务"""
    
    def __init__(self):
        self.db_path = Path(__file__).parent.parent.parent / "data" / "orders.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 刷单记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                order_date TEXT NOT NULL,
                store_id INTEGER NOT NULL,
                store_name TEXT,
                dish_id INTEGER NOT NULL,
                dish_name TEXT,
                dish_price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                total_amount REAL NOT NULL,
                pay_type TEXT NOT NULL,
                remark TEXT,
                api_success INTEGER DEFAULT 0,
                api_response TEXT
            )
        """)
        
        # 商品库表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS goods (
                id INTEGER PRIMARY KEY,
                product_code TEXT,
                product_name TEXT,
                category_id INTEGER,
                category_name TEXT,
                sub_category_id INTEGER,
                sub_category_name TEXT,
                cang_sub_category_id INTEGER,
                cang_sub_category_name TEXT,
                unit_price REAL,
                true_price REAL,
                unit TEXT,
                spec_name TEXT,
                status INTEGER DEFAULT 1,
                updated_at TEXT
            )
        """)
        
        # 检查并添加 status 字段
        cursor.execute("PRAGMA table_info(goods)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'status' not in columns:
            cursor.execute("ALTER TABLE goods ADD COLUMN status INTEGER DEFAULT 1")
        
        # 商品分类表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS goods_sub_cate (
                id INTEGER PRIMARY KEY,
                sub_category_code TEXT,
                sub_category_name TEXT,
                category_id INTEGER,
                category_name TEXT,
                type TEXT,
                updated_at TEXT
            )
        """)
        
        # 档口分类表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cang_sub_cate (
                id INTEGER PRIMARY KEY,
                sub_category_code TEXT,
                sub_category_name TEXT,
                category_id INTEGER,
                category_name TEXT,
                updated_at TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def add_order_record(
        self, order_date: str, store_id: int, store_name: str,
        dish_id: int, dish_name: str, dish_price: float,
        quantity: int, total_amount: float, pay_type: str,
        remark: str = "", api_success: bool = False, api_response: str = ""
    ) -> int:
        """添加刷单记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO order_records 
            (created_at, order_date, store_id, store_name, dish_id, dish_name, 
             dish_price, quantity, total_amount, pay_type, remark, api_success, api_response)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            order_date,
            store_id, store_name,
            dish_id, dish_name, dish_price,
            quantity, total_amount, pay_type,
            remark, 1 if api_success else 0, api_response
        ))
        
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return record_id
    
    def get_order_records(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None,
        store_id: Optional[int] = None, pay_type: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        """查询刷单记录"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        sql = "SELECT * FROM order_records WHERE 1=1"
        params = []
        
        if start_date:
            sql += " AND order_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND order_date <= ?"
            params.append(end_date)
        if store_id:
            sql += " AND store_id = ?"
            params.append(store_id)
        if pay_type:
            sql += " AND pay_type = ?"
            params.append(pay_type)
        
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_statistics(self, start_date: Optional[str] = None, end_date: Optional[str] = None, store_id: Optional[int] = None) -> Dict:
        """获取统计数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        sql = """
            SELECT 
                COUNT(*) as total_orders,
                SUM(CASE WHEN api_success = 1 THEN 1 ELSE 0 END) as success_orders,
                SUM(CASE WHEN api_success = 1 THEN total_amount ELSE 0 END) as total_amount,
                SUM(CASE WHEN api_success = 1 THEN quantity ELSE 0 END) as total_quantity
            FROM order_records WHERE 1=1
        """
        params = []
        
        if start_date:
            sql += " AND order_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND order_date <= ?"
            params.append(end_date)
        if store_id:
            sql += " AND store_id = ?"
            params.append(store_id)
        
        cursor.execute(sql, params)
        row = cursor.fetchone()
        conn.close()
        
        return {
            "total_orders": row[0] or 0,
            "success_orders": row[1] or 0,
            "total_amount": row[2] or 0,
            "total_quantity": row[3] or 0
        }
    
    def delete_order_record(self, record_id: int) -> bool:
        """删除刷单记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM order_records WHERE id = ?", (record_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0
    
    # ==================== 商品库操作 ====================
    
    def sync_goods(self, goods_list: List[Dict]) -> int:
        """同步商品库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 清空旧数据
        cursor.execute("DELETE FROM goods")
        
        # 插入新数据
        for g in goods_list:
            cursor.execute("""
                INSERT INTO goods (id, product_code, product_name, category_id, category_name,
                    sub_category_id, sub_category_name, cang_sub_category_id, cang_sub_category_name,
                    unit_price, true_price, unit, spec_name, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                g.get("id"),
                g.get("productCode"),
                g.get("productName"),
                g.get("categoryId"),
                g.get("categoryName"),
                g.get("subCategoryId"),
                g.get("subCategoryName"),
                g.get("cangSubCategoryId"),
                g.get("cangSubCategoryName"),
                g.get("unitPrice"),
                g.get("truePrice"),
                g.get("unit"),
                g.get("specName"),
                g.get("status", 1),  # 默认上架
                now
            ))
        
        
        conn.commit()
        count = cursor.execute("SELECT COUNT(*) FROM goods").fetchone()[0]
        conn.close()
        return count
    
    def get_goods(self, search: str = None, category: str = None) -> List[Dict]:
        """查询商品库"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        sql = "SELECT * FROM goods WHERE 1=1"
        params = []
        
        if search:
            sql += " AND (product_name LIKE ? OR product_code LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        if category:
            sql += " AND category_name = ?"
            params.append(category)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    # ==================== 商品分类操作 ====================
    
    def sync_goods_sub_cate(self, cate_list: List[Dict]) -> int:
        """同步商品分类（保留已设定的类型）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 先获取现有的类型设置
        cursor.execute("SELECT id, type FROM goods_sub_cate WHERE type IS NOT NULL AND type != ''")
        existing_types = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.execute("DELETE FROM goods_sub_cate")
        
        for c in cate_list:
            cate_id = c.get("id")
            # 如果之前有设定类型，保留
            preserved_type = existing_types.get(cate_id)
            
            cursor.execute("""
                INSERT INTO goods_sub_cate (id, sub_category_code, sub_category_name, category_id, category_name, type, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                cate_id,
                c.get("subCategoryCode"),
                c.get("subCategoryName"),
                c.get("categoryId"),
                c.get("categoryName"),
                preserved_type,
                now
            ))
        
        
        conn.commit()
        count = cursor.execute("SELECT COUNT(*) FROM goods_sub_cate").fetchone()[0]
        conn.close()
        return count
    
    def get_goods_sub_cate(self) -> List[Dict]:
        """查询商品分类"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, sub_category_code, sub_category_name, type FROM goods_sub_cate")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def update_goods_sub_cate_type(self, cate_id: int, cate_type: str) -> bool:
        """更新商品分类类型"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE goods_sub_cate SET type = ? WHERE id = ?", (cate_type, cate_id))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0
    
    # ==================== 档口分类操作 ====================
    
    def sync_cang_sub_cate(self, cate_list: List[Dict]) -> int:
        """同步档口分类"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("DELETE FROM cang_sub_cate")
        
        for c in cate_list:
            cursor.execute("""
                INSERT INTO cang_sub_cate (id, sub_category_code, sub_category_name, category_id, category_name, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                c.get("id"),
                c.get("subCategoryCode"),
                c.get("subCategoryName"),
                c.get("categoryId"),
                c.get("categoryName"),
                now
            ))
        
        
        conn.commit()
        count = cursor.execute("SELECT COUNT(*) FROM cang_sub_cate").fetchone()[0]
        conn.close()
        return count
    
    def get_cang_sub_cate(self) -> List[Dict]:
        """查询档口分类"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cang_sub_cate")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]


db = Database()
