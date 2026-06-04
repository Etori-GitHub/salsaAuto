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
        
        # 会员表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY,
                phone TEXT,
                username TEXT,
                balance REAL,
                member_type TEXT,
                updated_at TEXT
            )
        """)
        
        # 供应商表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY,
                supplier_code TEXT,
                supplier_name TEXT,
                phone TEXT,
                contact TEXT,
                address TEXT,
                status INTEGER DEFAULT 1,
                summary_entity TEXT,
                updated_at TEXT
            )
        """)
        
        # 汇总主体表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS summary_entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT
            )
        """)
        
        # 采购明细表（本地缓存）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_details (
                id INTEGER PRIMARY KEY,
                detail_code TEXT,
                purchase_code TEXT,
                supplier_code TEXT,
                supplier_name TEXT,
                product_id INTEGER,
                product_name TEXT,
                category_name TEXT,
                sub_category_name TEXT,
                quantity INTEGER,
                unit_price REAL,
                total_price REAL,
                purchase_time TEXT,
                purchaser TEXT,
                can_show INTEGER DEFAULT 1,
                inbound_status INTEGER DEFAULT 0,
                create_time TEXT,
                updated_at TEXT
            )
        """)
        
        # 耗用记录表（本地缓存）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS consume_records (
                id INTEGER PRIMARY KEY,
                store_id INTEGER,
                store_name TEXT,
                product_id INTEGER,
                product_code TEXT,
                product_name TEXT,
                category_code TEXT,
                category_name TEXT,
                sub_category_code TEXT,
                sub_category_name TEXT,
                cang_sub_category_code TEXT,
                cang_sub_category_name TEXT,
                spec_name TEXT,
                unit TEXT,
                unit_price REAL,
                quantity REAL,
                total_amount REAL,
                used_time TEXT,
                used_source TEXT,
                used_by INTEGER,
                create_time TEXT,
                updated_at TEXT
            )
        """)
        
        # 库存快照表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                snapshot_date TEXT NOT NULL,
                stock_quantity REAL DEFAULT 0,
                stock_amount REAL DEFAULT 0,
                created_at TEXT,
                UNIQUE(store_id, product_id, snapshot_date)
            )
        """)
        
        # 库存流水表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_flows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                flow_date TEXT NOT NULL,
                flow_type TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit_price REAL,
                amount REAL,
                balance_quantity REAL,
                balance_amount REAL,
                ref_type TEXT,
                ref_id INTEGER,
                remark TEXT,
                created_at TEXT
            )
        """)
        
        # 要货明细缓存表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS supply_order_details (
                id INTEGER PRIMARY KEY,
                store_id INTEGER,
                store_name TEXT,
                product_id INTEGER,
                product_code TEXT,
                product_name TEXT,
                category_name TEXT,
                sub_category_name TEXT,
                cang_sub_category_name TEXT,
                spec_name TEXT,
                unit TEXT,
                unit_price REAL,
                quantity REAL,
                total_amount REAL,
                create_time TEXT,
                delivery_code TEXT,
                can_show INTEGER DEFAULT 1,
                synced_at TEXT
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
    
    def get_statistics(self, start_date: Optional[str] = None, end_date: Optional[str] = None, store_id: Optional[int] = None, pay_type: Optional[str] = None) -> Dict:
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
        if pay_type:
            sql += " AND pay_type = ?"
            params.append(pay_type)
        
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
                    unit_price, true_price, unit, spec_name, status, supplier_code, supplier_name, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                g.get("supplierCode"),
                g.get("supplierName"),
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
    
    # ==================== 会员操作 ====================
    
    def sync_members(self, member_list: List[Dict]) -> int:
        """同步会员数据（根据 ID 匹配，更新用户名和余额）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 构建 API 会员字典（以 id 为 key）
        api_members = {m.get("id"): m for m in member_list}
        
        # 更新本地会员（根据 ID 匹配）
        for member_id, api_member in api_members.items():
            cursor.execute("""
                UPDATE members 
                SET username = ?, balance = ?, updated_at = ?
                WHERE id = ?
            """, (
                api_member.get("username", ""),
                api_member.get("balance", 0),
                now,
                member_id
            ))
        
        
        conn.commit()
        # 返回更新的数量
        count = cursor.execute("SELECT COUNT(*) FROM members").fetchone()[0]
        conn.close()
        return count
    
    def get_members(self) -> List[Dict]:
        """查询所有会员"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM members")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_member(self, member_id: int) -> Optional[Dict]:
        """查询单个会员"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM members WHERE id = ?", (member_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def update_member_balance(self, member_id: int, new_balance: float) -> bool:
        """更新会员余额"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE members SET balance = ? WHERE id = ?", (new_balance, member_id))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0
    
    def add_member(self, member_id: int, phone: str = "", username: str = "",
                    balance: float = 0, member_type: str = "None") -> bool:
        """添加新会员"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            cursor.execute("""
                INSERT INTO members (id, phone, username, balance, member_type, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (member_id, phone, username, balance, member_type, now))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False  # ID 已存在
    
    def update_member_type(self, member_id: int, member_type: str) -> bool:
        """更新会员类型"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE members SET member_type = ? WHERE id = ?", (member_type, member_id))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0
    
    def delete_member(self, member_id: int) -> bool:
        """删除会员"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM members WHERE id = ?", (member_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0
    
    # ==================== 供应商操作 ====================
    
    def sync_suppliers(self, supplier_list: List[Dict]) -> int:
        """同步供应商数据（保留汇总主体设置）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 获取现有的汇总主体设置
        cursor.execute("SELECT id, summary_entity FROM suppliers WHERE summary_entity IS NOT NULL AND summary_entity != ''")
        existing_entities = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.execute("DELETE FROM suppliers")
        
        for s in supplier_list:
            supplier_id = s.get("id")
            preserved_entity = existing_entities.get(supplier_id)
            
            cursor.execute("""
                INSERT INTO suppliers (id, supplier_code, supplier_name, phone, contact, address, status, summary_entity, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                supplier_id,
                s.get("supplierCode"),
                s.get("supplierName"),
                s.get("phone"),
                s.get("contact"),
                s.get("address"),
                s.get("status", 1),
                preserved_entity,
                now
            ))
        
        conn.commit()
        count = cursor.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0]
        conn.close()
        return count
    
    def get_suppliers(self, search: str = None) -> List[Dict]:
        """查询供应商"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        sql = "SELECT * FROM suppliers WHERE 1=1"
        params = []
        
        if search:
            sql += " AND (supplier_name LIKE ? OR supplier_code LIKE ? OR phone LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        
        sql += " ORDER BY id"
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def update_supplier_entity(self, supplier_id: int, entity_name: str) -> bool:
        """更新供应商汇总主体"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE suppliers SET summary_entity = ? WHERE id = ?", (entity_name, supplier_id))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0
    
    def batch_update_supplier_entity(self, entity_name: str) -> int:
        """批量更新所有空汇总主体的供应商"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE suppliers SET summary_entity = ? WHERE summary_entity IS NULL OR summary_entity = ''", (entity_name,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected
    
    # ==================== 汇总主体操作 ====================
    
    def get_summary_entities(self) -> List[Dict]:
        """获取所有汇总主体"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM summary_entities ORDER BY id")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def add_summary_entity(self, name: str) -> bool:
        """添加汇总主体"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor.execute("INSERT INTO summary_entities (name, created_at) VALUES (?, ?)", (name, now))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False
    
    def update_summary_entity(self, entity_id: int, name: str) -> bool:
        """更新汇总主体"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE summary_entities SET name = ? WHERE id = ?", (name, entity_id))
            affected = cursor.rowcount
            conn.commit()
            conn.close()
            return affected > 0
        except sqlite3.IntegrityError:
            conn.close()
            return False
    
    def delete_summary_entity(self, entity_id: int) -> bool:
        """删除汇总主体"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM summary_entities WHERE id = ?", (entity_id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0
    
    # ==================== 采购明细操作 ====================
    
    def sync_purchase_details(self, details: List[Dict]) -> int:
        """同步采购明细到本地库（覆盖）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 清空旧数据
        cursor.execute("DELETE FROM purchase_details")
        
        # 插入新数据
        for d in details:
            # 进货时间：优先从明细获取，否则从订单获取（不再用创建时间兜底）
            purchase_time = d.get("purchaseTime")
            if not purchase_time:
                orders = d.get("orders") or {}
                purchase_time = orders.get("purchaseTime")
            # 如果都没有，保持为空
            
            cursor.execute("""
                INSERT INTO purchase_details (
                    id, detail_code, purchase_code, supplier_code, supplier_name,
                    product_id, product_name, category_name, sub_category_name,
                    quantity, unit_price, total_price, purchase_time, purchaser,
                    can_show, inbound_status, create_time, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                d.get("id"),
                d.get("detailCode"),
                d.get("orderCode") or d.get("purchaseCode"),
                d.get("supplierCode"),
                d.get("supplierName"),
                d.get("productId"),
                d.get("productName"),
                d.get("productCategoryName"),
                d.get("productCategorySubName"),
                d.get("quantity"),
                d.get("unitPrice"),
                d.get("totalPrice"),
                purchase_time,  # 可能为空
                d.get("purchaser"),
                d.get("canShow", 1),
                d.get("inboundStatus", 0),
                d.get("createTime"),
                now
            ))
        
        count = len(details)
        conn.commit()
        conn.close()
        return count
    
    def get_purchase_details_by_date(self, date_str: str, supplier_codes: List[str] = None) -> List[Dict]:
        """按进货时间查询采购明细"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        sql = "SELECT * FROM purchase_details WHERE purchase_time LIKE ?"
        params = [f"{date_str}%"]
        
        if supplier_codes:
            placeholders = ",".join("?" * len(supplier_codes))
            sql += f" AND supplier_code IN ({placeholders})"
            params.extend(supplier_codes)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def update_purchase_detail_can_show(self, detail_id: int, can_show: int):
        """更新采购明细的显示状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE purchase_details SET can_show = ? WHERE id = ?", (can_show, detail_id))
        conn.commit()
        conn.close()
    
    def add_purchase_detail(self, detail: Dict):
        """添加采购明细到本地库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT OR REPLACE INTO purchase_details (
                id, detail_code, purchase_code, supplier_code, supplier_name,
                product_id, product_name, category_name, sub_category_name,
                quantity, unit_price, total_price, purchase_time, purchaser,
                can_show, inbound_status, create_time, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            detail.get("id"),
            detail.get("detailCode"),
            detail.get("orderCode") or detail.get("purchaseCode"),
            detail.get("supplierCode"),
            detail.get("supplierName"),
            detail.get("productId"),
            detail.get("productName"),
            detail.get("productCategoryName"),
            detail.get("productCategorySubName"),
            detail.get("quantity"),
            detail.get("unitPrice"),
            detail.get("totalPrice"),
            detail.get("purchaseTime"),
            detail.get("purchaser"),
            detail.get("canShow", 1),
            detail.get("inboundStatus", 0),
            detail.get("createTime"),
            now
        ))
        conn.commit()
        conn.close()
    
    def get_purchase_details_local(self) -> List[Dict]:
        """从本地数据库获取所有采购明细"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM purchase_details")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_all_purchase_details(self) -> List[Dict]:
        """获取所有采购明细（别名方法）"""
        return self.get_purchase_details_local()
    
    def update_purchase_detail_time(self, detail_id: int, purchase_time: str):
        """更新采购明细的进货时间"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE purchase_details SET purchase_time = ? WHERE id = ?", (purchase_time, detail_id))
        conn.commit()
        conn.close()
    
    # ==================== 耗用记录操作 ====================
    
    def sync_consume_records(self, records: List[Dict]) -> int:
        """同步耗用记录到本地库（覆盖模式：先清空再插入）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 先清空旧数据
        cursor.execute("DELETE FROM consume_records")
        
        count = 0
        for r in records:
            try:
                cursor.execute("""
                    INSERT INTO consume_records (
                        id, store_id, store_name, product_id, product_code, product_name,
                        category_code, category_name, sub_category_code, sub_category_name,
                        cang_sub_category_code, cang_sub_category_name, spec_name, unit,
                        unit_price, quantity, total_amount, used_time, used_source,
                        used_by, create_time, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r.get("id"),
                    r.get("store_id"),
                    r.get("store_name"),
                    r.get("product_id"),
                    r.get("product_code"),
                    r.get("product_name"),
                    r.get("category_code"),
                    r.get("category_name"),
                    r.get("sub_category_code"),
                    r.get("sub_category_name"),
                    r.get("cang_sub_category_code"),
                    r.get("cang_sub_category_name"),
                    r.get("spec_name"),
                    r.get("unit"),
                    r.get("unit_price"),
                    r.get("quantity"),
                    r.get("total_amount"),
                    r.get("used_time"),
                    r.get("used_source"),
                    r.get("used_by"),
                    r.get("create_time"),
                    now
                ))
                if cursor.rowcount > 0:
                    count += 1
            except Exception as e:
                print(f"同步耗用记录失败: {e}")
        
        conn.commit()
        conn.close()
        return count
    
    def get_consume_records(
        self,
        store_id: Optional[int] = None,
        product_id: Optional[int] = None,
        product_name: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict]:
        """查询耗用记录"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        sql = "SELECT * FROM consume_records WHERE 1=1"
        params = []
        
        if store_id:
            sql += " AND store_id = ?"
            params.append(store_id)
        if product_id:
            sql += " AND product_id = ?"
            params.append(product_id)
        if product_name:
            sql += " AND product_name LIKE ?"
            params.append(f"%{product_name}%")
        if start_time:
            sql += " AND used_time >= ?"
            params.append(f"{start_time} 00:00:00")
        if end_time:
            sql += " AND used_time <= ?"
            params.append(f"{end_time} 23:59:59")
        
        sql += " ORDER BY used_time DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_consume_summary(
        self,
        store_id: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None
    ) -> Dict:
        """获取耗用汇总"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        sql = """
            SELECT 
                COUNT(*) as total_records,
                SUM(quantity) as total_quantity,
                SUM(total_amount) as total_amount
            FROM consume_records WHERE 1=1
        """
        params = []
        
        if store_id:
            sql += " AND store_id = ?"
            params.append(store_id)
        if start_time:
            sql += " AND used_time >= ?"
            params.append(f"{start_time} 00:00:00")
        if end_time:
            sql += " AND used_time <= ?"
            params.append(f"{end_time} 23:59:59")
        
        cursor.execute(sql, params)
        row = cursor.fetchone()
        conn.close()
        
        return {
            "total_records": row[0] or 0,
            "total_quantity": row[1] or 0,
            "total_amount": row[2] or 0
        }
    
    # ==================== 库存快照操作 ====================
    
    def get_latest_stock_snapshot(self, store_id: int, product_id: int) -> Optional[Dict]:
        """获取最近的库存快照"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM stock_snapshots 
            WHERE store_id = ? AND product_id = ?
            ORDER BY snapshot_date DESC LIMIT 1
        """, (store_id, product_id))
        
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def save_stock_snapshot(self, store_id: int, product_id: int, snapshot_date: str,
                              stock_quantity: float, stock_amount: float) -> bool:
        """保存库存快照"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO stock_snapshots 
                (store_id, product_id, snapshot_date, stock_quantity, stock_amount, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (store_id, product_id, snapshot_date, stock_quantity, stock_amount, now))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"保存快照失败: {e}")
            conn.close()
            return False
    
    def get_all_stock_snapshots(self, snapshot_date: str = None) -> List[Dict]:
        """获取所有库存快照"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if snapshot_date:
            cursor.execute("SELECT * FROM stock_snapshots WHERE snapshot_date = ?", (snapshot_date,))
        else:
            cursor.execute("SELECT * FROM stock_snapshots ORDER BY snapshot_date DESC")
        
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    # ==================== 库存流水操作 ====================
    
    def add_stock_flow(self, flow: Dict) -> int:
        """添加库存流水记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            INSERT INTO stock_flows (
                store_id, product_id, flow_date, flow_type, quantity,
                unit_price, amount, balance_quantity, balance_amount,
                ref_type, ref_id, remark, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            flow.get("store_id"),
            flow.get("product_id"),
            flow.get("flow_date"),
            flow.get("flow_type"),
            flow.get("quantity"),
            flow.get("unit_price"),
            flow.get("amount"),
            flow.get("balance_quantity"),
            flow.get("balance_amount"),
            flow.get("ref_type"),
            flow.get("ref_id"),
            flow.get("remark"),
            now
        ))
        
        flow_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return flow_id
    
    def get_stock_flows(
        self,
        store_id: Optional[int] = None,
        product_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        flow_type: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict]:
        """查询库存流水"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        sql = "SELECT * FROM stock_flows WHERE 1=1"
        params = []
        
        if store_id:
            sql += " AND store_id = ?"
            params.append(store_id)
        if product_id:
            sql += " AND product_id = ?"
            params.append(product_id)
        if start_date:
            sql += " AND flow_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND flow_date <= ?"
            params.append(end_date)
        if flow_type:
            sql += " AND flow_type = ?"
            params.append(flow_type)
        
        sql += " ORDER BY flow_date DESC, id DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_stock_flow_summary(
        self,
        store_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """获取库存流水汇总"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        sql = """
            SELECT 
                flow_type,
                COUNT(*) as flow_count,
                SUM(quantity) as total_quantity,
                SUM(amount) as total_amount
            FROM stock_flows WHERE 1=1
        """
        params = []
        
        if store_id:
            sql += " AND store_id = ?"
            params.append(store_id)
        if start_date:
            sql += " AND flow_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND flow_date <= ?"
            params.append(end_date)
        
        sql += " GROUP BY flow_type"
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        
        result = {
            "supply_in": {"count": 0, "quantity": 0, "amount": 0},
            "consume_out": {"count": 0, "quantity": 0, "amount": 0}
        }
        
        for row in rows:
            flow_type = row[0]
            if flow_type == "supply":
                result["supply_in"] = {
                    "count": row[1],
                    "quantity": row[2] or 0,
                    "amount": row[3] or 0
                }
            elif flow_type == "consume":
                result["consume_out"] = {
                    "count": row[1],
                    "quantity": row[2] or 0,
                    "amount": row[3] or 0
                }
        
        return result
    
    def clear_stock_flows(self, store_id: int = None):
        """清除库存流水（用于重新计算）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if store_id:
            cursor.execute("DELETE FROM stock_flows WHERE store_id = ?", (store_id,))
        else:
            cursor.execute("DELETE FROM stock_flows")
        
        conn.commit()
        conn.close()
    
    # ==================== 要货明细缓存操作 ====================
    
    def sync_supply_order_details(self, records: List[Dict]) -> int:
        """同步要货明细到本地缓存（覆盖模式：先清空再插入）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 先清空旧数据
        cursor.execute("DELETE FROM supply_order_details")
        
        count = 0
        for r in records:
            try:
                cursor.execute("""
                    INSERT INTO supply_order_details (
                        id, store_id, store_name, product_id, product_code, product_name,
                        category_name, sub_category_name, cang_sub_category_name,
                        spec_name, unit, unit_price, quantity, total_amount,
                        create_time, delivery_code, can_show, synced_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r.get("id"),
                    r.get("store_id"),
                    r.get("store_name"),
                    r.get("product_id"),
                    r.get("product_code"),
                    r.get("product_name"),
                    r.get("category_name"),
                    r.get("sub_category_name"),
                    r.get("cang_sub_category_name"),
                    r.get("spec_name"),
                    r.get("unit"),
                    r.get("unit_price"),
                    r.get("quantity"),
                    r.get("total_amount"),
                    r.get("create_time"),
                    r.get("delivery_code"),
                    r.get("can_show", 1),
                    now
                ))
                count += 1
            except Exception as e:
                print(f"同步要货明细失败: {e}")
        
        conn.commit()
        conn.close()
        return count
    
    def get_supply_order_details(
        self,
        store_id: Optional[int] = None,
        product_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 10000
    ) -> List[Dict]:
        """查询要货明细缓存"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        sql = "SELECT * FROM supply_order_details WHERE can_show = 1"
        params = []
        
        if store_id:
            sql += " AND store_id = ?"
            params.append(store_id)
        if product_id:
            sql += " AND product_id = ?"
            params.append(product_id)
        if start_date:
            sql += " AND create_time >= ?"
            params.append(f"{start_date} 00:00:00")
        if end_date:
            sql += " AND create_time <= ?"
            params.append(f"{end_date} 23:59:59")
        
        sql += " ORDER BY create_time DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_supply_order_count(self, store_id: Optional[int] = None) -> int:
        """获取要货明细数量"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        sql = "SELECT COUNT(*) FROM supply_order_details WHERE can_show = 1"
        params = []
        
        if store_id:
            sql += " AND store_id = ?"
            params.append(store_id)
        
        cursor.execute(sql, params)
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def clear_supply_order_details(self):
        """清空要货明细缓存"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM supply_order_details")
        conn.commit()
        conn.close()


db = Database()
