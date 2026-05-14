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
        store_id: Optional[int] = None, limit: int = 100
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
        
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_statistics(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict:
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


db = Database()
