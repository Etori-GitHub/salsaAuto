"""补要货服务

根据任务自动调整要货明细，使总金额匹配任务目标。
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Optional

from src.api.client import api_client
from src.services.database import db
from src.config import config


class SupplyAdjustService:
    """补要货服务"""
    
    def get_task_list(self) -> List[Dict]:
        """获取要货任务列表"""
        tasks_dir = Path(__file__).parent.parent.parent / "data" / "supply-tasks"
        
        if not tasks_dir.exists():
            return []
        
        tasks = []
        for file in sorted(tasks_dir.glob("*.json"), reverse=True):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    tasks.append({
                        "task_id": data.get("task_id"),
                        "task_name": data.get("task_name"),
                        "store_name": data.get("store_name"),
                        "total_amount": data.get("total_amount"),
                        "date_range": data.get("date_range"),
                        "days_count": len(data.get("days", [])),
                        "file_path": str(file)
                    })
            except:
                continue
        
        return tasks
    
    def get_task_detail(self, task_id: str) -> Optional[dict]:
        """获取任务详情"""
        tasks_dir = Path(__file__).parent.parent.parent / "data" / "supply-tasks"
        file_path = tasks_dir / f"{task_id}.json"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None
    
    def query_order_by_code(self, delivery_code: str) -> Optional[dict]:
        """通过订单号查询订单信息，获取 deliveryId"""
        params = [
            ("page", 1),
            ("pageSize", 10),
            ("storeCode", ""),
            ("storeName", ""),
            ("supplierCode", ""),
            ("supplierName", ""),
            ("deliveryCode", delivery_code),
        ]
        
        try:
            result = api_client.get_raw("/restful/shasha/supply/sorders", params=params)
            
            if result.get("code") == 1:
                records = result.get("data", {}).get("records", [])
                if records:
                    return records[0]
            return None
        except Exception as e:
            print(f"查询订单失败: {e}")
            return None
    
    def query_order_by_store_and_date(self, store_code: str, date_str: str) -> Optional[dict]:
        """通过门店+日期查询订单信息"""
        # API 返回的 storeCode 格式是 M00011，需要转换
        api_store_code = f"M{store_code.zfill(5)}" if not store_code.startswith("M") else store_code
        
        params = [
            ("page", 1),
            ("pageSize", 10),
            ("storeCode", api_store_code),
            ("storeName", ""),
            ("supplierCode", ""),
            ("supplierName", ""),
            ("deliveryCode", ""),
            ("createTime", f"{date_str} 00:00:00"),
            ("createTime", f"{date_str} 23:59:59"),
        ]
        
        print(f"查询订单: store_code={api_store_code}, date={date_str}")
        
        try:
            result = api_client.get_raw("/restful/shasha/supply/sorders", params=params)
            
            print(f"订单查询结果: code={result.get('code')}, msg={result.get('msg')}")
            
            if result.get("code") == 1:
                records = result.get("data", {}).get("records", [])
                if records:
                    print(f"找到订单: {records[0].get('deliveryCode')}")
                    return records[0]
            return None
        except Exception as e:
            print(f"查询订单失败: {e}")
            return None
    
    def query_supply_details_by_delivery_code(self, delivery_code: str, store_code: str = "") -> List[dict]:
        """通过订单号查询要货明细
        
        Args:
            delivery_code: 要货单号
            store_code: 门店代码（可选，用于过滤重复的要货单号）
        """
        # 转换门店代码格式（如 "11" -> "M00011"）
        api_store_code = f"M{store_code.zfill(5)}" if store_code and not store_code.startswith("M") else store_code
        
        params = [
            ("page", 1),
            ("pageSize", 1000),
            ("deliveryCode", delivery_code),
            ("detailCode", ""),
            ("storeCode", api_store_code),  # 加上门店代码过滤
            ("storeName", ""),
            ("categoryCode", ""),
            ("categoryName", ""),
            ("subCategoryCode", ""),
            ("subCategoryName", ""),
            ("productCode", ""),
            ("productName", ""),
            ("deliveryId", ""),
        ]
        
        print(f"查询要货明细: delivery_code={delivery_code}, store_code={api_store_code}")
        
        try:
            result = api_client.get_raw("/restful/shasha/supply/sordersDetail", params=params)
            
            print(f"API 返回: code={result.get('code')}, msg={result.get('msg')}")
            
            if result.get("code") == 1:
                records = result.get("data", {}).get("records", [])
                print(f"查询到 {len(records)} 条要货明细")
                return records
            print(f"查询失败: {result}")
            return []
        except Exception as e:
            print(f"查询要货明细失败: {e}")
            return []
    
    def query_supply_details(self, store_code: str, date_str: str) -> List[dict]:
        """查询指定门店+日期的要货明细"""
        import time
        
        # API 返回的 storeCode 格式是 M00011，需要转换
        api_store_code = f"M{store_code.zfill(5)}" if not store_code.startswith("M") else store_code
        
        params = [
            ("page", 1),
            ("pageSize", 500),
            ("storeCode", api_store_code),
            ("storeName", ""),
            ("deliveryCode", ""),
            ("detailCode", ""),
            ("categoryCode", ""),
            ("categoryName", ""),
            ("subCategoryCode", ""),
            ("subCategoryName", ""),
            ("productCode", ""),
            ("productName", ""),
            ("deliveryId", ""),
            ("createTime", f"{date_str} 00:00:00"),  # 开始时间
            ("createTime", f"{date_str} 23:59:59"),  # 结束时间（同名参数）
            ("_t", str(int(time.time() * 1000))),  # 加时间戳防止缓存
        ]
        
        print(f"查询要货明细: store_code={store_code}, date={date_str}")
        
        try:
            result = api_client.get_raw("/restful/shasha/supply/sordersDetail", params=params)
            
            print(f"API 返回: code={result.get('code')}, msg={result.get('msg')}")
            
            if result.get("code") == 1:
                records = result.get("data", {}).get("records", [])
                print(f"查询到 {len(records)} 条要货明细")
                if records:
                    print(f"第一条明细: storeCode={records[0].get('storeCode')}, storeName={records[0].get('storeName')}, deliveryCode={records[0].get('deliveryCode')}")
                return records
            print(f"查询失败: {result}")
            return []
        except Exception as e:
            print(f"查询要货明细失败: {e}")
            return []
    
    def update_can_show(self, detail_id: int, value: int) -> bool:
        """更新明细的 canShow 状态"""
        url = f"{config.api_base_url}/restful/shasha/supply/sordersDetail/updateField"
        params = {
            "field": "can_show",
            "value": value,
            "id": detail_id
        }
        
        try:
            response = api_client.session.post(url, params=params, timeout=10, verify=False)
            result = response.json()
            return result.get("code") == 1
        except Exception as e:
            print(f"更新 canShow 失败: {e}")
            return False
    
    def update_create_time(self, detail_id: int, create_time: str) -> bool:
        """更新明细的创建时间
        
        Args:
            detail_id: 明细ID
            create_time: 创建时间，格式如 "2026-03-25 20:38:58"
        """
        url = f"{config.api_base_url}/restful/shasha/supply/sordersDetail/updateField"
        params = {
            "field": "create_time",
            "value": create_time,
            "id": detail_id
        }
        
        try:
            response = api_client.session.post(url, params=params, timeout=10, verify=False)
            result = response.json()
            print(f"更新创建时间: detail_id={detail_id}, time={create_time}, 结果: {result}")
            return result.get("code") == 1
        except Exception as e:
            print(f"更新创建时间失败: {e}")
            return False
    
    def add_order_item(self, delivery_id: int, product_id: int, sub_category_id: int, 
                       category_type: int, quantity: float) -> dict:
        """添加订货明细
        
        Args:
            delivery_id: 订单ID
            product_id: 商品ID
            sub_category_id: 子分类ID
            category_type: 分类类型 (4=贸易品, 5=加工品, 6=现采)
            quantity: 数量
        
        Returns:
            {"success": bool, "message": str}
        """
        url = f"{config.api_base_url}/restful/shasha/supply/sordersDetail"
        
        # productIdStr 格式: ["{category_type}","{sub_category_id}","{product_id}"]
        product_id_str = json.dumps([str(category_type), str(sub_category_id), str(product_id)])
        
        data = {
            "deliveryId": delivery_id,
            "productIdStr": product_id_str,
            "orderQuantity": quantity,
            "deliveredQuantity": quantity,
            "splitStatus": 1,
            "returnStatus": 0,
            "receiveStatus": 1
        }
        
        try:
            response = api_client.session.post(url, data=data, timeout=10, verify=False)
            result = response.json()
            print(f"添加订货 API 响应: {result}")
            if result.get("code") == 1:
                return {"success": True, "message": "OK"}
            else:
                return {"success": False, "message": result.get("msg", "未知错误")}
        except Exception as e:
            print(f"添加订货失败: {e}")
            return {"success": False, "message": str(e)}
    
    def get_available_products(self, category_type: int, existing_product_ids: set) -> List[dict]:
        """从本地商品库获取可用的商品
        
        Args:
            category_type: 分类类型 (5=加工品, 6=现采)
            existing_product_ids: 已存在的商品ID集合
        """
        conn = db.db_path and __import__('sqlite3').connect(db.db_path)
        if not conn:
            return []
        
        cursor = conn.cursor()
        
        # 查询上架状态的指定类型商品
        if category_type == 6:
            # 现采品：category_id=6, sub_category_id=21
            cursor.execute("""
                SELECT id, product_name, unit_price, sub_category_id 
                FROM goods 
                WHERE category_id = 6 AND sub_category_id = 21
                ORDER BY unit_price DESC
            """)
        else:
            # 加工品：category_id=5
            cursor.execute("""
                SELECT id, product_name, unit_price, sub_category_id 
                FROM goods 
                WHERE category_id = 5
                ORDER BY unit_price DESC
            """)
        
        rows = cursor.fetchall()
        conn.close()
        
        products = []
        for row in rows:
            product_id = row[0]
            if product_id not in existing_product_ids:
                products.append({
                    "id": product_id,
                    "name": row[1],
                    "price": row[2],
                    "sub_category_id": row[3]
                })
        
        return products
    
    def adjust_day(self, store_code: str, store_name: str, date_str: str, target_amount: float) -> dict:
        """调整单日的要货明细
        
        Args:
            store_code: 门店代码
            store_name: 门店名称
            date_str: 日期字符串
            target_amount: 目标金额
        
        Returns:
            调整结果
        """
        result = {
            "date": date_str,
            "store": store_name,
            "target": target_amount,
            "success": False,
            "message": "",
            "actions": []
        }
        
        # 1. 先查询订单列表，获取 delivery_code
        order_info = self.query_order_by_store_and_date(store_code, date_str)
        
        if not order_info:
            result["message"] = f"该日期无订单 (门店={store_name}, 日期={date_str})"
            result["success"] = True  # 标记为成功，跳过处理
            print(result["message"])
            return result
        
        delivery_code = order_info.get("deliveryCode")
        delivery_id = order_info.get("id")
        
        print(f"找到订单: deliveryCode={delivery_code}, deliveryId={delivery_id}")
        
        result["delivery_code"] = delivery_code
        result["delivery_id"] = delivery_id
        
        # 2. 用 delivery_code + store_code 查询明细
        details = self.query_supply_details_by_delivery_code(delivery_code, store_code)
        
        print(f"查询明细结果: 明细数={len(details) if details else 0}")
        
        # 2. 计算当前显示金额
        visible_details = [d for d in details if d.get("canShow") == 1]
        current_amount = sum(d.get("totalPriceD", 0) or 0 for d in visible_details)
        
        print(f"当前金额: {current_amount}, 目标金额: {target_amount}, 明细数: {len(details)}, 显示数: {len(visible_details)}")
        
        result["original_amount"] = current_amount
        result["delivery_code"] = delivery_code
        result["delivery_id"] = delivery_id
        
        # 已存在的商品ID集合
        existing_product_ids = set(d.get("productId") for d in details)
        # 已存在的明细ID集合（用于后续判断新添加的明细）
        existing_detail_ids = set(d.get("id") for d in details)
        
        # 3. 检查是否已经匹配（误差小于0.1元）
        diff = target_amount - current_amount
        if abs(diff) < 0.1:
            result["success"] = True
            result["message"] = f"金额已匹配: ¥{current_amount:.2f}"
            result["final_amount"] = current_amount
            result["final_diff"] = abs(diff)
            return result
        
        # 4. 判断是否需要关闭条目
        if current_amount > target_amount:
            # 需要关闭条目，使总金额略小于目标
            excess = current_amount - target_amount
            
            # 按金额排序，从金额相近的开始关闭
            sorted_details = sorted(visible_details, key=lambda d: abs((d.get("totalPriceD", 0) or 0) - excess))
            
            closed_count = 0
            for detail in sorted_details:
                if current_amount <= target_amount:
                    break
                
                detail_amount = detail.get("totalPriceD", 0) or 0
                detail_id = detail.get("id")
                
                if self.update_can_show(detail_id, 0):
                    current_amount -= detail_amount
                    closed_count += 1
                    result["actions"].append(f"关闭: {detail.get('productName')} ¥{detail_amount:.2f}")
            
            result["actions"].append(f"共关闭 {closed_count} 个条目")
        
        # 4. 计算差额
        diff = target_amount - current_amount
        diff_cents = round(diff * 100)
        
        result["diff_after_close"] = diff
        
        # 5. 添加加工品（如果差额 > 10元）
        if diff_cents > 1000:
            processed_products = self.get_available_products(5, existing_product_ids)
            
            for product in processed_products:
                if diff_cents <= 1000:
                    break
                
                price = product["price"]
                if price <= 0:
                    continue
                
                # 计算最大可购买数量（金额 < 差额，数量 < 10）
                max_qty_by_amount = int(diff_cents / 100 / price)
                max_qty = min(9, max_qty_by_amount)
                
                if max_qty < 1:
                    continue
                
                # 随机选择数量
                qty = random.randint(1, max_qty)
                item_amount = round(price * qty, 2)
                
                add_result = self.add_order_item(delivery_id, product["id"], product["sub_category_id"], 5, qty)
                if add_result.get("success"):
                    current_amount += item_amount
                    diff_cents = round((target_amount - current_amount) * 100)
                    existing_product_ids.add(product["id"])
                    result["actions"].append(f"添加加工品: {product['name']} x{qty} ¥{item_amount:.2f}")
                else:
                    result["actions"].append(f"添加加工品失败: {product['name']} - {add_result.get('message')}")
        
        # 6. 添加补差价商品（加工品-特殊）
        # 8919=1元, 8918=1分, 8917=1角
        # 不限制数量，不判断重复
        if diff_cents > 0:
            # 按金额从大到小尝试
            adjust_products = [
                (8919, 100),  # 1元 = 100分
                (8917, 10),   # 1角 = 10分
                (8918, 1),    # 1分
            ]
            
            for product_id, price_cents in adjust_products:
                while diff_cents >= price_cents:
                    qty = diff_cents // price_cents
                    
                    if qty > 0:
                        item_amount = qty * price_cents / 100
                        add_result = self.add_order_item(delivery_id, product_id, 25, 5, qty)
                        print(f"添加补差价商品: {product_id} x{qty} ¥{item_amount:.2f}, 结果: {add_result}")
                        
                        if add_result.get("success"):
                            current_amount += item_amount
                            diff_cents = round((target_amount - current_amount) * 100)
                            result["actions"].append(f"添加补差价: {product_id} x{qty} ¥{item_amount:.2f}")
                        else:
                            result["actions"].append(f"添加失败: {product_id} - {add_result.get('message')}")
                            break
                    
                    if diff_cents <= 0:
                        break
                
                if diff_cents <= 0:
                    break
        
        # 7. 修改新添加明细的创建时间
        # 用 delivery_code + store_code 重新查询明细，找出新添加的
        final_details = self.query_supply_details_by_delivery_code(delivery_code, store_code)
        
        # 找出新添加的明细（ID 不在 existing_detail_ids 中）
        new_detail_ids = []
        for detail in final_details:
            detail_id = detail.get("id")
            if detail_id and detail_id not in existing_detail_ids:
                new_detail_ids.append(detail_id)
        
        print(f"新添加的明细ID: {new_detail_ids}")
        
        # 生成随机时间（20:00-23:00）
        random_hour = random.randint(20, 22)
        random_minute = random.randint(0, 59)
        random_second = random.randint(0, 59)
        new_create_time = f"{date_str} {random_hour:02d}:{random_minute:02d}:{random_second:02d}"
        
        # 只修改新添加的明细
        updated_count = 0
        for detail_id in new_detail_ids:
            if self.update_create_time(detail_id, new_create_time):
                updated_count += 1
        
        if updated_count > 0:
            result["actions"].append(f"已修改 {updated_count} 条明细的创建时间为 {new_create_time}")
        
        # 8. 验算（重新查询要货明细）
        final_amount = sum(d.get("totalPriceD", 0) or 0 for d in final_details if d.get("canShow") == 1)
        final_diff = abs(target_amount - final_amount)
        
        result["final_amount"] = final_amount
        result["final_diff"] = final_diff
        
        if final_diff < 0.1:
            result["success"] = True
            result["message"] = f"调整成功: ¥{current_amount:.2f}"
        else:
            result["message"] = f"调整完成，存在误差: ¥{final_diff:.2f}"
        
        return result
    
    def execute_task(self, task_id: str) -> dict:
        """执行补要货任务
        
        Args:
            task_id: 任务ID
        
        Returns:
            执行结果
        """
        task = self.get_task_detail(task_id)
        
        if not task:
            return {"success": False, "message": "任务不存在"}
        
        store_id = task.get("store_id")
        store_name = task.get("store_name")
        days = task.get("days", [])
        
        if not days:
            return {"success": False, "message": "任务无日期数据"}
        
        results = []
        success_count = 0
        
        for day in days:
            date_str = day.get("date")
            target_amount = day.get("amount")
            
            day_result = self.adjust_day(store_id, store_name, date_str, target_amount)
            results.append(day_result)
            
            if day_result.get("success"):
                success_count += 1
        
        return {
            "success": success_count == len(days),
            "message": f"完成 {success_count}/{len(days)} 天",
            "total_days": len(days),
            "success_days": success_count,
            "results": results
        }


supply_adjust_service = SupplyAdjustService()
