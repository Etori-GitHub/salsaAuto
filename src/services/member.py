"""会员服务"""

import json
import random
from pathlib import Path
from typing import Optional

from src.api.client import api_client


class MemberService:
    """会员服务"""
    
    def __init__(self) -> None:
        self._member_file = Path(__file__).parent.parent.parent / "config" / "member.json"
        self._members: dict = {}
        self._load_members()
    
    def _load_members(self) -> bool:
        if not self._member_file.exists():
            print(f"会员文件不存在: {self._member_file}")
            return False
        try:
            with open(self._member_file, "r", encoding="utf-8") as f:
                self._members = json.load(f)
            print(f"已加载 {len(self._members)} 个会员")
            return True
        except (json.JSONDecodeError, KeyError) as e:
            print(f"会员文件解析失败: {e}")
            return False
    
    def _save_members(self) -> None:
        self._member_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._member_file, "w", encoding="utf-8") as f:
            json.dump(self._members, f, indent=4, ensure_ascii=False)
        print(f"会员信息已保存")
    
    def sync_from_api(self, page: int = 1, page_size: int = 100) -> dict:
        params = {
            "page": page, "pageSize": page_size,
            "storeCode": "", "storeName": "",
            "memberCode": "", "username": "", "phone": "",
        }
        response = api_client.get("members", params=params)
        
        if response.get("code") == 1:
            records = response.get("data", {}).get("records", [])
            updated = 0
            for record in records:
                member_id = str(record["id"])
                if member_id in self._members:
                    self._members[member_id]["balance"] = record.get("balance", 0)
                    self._members[member_id]["phone"] = record.get("phone", "")
                    self._members[member_id]["username"] = record.get("username", "")
                    updated += 1
                else:
                    self._members[member_id] = {
                        "phone": record.get("phone", ""),
                        "username": record.get("username", ""),
                        "balance": record.get("balance", 0),
                        "type": "None",
                    }
                    updated += 1
            self._save_members()
            print(f"同步完成: 更新 {updated} 个会员")
        return response
    
    def get_member(self, member_id: str) -> Optional[dict]:
        return self._members.get(member_id)
    
    def get_all_members(self) -> dict:
        return self._members
    
    def get_members_by_type(self, member_type: str) -> dict:
        if member_type == "" or member_type == "None":
            return {k: v for k, v in self._members.items() if v.get("type", "None") in ["None", ""]}
        return {k: v for k, v in self._members.items() if v.get("type", "") == member_type}
    
    def random_member(self, min_balance: float, member_type: str = "") -> Optional[str]:
        candidates = []
        for member_id, member_info in self._members.items():
            balance = member_info.get("balance", 0)
            m_type = member_info.get("type", "None")
            if balance < min_balance:
                continue
            if member_type == "" or member_type == "None":
                if m_type not in ["None", ""]:
                    continue
            else:
                if m_type != member_type:
                    continue
            candidates.append(member_id)
        
        if not candidates:
            type_name = "通用" if member_type in ["", "None"] else member_type
            print(f"没有可用的会员 (类型: {type_name}, 最小余额: {min_balance})")
            return None
        return random.choice(candidates)
    
    def update_balance(self, member_id: str, amount: float) -> bool:
        member = self._members.get(member_id)
        if not member:
            print(f"会员不存在: {member_id}")
            return False
        old_balance = member.get("balance", 0)
        new_balance = round(old_balance - amount, 2)
        member["balance"] = new_balance
        self._save_members()
        print(f"会员 {member_id} 支付 {amount}，余额: {old_balance} -> {new_balance}")
        return True
    
    def set_member_type(self, member_id: str, member_type: str) -> bool:
        member = self._members.get(member_id)
        if not member:
            print(f"会员不存在: {member_id}")
            return False
        member["type"] = member_type
        self._save_members()
        print(f"会员 {member_id} 类型已设置为: {member_type}")
        return True
    
    def reload(self) -> bool:
        return self._load_members()


member_service = MemberService()