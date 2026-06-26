"""耗用任务服务

管理耗用任务配置和补耗用计算。

新算法（V2）：
1. 任务只保存门店、日期范围、目标金额
2. 执行时逐日处理：
   - 调用库存查询获取当前库存池
   - 贪心算法从库存池选商品生成耗用 list
   - 调用 API 执行耗用
   - API 成功后立即写入本地数据库
3. 非最后一天剔除小金额商品（8970/8971/8972/8973）
4. 最后一天保留小金额商品用于精确补差
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


# 小金额商品ID（用于最后一天补差）
SMALL_AMOUNT_PRODUCTS = [8970, 8971, 8972, 8973]


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
    
    def generate_consume_plan_preview(self, task: Dict) -> Dict:
        """生成耗用方案预览（只估算金额，不生成具体商品列表）
        
        Args:
            task: 任务配置
                - excluded_dates: 排除的日期列表
        
        Returns:
            耗用方案预览
        """
        start_date = datetime.strptime(task["start_date"], "%Y-%m-%d")
        end_date = datetime.strptime(task["end_date"], "%Y-%m-%d")
        total_amount = task["total_amount"]
        daily_float = task.get("daily_float_percent", 0.1)
        excluded_dates = set(task.get("excluded_dates", []))
        
        # 生成所有日期列表
        all_dates = []
        current = start_date
        while current <= end_date:
            all_dates.append(current)
            current += timedelta(days=1)
        
        if not all_dates:
            return {"success": False, "message": "日期范围无效"}
        
        # 计算有效日期
        effective_dates = [d for d in all_dates if d.strftime("%Y-%m-%d") not in excluded_dates]
        effective_days = len(effective_dates)
        
        if effective_days <= 0:
            return {"success": False, "message": "所有日期都被排除，没有有效的执行日期"}
        
        # 计算每日目标金额（带浮动）
        base_daily_amount = total_amount / effective_days
        
        daily_plans = []
        accumulated_target = 0.0
        
        for i, date in enumerate(all_dates):
            date_str = date.strftime("%Y-%m-%d")
            is_excluded = date_str in excluded_dates
            
            if is_excluded:
                daily_plans.append({
                    "date": date_str,
                    "target_amount": 0,
                    "consume_plan": [],
                    "consume_amount": 0,
                    "is_excluded": True,
                })
                continue
            
            # 是否最后一天
            is_last_day = (i == len(all_dates) - 1) or (
                i < len(all_dates) - 1 and all_dates[i+1].strftime("%Y-%m-%d") in excluded_dates
            )
            # 更精确判断：是否最后一个有效日期
            remaining_effective = [d for d in all_dates[i:] if d.strftime("%Y-%m-%d") not in excluded_dates]
            is_last_effective_day = len(remaining_effective) == 1
            
            if is_last_effective_day:
                # 最后一天：精确补差
                target_amount = round(total_amount - accumulated_target, 2)
            else:
                # 带浮动
                float_factor = 1 + random.uniform(-daily_float, daily_float)
                target_amount = base_daily_amount * float_factor
            
            daily_plans.append({
                "date": date_str,
                "target_amount": round(target_amount, 2),
                "consume_plan": [],  # 执行时才生成
                "consume_amount": 0,  # 执行时才计算
                "is_excluded": False,
            })
            accumulated_target += target_amount
        
        # 计算总目标
        total_target = sum(p["target_amount"] for p in daily_plans if not p.get("is_excluded"))
        diff = round(total_amount - total_target, 2)
        
        return {
            "success": True,
            "days": effective_days,
            "total_amount": total_amount,
            "total_planned": round(total_target, 2),
            "diff": diff,
            "daily_plans": daily_plans,
            "message": "OK"
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
        
        # 执行方案
        exec_result = self.execute_plan(
            store_id=task["store_id"],
            store_name=task.get("store_name", ""),
            start_date=task["start_date"],
            end_date=task["end_date"],
            total_amount=task["total_amount"],
            daily_float_percent=task.get("daily_float_percent", 0.1),
            excluded_dates=task.get("excluded_dates", [])
        )
        
        return {
            "success": exec_result["success"],
            "task_id": task_id,
            "execution": exec_result,
            "message": exec_result["message"]
        }
    
    def execute_plan(
        self,
        store_id: int,
        store_name: str,
        start_date: str,
        end_date: str,
        total_amount: float,
        daily_float_percent: float = 0.1,
        excluded_dates: List[str] = []
    ) -> Dict:
        """执行耗用方案（逐日执行）
        
        Args:
            store_id: 门店ID
            store_name: 门店名称
            start_date: 开始日期
            end_date: 结束日期
            total_amount: 目标耗用金额
            daily_float_percent: 每日浮动百分比
            excluded_dates: 排除的日期列表
        
        Returns:
            执行结果
        """
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        excluded_set = set(excluded_dates)
        
        # 生成所有日期列表
        all_dates = []
        current = start
        while current <= end:
            all_dates.append(current)
            current += timedelta(days=1)
        
        if not all_dates:
            return {"success": False, "message": "日期范围无效"}
        
        # 计算有效日期
        effective_dates = [d for d in all_dates if d.strftime("%Y-%m-%d") not in excluded_set]
        effective_days = len(effective_dates)
        
        if effective_days <= 0:
            return {"success": False, "message": "所有日期都被排除"}
        
        # 计算每日基础金额
        base_daily_amount = total_amount / effective_days
        
        execution_results = []
        total_success = 0
        total_failed = 0
        total_records = 0
        accumulated_amount = 0.0
        
        for i, date in enumerate(all_dates):
            date_str = date.strftime("%Y-%m-%d")
            is_excluded = date_str in excluded_set
            
            if is_excluded:
                execution_results.append({
                    "date": date_str,
                    "status": "skipped",
                    "message": "已排除"
                })
                continue
            
            # 判断是否最后一个有效日期
            remaining_effective = [d for d in all_dates[i:] if d.strftime("%Y-%m-%d") not in excluded_set]
            is_last_effective_day = len(remaining_effective) == 1
            
            # 计算当日目标金额
            if is_last_effective_day:
                # 最后一天：精确补差
                target_amount = round(total_amount - accumulated_amount, 2)
            else:
                # 带浮动
                float_factor = 1 + random.uniform(-daily_float_percent, daily_float_percent)
                target_amount = base_daily_amount * float_factor
            
            # 执行单日耗用
            day_result = self._execute_single_day(
                store_id=store_id,
                store_name=store_name,
                date_str=date_str,
                target_amount=target_amount,
                is_last_day=is_last_effective_day,
                accumulated_amount=accumulated_amount,
                total_amount=total_amount
            )
            
            execution_results.append(day_result)
            total_success += day_result.get("success_count", 0)
            total_failed += day_result.get("failed_count", 0)
            total_records += day_result.get("record_count", 0)
            accumulated_amount += day_result.get("actual_amount", 0)
        
        return {
            "success": total_failed == 0,
            "total_success": total_success,
            "total_failed": total_failed,
            "total_records": total_records,
            "execution_results": execution_results,
            "message": f"执行完成：成功 {total_success} 条，失败 {total_failed} 条"
        }
    
    def _execute_single_day(
        self,
        store_id: int,
        store_name: str,
        date_str: str,
        target_amount: float,
        is_last_day: bool,
        accumulated_amount: float,
        total_amount: float
    ) -> Dict:
        """执行单日耗用
        
        Args:
            store_id: 门店ID
            store_name: 门店名称
            date_str: 日期字符串
            target_amount: 目标耗用金额
            is_last_day: 是否最后一天
            accumulated_amount: 已累计耗用金额
            total_amount: 总目标金额
        
        Returns:
            单日执行结果
        """
        print(f"[ConsumeTask] 执行日期: {date_str}, 目标金额: {target_amount}, 是否最后一天: {is_last_day}")
        
        # 1. 获取截止当日的库存池
        stock_result = stock_flow_service.get_stock_at_date(store_id=store_id, date_str=date_str)
        
        if not stock_result.get("success"):
            return {
                "date": date_str,
                "status": "error",
                "message": f"获取库存失败: {stock_result.get('message')}",
                "success_count": 0,
                "failed_count": 0,
                "record_count": 0,
                "actual_amount": 0,
            }
        
        stocks = stock_result.get("stocks", [])
        
        # 过滤出有效库存（数量 > 0，单价 > 0）
        valid_stocks = [s for s in stocks if s.get("quantity", 0) > 0 and s.get("unit_price", 0) > 0]
        
        if not valid_stocks:
            return {
                "date": date_str,
                "status": "error",
                "message": "没有有效库存",
                "success_count": 0,
                "failed_count": 0,
                "record_count": 0,
                "actual_amount": 0,
            }
        
        # 2. 从库存池生成耗用 list
        consume_list = self._greedy_consume_from_stock(
            stocks=valid_stocks,
            target_amount=target_amount,
            exclude_small_amount=not is_last_day
        )
        
        if not consume_list:
            return {
                "date": date_str,
                "status": "error",
                "message": "无法生成耗用方案",
                "success_count": 0,
                "failed_count": 0,
                "record_count": 0,
                "actual_amount": 0,
            }
        
        # 3. 执行耗用
        # 生成随机时间（10:00 - 20:00）
        hour = random.randint(10, 19)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        execute_time = f"{date_str} {hour:02d}:{minute:02d}:{second:02d}"
        
        day_success = 0
        day_failed = 0
        actual_amount = 0.0
        
        for item in consume_list:
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
                actual_amount += item["amount"]
                
                # API 成功后立即写入本地数据库
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
                print(f"[DEBUG] API 失败: {result.get('message')}")
        
        return {
            "date": date_str,
            "target_amount": round(target_amount, 2),
            "consume_plan": consume_list,
            "success_count": day_success,
            "failed_count": day_failed,
            "record_count": day_success,
            "actual_amount": round(actual_amount, 2),
            "status": "success" if day_failed == 0 else "partial",
        }
    
    def _greedy_consume_from_stock(
        self,
        stocks: List[Dict],
        target_amount: float,
        exclude_small_amount: bool = True
    ) -> List[Dict]:
        """贪心算法从库存池选商品（均匀分布）
        
        策略：
        1. 按单价排序（贵 → 便宜）
        2. 每个商品最多消耗目标金额的一定比例（如30%）
        3. 这样贵的商品不会被一次性耗尽，留一些给后面的日期
        
        Args:
            stocks: 库存列表
            target_amount: 目标耗用金额
            exclude_small_amount: 是否剔除小金额商品
        
        Returns:
            耗用方案列表
        """
        # 按单价排序（贵 → 便宜）
        sorted_stocks = sorted(stocks, key=lambda x: x.get("unit_price", 0), reverse=True)
        
        # 如果需要剔除小金额商品，先过滤
        if exclude_small_amount:
            sorted_stocks = [s for s in sorted_stocks if s.get("product_id") not in SMALL_AMOUNT_PRODUCTS]
        
        if not sorted_stocks:
            return []
        
        consume_list = []
        remaining = target_amount
        total_consume = 0.0
        
        # 每个商品最多消耗目标金额的 30%
        max_ratio_per_product = 0.3
        
        for stock in sorted_stocks:
            if remaining <= 0.01:
                break
            
            quantity = stock.get("quantity", 0)
            unit_price = stock.get("unit_price", 0)
            product_id = stock.get("product_id")
            
            if quantity <= 0 or unit_price <= 0:
                continue
            
            # 计算该商品最多可消耗的金额（目标金额的 30%）
            max_amount_for_this = target_amount * max_ratio_per_product
            
            # 计算可消耗数量
            max_by_amount_limit = max_amount_for_this / unit_price
            max_by_remaining = remaining / unit_price
            max_consume = min(quantity, max_by_amount_limit, max_by_remaining)
            
            # 四舍五入到2位小数
            consume_quantity = round(max_consume, 2)
            
            if consume_quantity <= 0:
                continue
            
            consume_amount = round(consume_quantity * unit_price, 2)
            
            consume_list.append({
                "product_id": product_id,
                "product_name": stock.get("product_name", ""),
                "product_code": stock.get("product_code", ""),
                "category_name": stock.get("category_name", ""),
                "cang_sub_category_name": stock.get("cang_sub_category_name", ""),
                "spec_name": stock.get("spec_name", ""),
                "unit": stock.get("unit", ""),
                "quantity": consume_quantity,
                "unit_price": unit_price,
                "amount": consume_amount,
            })
            
            remaining -= consume_amount
            total_consume += consume_amount
        
        return consume_list


consume_task_service = ConsumeTaskService()