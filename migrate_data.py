"""迁移数据从 JSON 到数据库"""

import json
from pathlib import Path
from src.services.database import db

print("=== 迁移数据到数据库 ===")

# 1. 迁移会员数据
member_file = Path(__file__).parent / "config" / "member.json"
if member_file.exists():
    with open(member_file, "r", encoding="utf-8") as f:
        member_data = json.load(f)
    
    member_list = []
    for member_id, info in member_data.items():
        member_list.append({
            "id": int(member_id),
            "phone": info.get("phone", ""),
            "username": info.get("username", ""),
            "balance": info.get("balance", 0),
            "type": info.get("type", "None"),
        })
    
    count = db.sync_members(member_list)
    print(f"会员迁移完成: {count} 条")
else:
    print("会员文件不存在")

print("迁移完成!")
