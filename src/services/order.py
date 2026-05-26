"""订单服务"""

import random
from datetime import datetime, timedelta
from typing import Optional

from src.config import config
from src.api.client import api_client
from src.services.member import member_service
from src.services.database import db


class OrderService:
    """订单服务"""
    
    def create_order(
        self, store_id: int, dish_id: int, quantity: int,
        pay_type: str = "cash", order_time: Optional[datetime] = None,
        remark: str = "", member_type: str = ""
    ) -> dict:
        """创建单个订单"""
        if order_time is None:
            order_time = datetime.now()
        
        price = config.get_dish_price(str(dish_id))
        total_price = round(price * quantity, 2)
        store_name = config.get_store_name(str(store_id))
        dish_name = config.get_dish_name(str(dish_id))
        
        # 完整的订单数据模板
        order_data = {
            "source": "前台",
            "remark": "111",
            "storeId": int(store_id),
            "memberId": "",
            "discountPrice": total_price,
            "diningType": 0,
            "status": 1,
            "createTime": order_time.strftime("%Y-%m-%d %H:%M:%S"),
            "review": "默认好评",
            "rating": 0,
            "dishCount": int(quantity),
            "dishs": f"[{dish_id}]",
            "cashPay": 0,
            "onlinePay": 0,
            "onlinePayCode": "",
            "memberPay": 0,
            "iccardPay": 0,
            "iccardPayCode": "",
            "couponPay": 0,
            "couponPayCode": ""
        }
        
        member_id = None
        
        if pay_type == "cash":
            order_data["cashPay"] = total_price
        elif pay_type == "memberPay":
            member_id = member_service.random_member(total_price, member_type)
            if member_id:
                order_data["memberPay"] = total_price
                order_data["memberId"] = int(member_id)
            else:
                print("没有可用会员，改为现金支付")
                order_data["cashPay"] = total_price
                pay_type = "cash"
        
        print(f"订单数据: {order_data}")
        response = api_client.post("orders", data=order_data)
        print(f"API 响应: {response}")
        
        # 判断是否成功
        api_success = response.get("code") == 1
        
        # 记录到数据库
        db.add_order_record(
            order_date=order_time.strftime("%Y-%m-%d"),
            store_id=int(store_id),
            store_name=store_name,
            dish_id=int(dish_id),
            dish_name=dish_name,
            dish_price=price,
            quantity=quantity,
            total_amount=total_price,
            pay_type=pay_type,
            remark=remark,
            api_success=api_success,
            api_response=str(response)
        )
        
        if api_success:
            print(f"订单创建成功: {store_name}, {dish_name}, 数量 {quantity}, 金额 {total_price}")
            if pay_type == "memberPay" and member_id:
                member_service.update_balance(member_id, total_price)
        else:
            print(f"订单创建失败: {response.get('msg', '未知错误')}")
        
        return response
    
    def batch_create_orders_by_amount(
        self, store_id: int, dish_id: int, total_amount: float,
        pay_type: str = "cash", start_time: Optional[datetime] = None,
        member_type: str = ""
    ) -> int:
        """按金额批量刷单"""
        remaining = total_amount
        order_count = 0
        current_time = start_time or datetime.now()
        
        while remaining > 0:
            quantity = random.randint(1, 3)
            price = config.get_dish_price(str(dish_id))
            cost = round(price * quantity, 2)
            
            if cost > remaining:
                quantity = max(1, int(remaining / price))
                cost = round(price * quantity, 2)
            
            self.create_order(store_id, dish_id, quantity, pay_type, current_time, member_type=member_type)
            remaining -= cost
            order_count += 1
            current_time += timedelta(seconds=random.randint(4, 40))
        
        print(f"批量创建完成: 共 {order_count} 个订单, 总金额 {total_amount}")
        return order_count
    
    def batch_create_orders_by_quantity(
        self, store_id: int, dish_id: int, total_quantity: int,
        pay_type: str = "cash", start_time: Optional[datetime] = None,
        member_type: str = "", remark: str = ""
    ) -> int:
        """按数量批量刷单"""
        remaining = total_quantity
        order_count = 0
        current_time = start_time or datetime.now()
        
        while remaining > 0:
            quantity = min(random.randint(1, 6), remaining)
            self.create_order(store_id, dish_id, quantity, pay_type, current_time, remark=remark, member_type=member_type)
            remaining -= quantity
            order_count += 1
            current_time += timedelta(seconds=random.randint(4, 40))
        
        print(f"批量创建完成: 共 {order_count} 个订单, 总数量 {total_quantity}")
        return order_count
    
    def execute_task(self, task_data: dict, member_type: str = "", remark: str = "111") -> dict:
        """
        执行刷单任务
        
        Args:
            task_data: 任务 JSON 数据
            member_type: 会员类型（可选）
            remark: 订单备注（默认 "111")
        
        Returns:
            执行结果统计
        """
        store_id = int(task_data["store_id"])
        pay_type = task_data["pay_type"]
        days = task_data["days"]
        
        total_orders = 0
        total_quantity = 0
        failed_days = []
        
        for day in days:
            date_str = day["date"]
            dishes = day["dishes"]
            
            for dish in dishes:
                dish_id = int(dish["id"])
                quantity = dish["quantity"]
                
                # 获取商品的时间范围
                dish_config = config.get_dish(str(dish_id))
                time_range = dish_config.get("time_range", "00:00-23:59") if dish_config else "00:00-23:59"
                
                # 解析时间上界
                start_time_str = time_range.split("-")[0]
                hour, minute = map(int, start_time_str.split(":"))
                
                # 拼接日期和时间
                date_parts = list(map(int, date_str.split("-")))
                order_time = datetime(date_parts[0], date_parts[1], date_parts[2], hour, minute, 0)
                
                # 执行刷单
                try:
                    count = self.batch_create_orders_by_quantity(
                        store_id=store_id,
                        dish_id=dish_id,
                        total_quantity=quantity,
                        pay_type=pay_type,
                        start_time=order_time,
                        member_type=member_type,
                        remark=remark
                    )
                    total_orders += count
                    total_quantity += quantity
                except Exception as e:
                    print(f"执行失败: {date_str} - {dish.get('name', dish_id)} - {e}")
                    failed_days.append({"date": date_str, "dish": dish.get("name", dish_id), "error": str(e)})
        
        result = {
            "success": len(failed_days) == 0,
            "total_orders": total_orders,
            "total_quantity": total_quantity,
            "failed_days": failed_days
        }
        
        print(f"任务执行完成: 共 {total_orders} 个订单, {total_quantity} 件商品")
        if failed_days:
            print(f"失败记录: {failed_days}")
        
        return result


order_service = OrderService()
