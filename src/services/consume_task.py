"""耗用任务服务

管理耗用任务配置和补耗用计算。
"""

import json
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from collections import defaultdict

from src.services.database import db
from src.services.consume_service import consume_service
from src.services.stock_flow import stock_flow_service


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
    
    def calculate_daily_plan(self, task: Dict) -> Dict:
        """计算每日耗用计划
        
        Args:
            task: 任务配置
        
        Returns:
            每日耗用计划
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
        
        # 计算每日基础金额
        base_daily_amount = total_amount / days
        
        # 生成每日金额（带随机浮动）
        daily_amounts = []
        remaining = total_amount
        
        for i in range(days):
            if i == days - 1:
                # 最后一天，用剩余金额
                daily_target = remaining
            else:
                # 随机浮动
                float_factor = 1 + random.uniform(-daily_float, daily_float)
                daily_target = base_daily_amount * float_factor
                daily_target = min(daily_target, remaining)  # 不超过剩余金额
            
            daily_amounts.append({
                "date": (start_date + timedelta(days=i)).strftime("%Y-%m-%d"),
                "target_amount": round(daily_target, 2),
            })
            remaining -= daily_target
        
        # 调整最后一天确保总和精确
        total_planned = sum(d["target_amount"] for d in daily_amounts)
        diff = total_amount - total_planned
        if abs(diff) > 0.01:
            daily_amounts[-1]["target_amount"] += diff
        
        return {
            "success": True,
            "days": days,
            "total_amount": total_amount,
            "daily_plan": daily_amounts,
            "message": "OK"
        }
    
    def get_daily_stock(self, store_id: int, date: str) -> Dict:
        """获取指定日期的库存情况
        
        Args:
            store_id: 门店ID
            date: 日期
        
        Returns:
            当日库存情况（按商品）
        """
        # 从库存流水获取该日期的库存快照
        # 我们需要获取该日期之前的所有流水，计算当日开始时的库存
        
        # 先同步要货和耗用记录（确保数据最新）
        supply_result = stock_flow_service.sync_supply_records(store_id, None, date)
        consume_result = stock_flow_service.sync_consume_records(store_id, None, date)
        
        # 获取库存流水
        flows = db.get_stock_flows(store_id, end_date=date, limit=100000)
        
        # 按商品汇总库存
        product_stock = defaultdict(lambda: {"quantity": 0, "amount": 0})
        product_info = {}  # 商品信息缓存
        
        for flow in flows:
            pid = flow["product_id"]
            
            # 缓存商品信息
            if pid not in product_info:
                product_info[pid] = {
                    "product_id": pid,
                    "product_name": "",  # 需要从其他地方获取
                    "unit_price": flow.get("unit_price", 0),
                }
            
            # 更新库存（取最新的余额）
            product_stock[pid]["quantity"] = flow["balance_quantity"]
            product_stock[pid]["amount"] = flow["balance_amount"]
        
        # 构建返回数据
        stock_list = []
        for pid, stock in product_stock.items():
            if stock["quantity"] > 0:  # 只返回有库存的商品
                stock_list.append({
                    "product_id": pid,
                    "quantity": stock["quantity"],
                    "amount": stock["amount"],
                    "unit_price": product_info[pid]["unit_price"],
                })
        
        return {
            "success": True,
            "store_id": store_id,
            "date": date,
            "products": stock_list,
            "total_quantity": sum(s["quantity"] for s in stock_list),
            "total_amount": sum(s["amount"] for s in stock_list),
            "message": "OK"
        }
    
    def calculate_day_consume(self, store_id: int, date: str, target_amount: float) -> Dict:
        """计算单日耗用方案
        
        Args:
            store_id: 门店ID
            date: 日期
            target_amount: 目标耗用金额
        
        Returns:
            耗用方案（商品列表和数量）
        """
        # 获取当日库存
        stock_result = self.get_daily_stock(store_id, date)
        if not stock_result["success"]:
            return stock_result
        
        products = stock_result["products"]
        total_stock_amount = stock_result["total_amount"]
        
        # 检查库存是否足够
        if total_stock_amount < target_amount:
            return {
                "success": False,
                "message": f"当日库存金额 {total_stock_amount:.2f} 不足以耗用 {target_amount:.2f}",
                "stock_amount": total_stock_amount,
                "target_amount": target_amount,
            }
        
        # 贪心算法：从高价值商品开始分配
        # 按单价排序（从高到低）
        products_sorted = sorted(products, key=lambda x: x["unit_price"], reverse=True)
        
        consume_plan = []
        remaining_amount = target_amount
        
        for product in products_sorted:
            if remaining_amount <= 0.01:
                break
            
            unit_price = product["unit_price"]
            stock_quantity = product["quantity"]
            
            if unit_price <= 0:
                continue
            
            # 计算该商品可以消耗多少
            max_consume_amount = stock_quantity * unit_price
            
            if max_consume_amount >= remaining_amount:
                # 该商品足够完成剩余目标
                consume_quantity = remaining_amount / unit_price
                consume_quantity = min(consume_quantity, stock_quantity)
                consume_amount = consume_quantity * unit_price
                
                consume_plan.append({
                    "product_id": product["product_id"],
                    "quantity": round(consume_quantity, 2),
                    "unit_price": unit_price,
                    "amount": round(consume_amount, 2),
                })
                remaining_amount -= consume_amount
            else:
                # 该商品全部消耗
                consume_plan.append({
                    "product_id": product["product_id"],
                    "quantity": stock_quantity,
                    "unit_price": unit_price,
                    "amount": round(max_consume_amount, 2),
                })
                remaining_amount -= max_consume_amount
        
        # 计算总耗用金额
        total_consume = sum(p["amount"] for p in consume_plan)
        
        return {
            "success": True,
            "date": date,
            "store_id": store_id,
            "target_amount": target_amount,
            "consume_amount": round(total_consume, 2),
            "consume_plan": consume_plan,
            "message": "OK"
        }
    
    def execute_day_consume(self, store_id: int, date: str, consume_plan: List[Dict], execute_time: str = None) -> Dict:
        """执行单日耗用
        
        Args:
            store_id: 门店ID
            date: 日期
            consume_plan: 耗用方案
            execute_time: 执行时间（默认当日随机时间）
        
        Returns:
            执行结果
        """
        if not execute_time:
            # 生成随机时间（10:00 - 20:00）
            hour = random.randint(10, 19)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            execute_time = f"{date} {hour:02d}:{minute:02d}:{second:02d}"
        
        success_count = 0
        failed_count = 0
        results = []
        
        for plan in consume_plan:
            result = consume_service.create_consume_record(
                store_id=store_id,
                product_ids=[plan["product_id"]],
                quantity=plan["quantity"],
                consume_time=execute_time
            )
            
            if result["success"]:
                success_count += 1
                results.append({
                    "product_id": plan["product_id"],
                    "quantity": plan["quantity"],
                    "status": "success"
                })
            else:
                failed_count += 1
                results.append({
                    "product_id": plan["product_id"],
                    "quantity": plan["quantity"],
                    "status": "failed",
                    "error": result["message"]
                })
        
        return {
            "success": failed_count == 0,
            "date": date,
            "execute_time": execute_time,
            "success_count": success_count,
            "failed_count": failed_count,
            "results": results,
            "message": f"成功 {success_count} 条，失败 {failed_count} 条"
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
        
        # 计算每日计划
        plan_result = self.calculate_daily_plan(task)
        if not plan_result["success"]:
            return plan_result
        
        daily_plan = plan_result["daily_plan"]
        
        # 执行每日耗用
        execution_results = []
        total_success = 0
        total_failed = 0
        
        for day_plan in daily_plan:
            date = day_plan["date"]
            target_amount = day_plan["target_amount"]
            
            # 计算当日耗用方案
            consume_result = self.calculate_day_consume(
                task["store_id"], date, target_amount
            )
            
            if not consume_result["success"]:
                execution_results.append({
                    "date": date,
                    "status": "skipped",
                    "message": consume_result["message"]
                })
                continue
            
            # 执行耗用
            exec_result = self.execute_day_consume(
                task["store_id"], date, consume_result["consume_plan"]
            )
            
            execution_results.append({
                "date": date,
                "target_amount": target_amount,
                "actual_amount": consume_result["consume_amount"],
                "status": "success" if exec_result["success"] else "partial",
                "success_count": exec_result["success_count"],
                "failed_count": exec_result["failed_count"],
            })
            
            total_success += exec_result["success_count"]
            total_failed += exec_result["failed_count"]
        
        return {
            "success": True,
            "task_id": task_id,
            "total_success": total_success,
            "total_failed": total_failed,
            "execution_results": execution_results,
            "message": f"任务执行完成：成功 {total_success} 条，失败 {total_failed} 条"
        }


consume_task_service = ConsumeTaskService()