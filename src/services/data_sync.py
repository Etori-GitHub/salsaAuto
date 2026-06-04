"""数据同步服务

同步要货明细和耗用记录到本地数据库。
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List

from src.services.database import db
from src.services.supply_query import supply_query_service
from src.services.consume_query import consume_query_service

logger = logging.getLogger(__name__)


class DataSyncService:
    """数据同步服务"""
    
    def sync_supply_orders(self, store_id: int = None) -> Dict:
        """同步要货明细到本地缓存
        
        Args:
            store_id: 门店ID（可选，不传则同步全部）
        
        Returns:
            同步结果
        """
        logger.info(f"[sync_supply_orders] 开始同步要货明细: store_id={store_id}")
        print(f"[sync_supply_orders] 开始同步要货明细...")
        
        # 转换门店ID格式
        store_code = None
        if store_id:
            store_code = f"M{str(store_id).zfill(5)}"
        
        # 查询全部要货记录（从 2026-01-01 开始）
        result = supply_query_service.query_all_supply_orders(
            store_code=store_code,
            start_time="2026-01-01"
        )
        
        if not result["success"]:
            logger.error(f"[sync_supply_orders] 查询失败: {result['message']}")
            print(f"[sync_supply_orders] 查询失败: {result['message']}")
            return result
        
        records = result["records"]
        logger.info(f"[sync_supply_orders] 查询到 {len(records)} 条要货记录")
        
        # 解析并过滤有效数据
        valid_records = []
        skipped = 0
        
        for record in records:
            stores = record.get("stores") or {}
            product = record.get("supProduct") or {}
            
            record_store_id = stores.get("id")
            product_id = product.get("id")
            
            # 只同步 canShow = 1 的有效记录
            can_show = record.get("canShow", 1)
            if can_show != 1:
                skipped += 1
                continue
            
            # 过滤无效数据
            if not record_store_id or not product_id:
                skipped += 1
                continue
            
            quantity = record.get("quantity", 0) or 0
            if quantity <= 0:
                skipped += 1
                continue
            
            create_time = record.get("createTime", "")
            if not create_time:
                skipped += 1
                continue
            
            # 只同步 2026-01-01 之后的数据
            if create_time < "2026-01-01":
                skipped += 1
                continue
            
            unit_price = product.get("unitPrice", 0) or 0
            
            valid_records.append({
                "id": record.get("id"),
                "store_id": record_store_id,
                "store_name": stores.get("storeName", ""),
                "product_id": product_id,
                "product_code": product.get("productCode", ""),
                "product_name": product.get("productName", ""),
                "category_name": product.get("categoryName", ""),
                "sub_category_name": product.get("subCategoryName", ""),
                "cang_sub_category_name": product.get("cangSubCategoryName", ""),
                "spec_name": product.get("specName", ""),
                "unit": product.get("unit", ""),
                "unit_price": unit_price,
                "quantity": quantity,
                "total_amount": quantity * unit_price,
                "create_time": create_time,
                "delivery_code": record.get("deliveryCode", ""),
                "can_show": can_show,
            })
        
        logger.info(f"[sync_supply_orders] 有效记录: {len(valid_records)}，跳过: {skipped}")
        
        # 同步到数据库
        count = db.sync_supply_order_details(valid_records)
        logger.info(f"[sync_supply_orders] 同步完成: {count} 条记录")
        
        return {
            "success": True,
            "total": len(records),
            "valid": len(valid_records),
            "synced": count,
            "skipped": skipped,
            "message": "同步完成"
        }
    
    def sync_consume_records(self, store_id: int = None) -> Dict:
        """同步耗用记录到本地缓存
        
        Args:
            store_id: 门店ID（可选，不传则同步全部）
        
        Returns:
            同步结果
        """
        logger.info(f"[sync_consume_records] 开始同步耗用记录: store_id={store_id}")
        
        # 查询全部耗用记录（不限制时间）
        result = consume_query_service.query_all_consume_records()
        
        if not result["success"]:
            logger.error(f"[sync_consume_records] 查询失败: {result['message']}")
            return result
        
        records = result["records"]
        logger.info(f"[sync_consume_records] 查询到 {len(records)} 条耗用记录")
        
        # 解析并过滤有效数据
        valid_records = []
        skipped = 0
        
        for record in records:
            parsed = consume_query_service.parse_consume_record(record)
            
            # 如果指定了门店，过滤
            if store_id and parsed.get("store_id") != store_id:
                skipped += 1
                continue
            
            # 过滤无效数据
            if not parsed.get("store_id") or not parsed.get("product_id"):
                skipped += 1
                continue
            
            if parsed.get("quantity", 0) <= 0:
                skipped += 1
                continue
            
            if not parsed.get("used_time"):
                skipped += 1
                continue
            
            # 只同步 2026-01-01 之后的数据
            used_time = parsed.get("used_time", "")
            if used_time and used_time < "2026-01-01":
                skipped += 1
                continue
            
            valid_records.append(parsed)
        
        logger.info(f"[sync_consume_records] 有效记录: {len(valid_records)}，跳过: {skipped}")
        
        # 同步到数据库
        count = db.sync_consume_records(valid_records)
        logger.info(f"[sync_consume_records] 同步完成: {count} 条新记录")
        
        return {
            "success": True,
            "total": len(records),
            "valid": len(valid_records),
            "synced": count,
            "skipped": skipped,
            "message": "同步完成"
        }
    
    def sync_all(self, store_id: int = None) -> Dict:
        """同步全部数据（要货 + 耗用）
        
        Args:
            store_id: 门店ID（可选）
        
        Returns:
            同步结果汇总
        """
        logger.info(f"[sync_all] 开始全量同步: store_id={store_id}")
        
        # 同步要货
        supply_result = self.sync_supply_orders(store_id)
        
        # 同步耗用
        consume_result = self.sync_consume_records(store_id)
        
        return {
            "success": True,
            "supply": supply_result,
            "consume": consume_result,
            "message": "全量同步完成"
        }
    
    def get_sync_status(self) -> Dict:
        """获取同步状态"""
        supply_count = db.get_supply_order_count()
        
        conn = db.db_path and __import__('sqlite3').connect(db.db_path)
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM consume_records")
            consume_count = cursor.fetchone()[0]
            conn.close()
        else:
            consume_count = 0
        
        return {
            "supply_count": supply_count,
            "consume_count": consume_count,
            "last_sync": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }


data_sync_service = DataSyncService()