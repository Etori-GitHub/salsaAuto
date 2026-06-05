"""耗用任务服务

管理耗用任务配置和补耗用计算。

新算法：
1. 一次性获取日期范围内所有要货数据
2. 计算每日平均耗用金额（带浮动）
3. 逐日贪心计算耗用方案（优先消耗贵的商品，留便宜的到后面）
4. 最后一天精确补差
5. 批量执行耗用，API成功后同步写入本地数据库
"""

import json
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from collections import defaultdict

from src.services.database import db
from src.services.consume_service import consume_service


class ConsumeTaskService:
    """耗用任务服务"""
    
    def __init__(self):
        self.task_dir = Path(__file__).parent.parent.parent / "data" / "consume-tasks"
        self.task_dir.mkdir(parents=True, exist_ok=True)
    
    def save_task(self, task: Dict) -> Dict:
        """保存耗用任务
        
        Args:
            task: 任务配置
                - store_id: 门店ID
                - store_name: 门店名称
                - start_date: 开始日期
                - end_date: 结束日期
                - total_amount: 目标耗用金额
                - daily_float_percent: 每日浮动百分比（默认0.1）
        
        Returns:
            保存结果
        """
        now = datetime.now()
        task_id = f"consume_{task['store_id']}_{now.strftime('%Y%m%d%H%M%S')}"
        task_name = f"{task['store_name']}_{task['start_date']}-{task['end_date']}"
        
        task_data = {
            "task_id": task_id,
            "task_name": task_name,
            "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "store_id": task["store_id"],
            "store_name": task["store_name"],
            "start_date": task["start_date"],
            "end_date": task["end_date"],
            "total_amount": task["total_amount"],
            "daily_float_percent": task.get("daily_float_percent", 0.1),
        }
        
        # 保存到文件
        task_file = self.task_dir / f"{task_id}.json"
        with open(task_file, "w", encoding="utf-8") as f:
            json.dump(task_data, f, indent=2, ensure_ascii=False)
        
        return {
            "success": True,
            "task_id": task_id,
            "message": "任务保存成功"
        }
    
    def get_task_list(self) -> List[Dict]:
        """获取所有耗用任务"""
        tasks = []
        for task_file in sorted(self.task_dir.glob("consume_*.json"), reverse=True):
            try:
                with open(task_file, "r", encoding="utf-8") as f:
                    tasks.append(json.load(f))
            except Exception as e:
                print(f"读取任务文件失败: {task_file}, {e}")
        return tasks
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取单个任务详情"""
        task_file = self.task_dir / f"{task_id}.json"
        if not task_file.exists():
            return None
        
        with open(task_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def generate_consume_plan(self, task: Dict) -> Dict:
        """生成耗用方案（新算法）
        
        Args:
            task: 任务配置
        
        Returns:
            耗用方案
        """
        store_id = task["store_id"]
        start_date = datetime.strptime(task["start_date"], "%Y-%m-%d")
        end_date = datetime.strptime(task["end_date"], "%Y-%m-%d")
        total_amount = task["total_amount"]
        daily_float = task.get("daily_float_percent", 0.1)
        
        # 计算天数
        days = (end_date - start_date).days + 1
        if days <= 0:
            return {"success": False, "message": "日期范围无效"}
        
        # 1. 获取日期范围内所有要货数据
        supply_records = db.get_supply_order_details(
            store_id=store_id,
            start_date=task["start_date"],
            end_date=task["end_date"],
            limit=100000
        )
        
        if not supply_records:
            return {"success": False, "message": "未找到要货数据，请先同步"}
        
        # 2. 获取商品信息
        product_ids = list(set(r["product_id"] for r in supply_records))
        goods_info = db.get_goods_by_ids(product_ids)
        
        # 3. 按日期分组要货数据
        supply_by_date = defaultdict(list)
        for r in supply_records:
            date_str = r["create_time"][:10] if r.get("create_time") else ""
            if date_str:
                supply_by_date[date_str].append(r)
        
        # 4. 初始化库存 dict
        # stock = {product_id: {"quantity": float, "unit_price": float, "product_name": str}}
        stock = {}
        
        # 5. 计算每日平均耗用金额
        base_daily_amount = total_amount / days
        
        # 6. 逐日计算耗用方案
        daily_plans = []
        accumulated_amount = 0.0
        
        date_range = [start_date + timedelta(days=i) for i in range(days)]
        
        for i, date in enumerate(date_range):
            date_str = date.strftime("%Y-%m-%d")
            is_last_day = (i == days - 1)
            
            # 加上当天的要货
            day_supply = supply_by_date.get(date_str, [])
            for item in day_supply:
                pid = item["product_id"]
                quantity = item.get("quantity", 0) or 0
                goods = goods_info.get(pid, {})
                # 从商品库取价格（成本价）
                goods_unit_price = goods.get("unit_price") or goods.get("true_price") or 0
                
                if pid not in stock:
                    stock[pid] = {
                        "quantity": 0.0,
                        "unit_price": goods_unit_price,  # 用商品库的价格
                        "product_name": goods.get("product_name", item.get("product_name", "")),
                        "product_code": goods.get("product_code", item.get("product_code", "")),
                        "category_name": goods.get("category_name", ""),
                        "cang_sub_category_name": goods.get("cang_sub_category_name", ""),
                        "spec_name": goods.get("spec_name", ""),
                        "unit": goods.get("unit", item.get("unit", "")),
                    }
                
                stock[pid]["quantity"] += quantity
            
            # 计算当日目标耗用金额
            if is_last_day:
                # 最后一天：精确补差
                target_amount = round(total_amount - accumulated_amount, 2)
            else:
                # 带浮动
                float_factor = 1 + random.uniform(-daily_float, daily_float)
                target_amount = base_daily_amount * float_factor
                # 确保不超过剩余目标
                remaining = total_amount - accumulated_amount
                target_amount = min(target_amount, remaining * 0.9)  # 留一些给后面
            
            # 贪心算法计算当日耗用方案
            consume_plan, consume_amount = self._greedy_consume(stock, target_amount, is_last_day)
            
            daily_plans.append({
                "date": date_str,
                "target_amount": round(target_amount, 2),
                "consume_plan": consume_plan,
                "consume_amount": round(consume_amount, 2),
            })
            
            accumulated_amount += consume_amount
            
            # 扣减库存
            for item in consume_plan:
                pid = item["product_id"]
                stock[pid]["quantity"] -= item["quantity"]
        
        # 验算
        total_planned = sum(p["consume_amount"] for p in daily_plans)
        diff = round(total_amount - total_planned, 2)
        
        return {
            "success": True,
            "days": days,
            "total_amount": total_amount,
            "total_planned": round(total_planned, 2),
            "diff": diff,
            "daily_plans": daily_plans,
            "message": "OK" if abs(diff) < 0.01 else f"差额: {diff}"
        }
    
    def _greedy_consume(self, stock: Dict, target_amount: float, is_last_day: bool) -> tuple:
        """贪心算法：优先消耗便宜的商品
        
        Args:
            stock: 库存 dict
            target_amount: 目标耗用金额
            is_last_day: 是否最后一天
        
        Returns:
            (consume_plan, consume_amount)
        """
        # 按单价排序（贵 → 便宜），优先消耗贵的，留便宜的到后面
        products = sorted(
            [(pid, info) for pid, info in stock.items() if info["quantity"] > 0],
            key=lambda x: x[1]["unit_price"],
            reverse=True  # 降序：贵的在前
        )
        
        if not products:
            return [], 0.0
        
        consume_plan = []
        remaining = target_amount
        total_consume = 0.0
        
        for i, (pid, info) in enumerate(products):
            quantity = info["quantity"]
            unit_price = info["unit_price"]
            
            if quantity <= 0 or unit_price <= 0:
                continue
            
            # 计算可消耗数量
            max_by_amount = remaining / unit_price
            max_consume = min(quantity, max_by_amount)
            
            # 每个品至少消耗1单位（最后一天除外）
            if not is_last_day and i < len(products) - 1:
                min_consume = min(1.0, quantity)
                max_consume = max(min_consume, max_consume)
            
            # 四舍五入到2位小数
            consume_quantity = round(max_consume, 2)
            
            if consume_quantity <= 0:
                continue
            
            consume_amount = round(consume_quantity * unit_price, 2)
            
            consume_plan.append({
                "product_id": pid,
                "product_name": info["product_name"],
                "product_code": info["product_code"],
                "category_name": info["category_name"],
                "cang_sub_category_name": info["cang_sub_category_name"],
                "spec_name": info["spec_name"],
                "unit": info["unit"],
                "quantity": consume_quantity,
                "unit_price": unit_price,
                "amount": consume_amount,
            })
            
            remaining -= consume_amount
            total_consume += consume_amount
            
            if remaining <= 0.01:
                break
        
        return consume_plan, round(total_consume, 2)
    
    def execute_plan(self, store_id: int, store_name: str, daily_plans: List[Dict]) -> Dict:
        """执行耗用方案
        
        Args:
            store_id: 门店ID
            store_name: 门店名称
            daily_plans: 每日耗用方案
        
        Returns:
            执行结果
        """
        execution_results = []
        total_success = 0
        total_failed = 0
        total_records = 0
        
        for day_plan in daily_plans:
            date = day_plan["date"]
            consume_plan = day_plan["consume_plan"]
            
            if not consume_plan:
                execution_results.append({
                    "date": date,
                    "status": "skipped",
                    "message": "无耗用方案"
                })
                continue
            
            # 生成随机时间（10:00 - 20:00）
            hour = random.randint(10, 19)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            execute_time = f"{date} {hour:02d}:{minute:02d}:{second:02d}"
            
            day_success = 0
            day_failed = 0
            
            for item in consume_plan:
                # 打印调试信息
                print(f"[DEBUG] 创建耗用记录: store_id={store_id}, product_id={item['product_id']}, quantity={item['quantity']}, time={execute_time}")
                
                # 调用 API 创建耗用记录
                result = consume_service.create_consume_record(
                    store_id=store_id,
                    product_id=item["product_id"],
                    quantity=item["quantity"],
                    consume_time=execute_time
                )
                
                if result["success"]:
                    day_success += 1
                    total_records += 1
                    
                    # 写入本地数据库
                    db.add_consume_record({
                        "store_id": store_id,
                        "store_name": store_name,
                        "product_id": item["product_id"],
                        "product_code": item["product_code"],
                        "product_name": item["product_name"],
                        "category_name": item["category_name"],
                        "cang_sub_category_name": item["cang_sub_category_name"],
                        "spec_name": item["spec_name"],
                        "unit": item["unit"],
                        "unit_price": item["unit_price"],
                        "quantity": item["quantity"],
                        "total_amount": item["amount"],
                        "used_time": execute_time,
                        "used_source": "手工补录",
                        "create_time": execute_time,
                    })
                else:
                    day_failed += 1
            
            total_success += day_success
            total_failed += day_failed
            
            execution_results.append({
                "date": date,
                "target_amount": day_plan["target_amount"],
                "consume_amount": day_plan["consume_amount"],
                "success_count": day_success,
                "failed_count": day_failed,
                "status": "success" if day_failed == 0 else "partial",
            })
        
        return {
            "success": total_failed == 0,
            "total_success": total_success,
            "total_failed": total_failed,
            "total_records": total_records,
            "execution_results": execution_results,
            "message": f"执行完成：成功 {total_success} 条，失败 {total_failed} 条"
        }
    
    def execute_task(self, task_id: str) -> Dict:
        """执行完整耗用任务
        
        Args:
            task_id: 任务ID
        
        Returns:
            执行结果
        """
        task = self.get_task(task_id)
        if not task:
            return {"success": False, "message": "任务不存在"}
        
        # 生成耗用方案
        plan_result = self.generate_consume_plan(task)
        if not plan_result["success"]:
            return plan_result
        
        # 执行方案
        exec_result = self.execute_plan(
            store_id=task["store_id"],
            store_name=task.get("store_name", ""),
            daily_plans=plan_result["daily_plans"]
        )
        
        return {
            "success": exec_result["success"],
            "task_id": task_id,
            "plan": {
                "total_amount": plan_result["total_amount"],
                "total_planned": plan_result["total_planned"],
                "diff": plan_result["diff"],
                "days": plan_result["days"],
            },
            "execution": exec_result,
            "message": exec_result["message"]
        }
    
    def preview_task(self, task_id: str) -> Dict:
        """预览耗用方案（不执行）
        
        Args:
            task_id: 任务ID
        
        Returns:
            耗用方案预览
        """
        task = self.get_task(task_id)
        if not task:
            return {"success": False, "message": "任务不存在"}
        
        return self.generate_consume_plan(task)


consume_task_service = ConsumeTaskService()
