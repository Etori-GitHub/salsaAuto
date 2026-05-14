"""命令行界面"""

from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, FloatPrompt

from src.config import config
from src.auth.service import auth_service
from src.services.order import order_service
from src.services.member import member_service


console = Console()


def show_banner() -> None:
    console.clear()
    console.print("[bold red]salsaAuto v2.0[/bold red] - 餐饮管理系统自动化工具")
    console.print("重构版 | 模块化 | 可维护")
    console.print()


def show_stores() -> None:
    table = Table(title="门店列表")
    table.add_column("序号", style="cyan")
    table.add_column("ID", style="green")
    table.add_column("名称", style="yellow")
    
    stores = config.get_all_stores()
    for i, (store_id, store) in enumerate(stores.items(), 1):
        table.add_row(str(i), store_id, store["name"])
    
    console.print(table)


def show_dishes() -> None:
    table = Table(title="菜品列表")
    table.add_column("序号", style="cyan")
    table.add_column("ID", style="green")
    table.add_column("名称", style="yellow")
    table.add_column("价格", style="magenta")
    
    dishes = config.get_all_dishes()
    for i, (dish_id, dish) in enumerate(dishes.items(), 1):
        table.add_row(str(i), dish_id, dish["name"], f"Y{dish['price']}")
    
    console.print(table)


def select_store() -> int:
    show_stores()
    store_ids = list(config.get_all_stores().keys())
    
    choice = IntPrompt.ask("选择门店序号", default=1)
    if 1 <= choice <= len(store_ids):
        return int(store_ids[choice - 1])
    
    console.print("[red]无效选择[/red]")
    return 0


def select_dish() -> int:
    show_dishes()
    dish_ids = list(config.get_all_dishes().keys())
    
    choice = IntPrompt.ask("选择菜品序号", default=1)
    if 1 <= choice <= len(dish_ids):
        return int(dish_ids[choice - 1])
    
    console.print("[red]无效选择[/red]")
    return 0


def select_pay_type() -> str:
    console.print("1. 会员支付")
    console.print("2. 现金支付")
    
    choice = Prompt.ask("选择支付方式", choices=["1", "2"], default="1")
    return "memberPay" if choice == "1" else "cash"


