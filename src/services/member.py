"""会员服务"""

import random
from typing import Optional, Dict, List

from src.api.client import api_client
from src.services.database import db


class MemberService:
    """会员服务（使用数据库）"""
    
    def sync_from_api(self, page: int = 1, page_size: int = 100) -> dict:
        """从 API 同步会员数据"""
        params = {
            "page": page, "pageSize": page_size,
            "storeCode": "", "storeName": "",
            "memberCode": "", "username": "", "phone": "",
        }
        response = api_client.get("members", params=params)
        
        if response.get("code") == 1:
            records = response.get("data", {}).get("records", [])
            # 转换为数据库格式
            member_list = []
            for record in records:
                member_list.append({
                    "id": record.get("id"),
                    "phone": record.get("phone", ""),
                    "username": record.get("username", ""),
                    "balance": record.get("balance", 0),
                    "type": record.get("type", "None"),
                })
            
            count = db.sync_members(member_list)
            print(f"同步完成: 更新 {count} 个会员")
        return response
    
    def get_member(self, member_id: int) -> Optional[dict]:
        """获取单个会员"""
        return db.get_member(member_id)
    
    def get_all_members(self) -> List[dict]:
        """获取所有会员"""
        return db.get_members()
    
    def get_members_by_type(self, member_type: str) -> List[dict]:
        """按类型获取会员"""
        all_members = db.get_members()
        if member_type == "" or member_type == "None":
            return [m for m in all_members if m.get("member_type", "None") in ["None", ""]]
        return [m for m in all_members if m.get("member_type", "") == member_type]
    
    def random_member(self, min_balance: float, member_type: str = "") -> Optional[int]:
        """随机选择一个余额足够的会员"""
        members = db.get_members()
        candidates = []
        
        for member in members:
            balance = member.get("balance", 0)
            m_type = member.get("member_type", "None")
            
            if balance < min_balance:
                continue
            
            if member_type == "" or member_type == "None":
                if m_type not in ["None", ""]:
                    continue
            else:
                if m_type != member_type:
                    continue
            
            candidates.append(member.get("id"))
        
        if not candidates:
            type_name = "通用" if member_type in ["", "None"] else member_type
            print(f"没有可用的会员 (类型: {type_name}, 最小余额: {min_balance})")
            return None
        
        return random.choice(candidates)
    
    def update_balance(self, member_id: int, amount: float) -> bool:
        """更新会员余额"""
        member = db.get_member(member_id)
        if not member:
            print(f"会员不存在: {member_id}")
            return False
        
        old_balance = member.get("balance", 0)
        new_balance = round(old_balance - amount, 2)
        
        if db.update_member_balance(member_id, new_balance):
            print(f"会员 {member_id} 支付 {amount}，余额: {old_balance} -> {new_balance}")
            return True
        return False
    
    def add_member(self, member_id: int, phone: str = "", username: str = "",
                    balance: float = 0, member_type: str = "None") -> bool:
        """添加新会员"""
        if db.add_member(member_id, phone, username, balance, member_type):
            print(f"添加会员成功: {member_id} - {username}")
            return True
        print(f"添加会员失败: ID {member_id} 已存在")
        return False
    
    def set_member_type(self, member_id: int, member_type: str) -> bool:
        """设置会员类型"""
        if db.update_member_type(member_id, member_type):
            print(f"会员 {member_id} 类型已设置为: {member_type}")
            return True
        return False
    
    def reload(self) -> bool:
        """重新加载（数据库不需要）"""
        return True


member_service = MemberService()
