"""库存流水服务

从本地数据库查询要货和耗用数据,合并计算库存流水。
数据需要先通过「同步数据」按钮从 API 拉取到本地。
"""

import logging
import traceback
from datetime import datetime
from typing import Optional, Dict, List
from collections import defaultdict

from src.services.supply_query import supply_query_service
from src.services.consume_query import consume_query_service
from src.services.database import db

logger = logging.getLogger(__name__)


class StockFlowService:
    """库存流水服务"""

    def sync_supply_orders(self, store_id: int = None) -> Dict:
        """同步要货明细到本地数据库"""
        logger.info(f"[sync_supply_orders] 开始同步: store_id={store_id}")
        print(f"[sync_supply_orders] 开始同步: store_id={store_id}")

        try:
            store_code = f"M{str(store_id).zfill(5)}" if store_id else None

            # 拉取全部数据,不传时间参数,pageSize=10000
            result = supply_query_service.query_all_supply_orders(
                store_code=store_code,
                page_size=10000
            )

            if not result.get("success"):
                error_msg = result.get('message', '未知错误')
                logger.error(f"[sync_supply_orders] API查询失败: {error_msg}")
                print(f"[sync_supply_orders] API查询失败: {error_msg}")
                return result

            records = result.get("records", [])
            logger.info(f"[sync_supply_orders] API返回 {len(records)} 条记录")
            print(f"[sync_supply_orders] API返回 {len(records)} 条记录")

            # 解析并过滤有效数据
            valid_records = []
            skipped = 0

            for r in records:
                if r.get("canShow") != 1:
                    skipped += 1
                    continue

                record_store_id = r.get("storeId")
                record_product_id = r.get("productId")

                if not record_store_id or not record_product_id:
                    skipped += 1
                    continue

                # 不再过滤时间,拉取全部数据
                quantity = r.get("orderQuantity", 0) or r.get("quantity", 0) or 0
                if quantity <= 0:
                    skipped += 1
                    continue

                unit_price = r.get("unitPrice", 0) or 0
                create_time = r.get("createTime", "")

                valid_records.append({
                    "id": r.get("id"),
                    "store_id": record_store_id,
                    "store_name": r.get("storeName", ""),
                    "product_id": record_product_id,
                    "product_code": r.get("productCode", ""),
                    "product_name": r.get("productName", ""),
                    "category_name": r.get("productCategoryName", ""),
                    "sub_category_name": r.get("productSubcategoryName", ""),
                    "cang_sub_category_name": r.get("cangSubCategoryName", ""),
                    "spec_name": "",
                    "unit": r.get("unit", ""),
                    "unit_price": unit_price,
                    "quantity": quantity,
                    "total_amount": quantity * unit_price,
                    "create_time": create_time,
                    "delivery_code": r.get("deliveryCode", ""),
                    "can_show": 1,
                })

            logger.info(f"[sync_supply_orders] 有效记录: {len(valid_records)},跳过: {skipped}")

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

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[sync_supply_orders] 异常: {error_msg}")
            logger.error(traceback.format_exc())
            print(f"[sync_supply_orders] 异常: {error_msg}")
            traceback.print_exc()
            return {"success": False, "message": error_msg}

    def sync_consume_records(self, store_id: int = None) -> Dict:
        """同步耗用记录到本地数据库"""
        logger.info(f"[sync_consume_records] 开始同步: store_id={store_id}")
        print(f"[sync_consume_records] 开始同步: store_id={store_id}")

        try:
            # 拉取全部数据,不传时间参数
            result = consume_query_service.query_all_consume_records(
                store_id=store_id,
                page_size=10000  # 一次性取完
            )

            if not result.get("success"):
                error_msg = result.get('message', '未知错误')
                logger.error(f"[sync_consume_records] API查询失败: {error_msg}")
                print(f"[sync_consume_records] API查询失败: {error_msg}")
                return result

            records = result.get("records", [])
            logger.info(f"[sync_consume_records] API返回 {len(records)} 条记录")
            print(f"[sync_consume_records] API返回 {len(records)} 条记录")

            valid_records = []
            skipped = 0

            for r in records:
                parsed = consume_query_service.parse_consume_record(r)

                if store_id and parsed.get("store_id") != store_id:
                    skipped += 1
                    continue

                if not parsed.get("store_id") or not parsed.get("product_id"):
                    skipped += 1
                    continue

                if parsed.get("quantity", 0) <= 0:
                    skipped += 1
                    continue

                # 不再过滤时间,拉取全部数据
                valid_records.append(parsed)

            logger.info(f"[sync_consume_records] 有效记录: {len(valid_records)},跳过: {skipped}")

            count = db.sync_consume_records(valid_records)
            logger.info(f"[sync_consume_records] 同步完成: {count} 条记录")

            return {
                "success": True,
                "total": len(records),
                "valid": len(valid_records),
                "synced": count,
                "skipped": skipped,
                "message": "同步完成"
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[sync_consume_records] 异常: {error_msg}")
            logger.error(traceback.format_exc())
            print(f"[sync_consume_records] 异常: {error_msg}")
            traceback.print_exc()
            return {"success": False, "message": error_msg}

    def sync_all(self, store_id: int = None) -> Dict:
        """同步全部数据(要货 + 耗用)"""
        logger.info(f"[sync_all] 开始全量同步: store_id={store_id}")

        supply_result = self.sync_supply_orders(store_id)
        consume_result = self.sync_consume_records(store_id)

        return {
            "success": True,
            "supply": supply_result,
            "consume": consume_result,
            "message": "全量同步完成"
        }

    def get_stock_flows(
        self,
        store_id: Optional[int] = None,
        product_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 10000
    ) -> Dict:
        """获取库存流水(从本地数据库)"""
        logger.info(f"[get_stock_flows] 查询: store_id={store_id}, product_id={product_id}")

        if not start_date:
            start_date = "2026-01-01"
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        supply_records = db.get_supply_order_details(
            store_id=store_id,
            product_id=product_id,
            start_date=start_date,
            end_date=end_date,
            limit=100000
        )
        logger.info(f"[get_stock_flows] 要货记录: {len(supply_records)} 条")

        consume_records = db.get_consume_records(
            store_id=store_id,
            product_id=product_id,
            start_time=start_date,
            end_time=end_date,
            limit=100000
        )
        logger.info(f"[get_stock_flows] 耗用记录: {len(consume_records)} 条")

        all_flows = []

        for r in supply_records:
            create_time = r.get("create_time", "")
            flow_date = create_time[:10] if create_time else ""

            all_flows.append({
                "store_id": r.get("store_id"),
                "store_name": r.get("store_name", ""),
                "product_id": r.get("product_id"),
                "product_name": r.get("product_name", ""),
                "category_name": r.get("category_name", ""),
                "sub_category_name": r.get("sub_category_name", ""),
                "cang_sub_category_name": r.get("cang_sub_category_name", ""),
                "spec_name": r.get("spec_name", ""),
                "unit": r.get("unit", ""),
                "unit_price": r.get("unit_price", 0),
                "flow_type": "supply",
                "quantity": r.get("quantity", 0),
                "amount": r.get("total_amount", 0),
                "flow_date": flow_date,
                "flow_time": create_time,
            })

        for r in consume_records:
            used_time = r.get("used_time", "")
            flow_date = used_time[:10] if used_time else ""

            all_flows.append({
                "store_id": r.get("store_id"),
                "store_name": r.get("store_name", ""),
                "product_id": r.get("product_id"),
                "product_name": r.get("product_name", ""),
                "category_name": r.get("category_name", ""),
                "sub_category_name": r.get("sub_category_name", ""),
                "cang_sub_category_name": r.get("cang_sub_category_name", ""),
                "spec_name": r.get("spec_name", ""),
                "unit": r.get("unit", ""),
                "unit_price": r.get("unit_price", 0),
                "flow_type": "consume",
                "quantity": r.get("quantity", 0),
                "amount": r.get("total_amount", 0),
                "flow_date": flow_date,
                "flow_time": used_time,
            })

        all_flows.sort(key=lambda x: x.get("flow_time", ""))

        product_balance = defaultdict(lambda: {"quantity": 0, "amount": 0})

        for flow in all_flows:
            key = (flow["store_id"], flow["product_id"])

            if flow["flow_type"] == "supply":
                product_balance[key]["quantity"] += flow["quantity"]
                product_balance[key]["amount"] += flow["amount"]
            else:
                product_balance[key]["quantity"] -= flow["quantity"]
                product_balance[key]["amount"] -= flow["amount"]

            flow["balance_quantity"] = product_balance[key]["quantity"]
            flow["balance_amount"] = product_balance[key]["amount"]

        total_supply = sum(f["quantity"] for f in all_flows if f["flow_type"] == "supply")
        total_supply_amount = sum(f["amount"] for f in all_flows if f["flow_type"] == "supply")
        total_consume = sum(f["quantity"] for f in all_flows if f["flow_type"] == "consume")
        total_consume_amount = sum(f["amount"] for f in all_flows if f["flow_type"] == "consume")

        all_flows.reverse()
        all_flows = all_flows[:limit]

        return {
            "success": True,
            "flows": all_flows,
            "total_count": len(all_flows),
            "summary": {
                "supply_count": len([f for f in all_flows if f["flow_type"] == "supply"]),
                "supply_quantity": total_supply,
                "supply_amount": total_supply_amount,
                "consume_count": len([f for f in all_flows if f["flow_type"] == "consume"]),
                "consume_quantity": total_consume,
                "consume_amount": total_consume_amount,
            },
            "message": "OK"
        }

    def get_current_stock(self, store_id: int = None, product_id: int = None) -> Dict:
        """获取当前库存"""
        logger.info(f"[get_current_stock] 查询: store_id={store_id}, product_id={product_id}")

        result = self.get_stock_flows(store_id=store_id, product_id=product_id, limit=100000)

        if not result["success"]:
            return result

        flows = result["flows"]

        product_stock = defaultdict(lambda: {"quantity": 0, "amount": 0, "product_name": "", "unit": "", "store_name": ""})

        for flow in flows:
            key = (flow["store_id"], flow["product_id"])

            product_stock[key]["product_name"] = flow.get("product_name", "")
            product_stock[key]["unit"] = flow.get("unit", "")
            product_stock[key]["store_name"] = flow.get("store_name", "")
            product_stock[key]["quantity"] = flow.get("balance_quantity", 0)
            product_stock[key]["amount"] = flow.get("balance_amount", 0)

        # 收集所有商品ID，从商品库查询分类、档口、规格
        all_product_ids = list(set(p_id for (s_id, p_id) in product_stock.keys()))
        goods_info = db.get_goods_by_ids(all_product_ids)

        stock_list = []
        for (s_id, p_id), stock in product_stock.items():
            # 从商品库获取分类、档口、规格
            goods = goods_info.get(p_id, {})
            
            stock_list.append({
                "store_id": s_id,
                "product_id": p_id,
                "product_name": stock["product_name"],
                "store_name": stock["store_name"],
                "category_name": goods.get("category_name", ""),
                "cang_sub_category_name": goods.get("cang_sub_category_name", ""),
                "spec_name": goods.get("spec_name", ""),
                "unit": stock["unit"],
                "quantity": stock["quantity"],
                "amount": stock["amount"],
            })

        stock_list.sort(key=lambda x: abs(x["amount"]), reverse=True)

        return {
            "success": True,
            "stocks": stock_list,
            "total_quantity": sum(s["quantity"] for s in stock_list),
            "total_amount": sum(s["amount"] for s in stock_list),
            "message": "OK"
        }

    def get_sync_status(self) -> Dict:
        """获取同步状态"""
        supply_count = db.get_supply_order_count()

        import sqlite3
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM consume_records WHERE used_time >= '2026-01-01'")
        consume_count = cursor.fetchone()[0]
        conn.close()

        return {
            "success": True,
            "supply_count": supply_count,
            "consume_count": consume_count,
            "last_sync": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }


stock_flow_service = StockFlowService()