def parse_datetime(input_str: str) -> Optional[datetime]:
    if not input_str:
        return None
    
    try:
        return datetime.strptime(input_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        console.print("[red]日期格式错误，使用当前时间[/red]")
        return None


def cmd_login() -> None:
    console.print("[cyan]正在登录...[/cyan]")
    
    if auth_service.load_token():
        console.print("[green]已加载保存的 Token[/green]")
        return
    
    if auth_service.login_with_captcha():
        console.print("[green]登录成功[/green]")
    else:
        console.print("[red]登录失败[/red]")


def cmd_sync_members() -> None:
    console.print("[cyan]正在从 API 同步会员余额...[/cyan]")
    member_service.sync_from_api()


def cmd_set_member_type() -> None:
    members = member_service.get_all_members()
    
    table = Table(title="会员列表")
    table.add_column("序号", style="cyan")
    table.add_column("ID", style="green")
    table.add_column("用户名", style="yellow")
    table.add_column("余额", style="magenta")
    table.add_column("类型", style="red")
    
    member_ids = list(members.keys())
    for i, member_id in enumerate(member_ids, 1):
        member = members[member_id]
        table.add_row(
            str(i),
            member_id,
            member.get("username", ""),
            f"Y{member.get('balance', 0)}",
            member.get("type", "None")
        )
    
    console.print(table)
    
    choice = IntPrompt.ask("选择会员序号", default=1)
    if 1 <= choice <= len(member_ids):
        member_id = member_ids[choice - 1]
        console.print("1. None (通用会员)")
        console.print("2. yizhiman (一纸满会员)")
        type_choice = Prompt.ask("选择类型", choices=["1", "2"], default="1")
        member_type = "None" if type_choice == "1" else "yizhiman"
        member_service.set_member_type(member_id, member_type)
    else:
        console.print("[red]无效选择[/red]")


def cmd_create_order() -> None:
    store_id = select_store()
    if store_id == 0:
        return
    
    dish_id = select_dish()
    if dish_id == 0:
        return
    
    quantity = IntPrompt.ask("数量", default=1)
    pay_type = select_pay_type()
    
    member_type = "yizhiman" if store_id == 32 else "None"
    
    order_service.create_order(store_id, dish_id, quantity, pay_type, member_type=member_type)


def cmd_batch_by_amount() -> None:
    store_id = select_store()
    if store_id == 0:
        return
    
    dish_id = select_dish()
    if dish_id == 0:
        return
    
    total_amount = FloatPrompt.ask("总金额")
    pay_type = select_pay_type()
    
    time_str = Prompt.ask("开始时间 (留空使用当前时间)", default="")
    start_time = parse_datetime(time_str)
    
    member_type = "yizhiman" if store_id == 32 else "None"
    
    console.print(f"[cyan]开始批量创建订单，目标金额: Y{total_amount}[/cyan]")
    order_service.batch_create_orders_by_amount(
        store_id, dish_id, total_amount, pay_type, start_time,
        member_type=member_type
    )


def cmd_batch_by_quantity() -> None:
    store_id = select_store()
    if store_id == 0:
        return
    
    dish_id = select_dish()
    if dish_id == 0:
        return
    
    total_quantity = IntPrompt.ask("总数量")
    pay_type = select_pay_type()
    
    time_str = Prompt.ask("开始时间 (留空使用当前时间)", default="")
    start_time = parse_datetime(time_str)
    
    member_type = "yizhiman" if store_id == 32 else "None"
    
    console.print(f"[cyan]开始批量创建订单，目标数量: {total_quantity}[/cyan]")
    order_service.batch_create_orders_by_quantity(
        store_id, dish_id, total_quantity, pay_type, start_time,
        member_type=member_type
    )


def cmd_yizhiman_batch() -> None:
    store_id = 32
    
    console.print(f"[cyan]一纸满门店 (ID: {store_id})[/cyan]")
    
    dish_id = select_dish()
    if dish_id == 0:
        return
    
    total_quantity = IntPrompt.ask("总数量")
    pay_type = "memberPay"
    
    time_str = Prompt.ask("开始时间 (留空使用当前时间)", default="")
    start_time = parse_datetime(time_str)
    
    console.print(f"[cyan]开始一纸满刷单，目标数量: {total_quantity}[/cyan]")
    order_service.batch_create_orders_by_quantity(
        store_id, dish_id, total_quantity, pay_type, start_time,
        member_type="yizhiman"
    )


def run_cli() -> None:
    show_banner()
    
    if auth_service.load_token():
        console.print("[green]OK 已加载 Token[/green]")
    else:
        console.print("[yellow]! 未找到 Token，请先登录[/yellow]")
    
    if member_service.reload():
        console.print(f"[green]OK 已加载会员信息 ({len(member_service.get_all_members())} 人)[/green]")
    else:
        console.print("[yellow]! 未找到会员信息，请先同步[/yellow]")
    
    console.print()
    
    while True:
        console.print("[bold]命令列表[/bold]")
        console.print("  0001 - 登录并获取 Token")
        console.print("  0002 - 同步会员余额 (API)")
        console.print("  0003 - 设置会员类型")
        console.print("  0010 - 创建单个订单")
        console.print("  0101 - 按金额批量创建订单")
        console.print("  0202 - 按数量批量创建订单")
        console.print("  0303 - 一纸满门店刷单")
        console.print("  exit - 退出")
        console.print()
        
        cmd = Prompt.ask("[bold cyan]请输入命令[/bold cyan]")
        
        if cmd == "0001":
            cmd_login()
        elif cmd == "0002":
            cmd_sync_members()
        elif cmd == "0003":
            cmd_set_member_type()
        elif cmd == "0010":
            cmd_create_order()
        elif cmd == "0101":
            cmd_batch_by_amount()
        elif cmd == "0202":
            cmd_batch_by_quantity()
        elif cmd == "0303":
            cmd_yizhiman_batch()
        elif cmd == "exit":
            console.print("[yellow]再见！[/yellow]")
            break
        else:
            console.print("[red]未知命令[/red]")
        
        console.print()