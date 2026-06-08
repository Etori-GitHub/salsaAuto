"""Web UI 服务"""

import json
import subprocess
import re
import os
import zipfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from io import BytesIO

import requests

from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import SessionNotCreatedException

from src.config import config
from src.auth.service import auth_service
from src.api.client import api_client
from src.services.order import order_service
from src.services.member import member_service
from src.services.supply_adjust import supply_adjust_service
from src.services.order_query import order_query_service
from src.services.order_service import order_service_v2
from src.services.store_query import store_query_service
from src.services.supply_query import supply_query_service
from src.services.base_library import base_library_service
from src.services.monthly_order import monthly_order_service
from src.services.database import db


app = FastAPI(title="salsaAuto", description="餐饮管理系统自动化工具")

BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

jinja_env = Environment(loader=FileSystemLoader(BASE_DIR / "templates"))

# 今日刷单记录
today_orders: dict[str, float] = {}

# Chrome 版本信息
chrome_version: Optional[str] = None
chromedriver_version: Optional[str] = None
chromedriver_download_url: Optional[str] = None

# 验证码 ID 缓存
captcha_id_cache: Optional[str] = None

# 浏览器实例(保持打开)
login_driver = None

# 启动时加载 Token
auth_service.load_token()
# 同步 Token 到 api_client
token = auth_service.get_token()
if token:
    api_client.set_token(token)


def render_template(name: str, context: dict) -> str:
    template = jinja_env.get_template(name)
    return template.render(context)


# === Chrome 驱动检测 ===

def detect_chromedriver_version() -> Optional[str]:
    """通过扫描 chromedriver-win64 文件夹获取版本"""
    driver_dir = Path(__file__).parent.parent / "chromedriver-win64"

    if not driver_dir.exists():
        return None

    driver_exe = driver_dir / "chromedriver.exe"
    if not driver_exe.exists():
        return None

    try:
        result = subprocess.run(
            [str(driver_exe), "--version"],
            capture_output=True, text=True, timeout=5
        )
        match = re.search(r'ChromeDriver\s+([\d.]+)', result.stdout)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"检测 ChromeDriver 版本失败: {e}")

    return None


def detect_chrome_version() -> Optional[str]:
    """通过启动 Chrome 浏览器获取版本"""
    driver_dir = Path(__file__).parent.parent / "chromedriver-win64"
    driver_exe = driver_dir / "chromedriver.exe"

    if not driver_exe.exists():
        return None

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    try:
        driver = webdriver.Chrome(
            service=Service(str(driver_exe)),
            options=options
        )

        capabilities = driver.capabilities
        version = capabilities.get("browserVersion")
        driver.quit()
        return version

    except SessionNotCreatedException as e:
        error_msg = str(e)
        print(f"ChromeDriver 启动失败: {error_msg}")

        match = re.search(r'Current browser version is ([\d.]+)', error_msg)
        if match:
            return match.group(1)

    except Exception as e:
        print(f"检测 Chrome 版本失败: {e}")

    return None


def check_chromedriver_download_url(version: str) -> Optional[str]:
    """检查 ChromeDriver 下载链接是否可用"""
    url = f"https://storage.googleapis.com/chrome-for-testing-public/{version}/win64/chromedriver-win64.zip"

    try:
        resp = requests.head(url, timeout=10, allow_redirects=True)
        if resp.status_code == 200:
            return url
    except:
        pass

    return None


def download_and_update_chromedriver(download_url: str) -> tuple[bool, str]:
    """下载并更新 ChromeDriver"""
    driver_dir = Path(__file__).parent.parent / "chromedriver-win64"
    driver_backup = Path(__file__).parent.parent / "chromedriver-win64-backup"

    try:
        print(f"正在下载 ChromeDriver: {download_url}")
        response = requests.get(download_url, timeout=120)
        response.raise_for_status()

        # 备份旧驱动
        if driver_dir.exists():
            if driver_backup.exists():
                shutil.rmtree(driver_backup)
            shutil.move(str(driver_dir), str(driver_backup))
            print("已备份旧驱动")

        # 解压新驱动
        with zipfile.ZipFile(BytesIO(response.content)) as zf:
            zf.extractall(driver_dir.parent)
            print("解压完成")

        # 删除备份
        if driver_backup.exists():
            shutil.rmtree(driver_backup)

        return True, "ChromeDriver 更新成功"

    except Exception as e:
        # 恢复备份
        if driver_backup.exists():
            if driver_dir.exists():
                shutil.rmtree(driver_dir)
            shutil.move(str(driver_backup), str(driver_dir))
            print("已恢复旧驱动")

        return False, f"更新失败: {str(e)}"


def init_chrome_versions():
    """初始化 Chrome 版本信息"""
    global chrome_version, chromedriver_version, chromedriver_download_url

    print("检测 Chrome 版本信息...")

    chromedriver_version = detect_chromedriver_version()
    print(f"ChromeDriver 版本: {chromedriver_version or '未检测到'}")

    chrome_version = detect_chrome_version()
    print(f"Chrome 浏览器版本: {chrome_version or '未检测到'}")

    # 如果没有检测到 ChromeDriver,自动下载默认版本
    if not chromedriver_version:
        print("未检测到 ChromeDriver,尝试下载默认版本 148.0.7778.168...")
        default_version = "148.0.7778.168"
        default_url = f"https://storage.googleapis.com/chrome-for-testing-public/{default_version}/win64/chromedriver-win64.zip"

        success, message = download_and_update_chromedriver(default_url)
        if success:
            chromedriver_version = detect_chromedriver_version()
            print(f"ChromeDriver 已安装: {chromedriver_version}")
        else:
            print(f"ChromeDriver 自动安装失败: {message}")

    # 检查下载链接是否可用
    if chrome_version:
        chromedriver_download_url = check_chromedriver_download_url(chrome_version)
        if chromedriver_download_url:
            print(f"ChromeDriver 下载链接可用")
        else:
            print("ChromeDriver 下载链接不可用")


# === 页面路由 ===

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return render_template("index.html", {"request": request, "page": "index"})


@app.get("/stores", response_class=HTMLResponse)
async def stores_page(request: Request):
    return render_template("stores.html", {"request": request, "page": "stores"})


@app.get("/dishes", response_class=HTMLResponse)
async def dishes_page(request: Request):
    return render_template("dishes.html", {"request": request, "page": "dishes"})


@app.get("/members", response_class=HTMLResponse)
async def members_page(request: Request):
    return render_template("members.html", {"request": request, "page": "members"})


@app.get("/orders", response_class=HTMLResponse)
async def orders_page(request: Request):
    return render_template("orders.html", {"request": request, "page": "orders"})


@app.get("/calculator", response_class=HTMLResponse)
async def calculator_page(request: Request):
    return render_template("calculator.html", {"request": request, "page": "calculator"})


@app.get("/records", response_class=HTMLResponse)
async def records_page(request: Request):
    return render_template("records.html", {"request": request, "page": "records"})

@app.get("/moyu", response_class=HTMLResponse)
async def moyu_page(request: Request):
    return render_template("moyu.html", {"request": request, "page": "moyu"})

@app.get("/order-query", response_class=HTMLResponse)
async def order_query_page(request: Request):
    return render_template("order_query.html", {"request": request, "page": "order-query"})

@app.get("/orders-query", response_class=HTMLResponse)
async def orders_query_page(request: Request):
    return render_template("orders_query.html", {"request": request, "page": "orders-query"})

@app.get("/product-analysis", response_class=HTMLResponse)
async def product_analysis_page(request: Request):
    return render_template("product_analysis.html", {"request": request, "page": "product-analysis"})

@app.get("/category-analysis", response_class=HTMLResponse)
async def category_analysis_page(request: Request):
    return render_template("category_analysis.html", {"request": request, "page": "category-analysis"})

@app.get("/supply-query", response_class=HTMLResponse)
async def supply_query_page(request: Request):
    return render_template("supply_query.html", {"request": request, "page": "supply-query"})

@app.get("/goods", response_class=HTMLResponse)
async def goods_page(request: Request):
    return render_template("goods.html", {"request": request, "page": "goods"})

@app.get("/goods-sub-cate", response_class=HTMLResponse)
async def goods_sub_cate_page(request: Request):
    return render_template("goods_sub_cate.html", {"request": request, "page": "goods-sub-cate"})

@app.get("/cang-sub-cate", response_class=HTMLResponse)
async def cang_sub_cate_page(request: Request):
    return render_template("cang_sub_cate.html", {"request": request, "page": "cang-sub-cate"})

@app.get("/monthly-order", response_class=HTMLResponse)
async def monthly_order_page(request: Request):
    return render_template("monthly_order.html", {"request": request, "page": "monthly-order"})

@app.get("/supply-calculator", response_class=HTMLResponse)
async def supply_calculator_page(request: Request):
    return render_template("supply_calculator.html", {"request": request, "page": "supply-calculator"})

@app.get("/supply-adjust", response_class=HTMLResponse)
async def supply_adjust_page(request: Request):
    return render_template("supply_adjust.html", {"request": request, "page": "supply-adjust"})

@app.get("/suppliers", response_class=HTMLResponse)
async def suppliers_page(request: Request):
    return render_template("suppliers.html", {"request": request, "page": "suppliers"})

@app.get("/purchase-query", response_class=HTMLResponse)
async def purchase_query_page(request: Request):
    return render_template("purchase_query.html", {"request": request, "page": "purchase-query"})

@app.get("/purchase-task", response_class=HTMLResponse)
async def purchase_task_page(request: Request):
    return render_template("purchase_task.html", {"request": request, "page": "purchase-task"})

@app.get("/purchase-adjust", response_class=HTMLResponse)
async def purchase_adjust_page(request: Request):
    return render_template("purchase_adjust.html", {"request": request, "page": "purchase-adjust"})

@app.get("/purchase-time-fix", response_class=HTMLResponse)
async def purchase_time_fix_page(request: Request):
    return render_template("purchase_time_fix.html", {"request": request, "page": "purchase-time-fix"})


# === API 路由 ===

@app.get("/api/status")
async def get_status():
    """获取系统状态"""
    driver_match = False
    if chrome_version and chromedriver_version:
        chrome_major = chrome_version.split('.')[0]
        driver_major = chromedriver_version.split('.')[0]
        driver_match = chrome_major == driver_major

    token_info = auth_service.get_token_info()

    return {
        "token_loaded": auth_service.get_token() is not None,
        "token_updated_at": token_info.get("updated_at") if token_info else None,
        "chrome_version": chrome_version,
        "chromedriver_version": chromedriver_version,
        "driver_match": driver_match,
        "driver_download_available": chromedriver_download_url is not None,
        "member_count": len(member_service.get_all_members()),
        "today_orders": today_orders,
        "today_total": sum(today_orders.values()),
    }


@app.get("/api/stores")
async def get_stores():
    """获取门店列表,只返回可见门店"""
    all_stores = config.get_all_stores()
    # 过滤掉隐藏的门店
    visible_stores = {
        k: v for k, v in all_stores.items()
        if v.get("visible", True) != False
    }
    return {"stores": visible_stores}


@app.post("/api/stores/visibility")
async def update_store_visibility(request: Request):
    """更新门店显隐状态"""
    data = await request.json()
    store_id = data.get("store_id")
    visible = data.get("visible")

    if not store_id:
        return {"success": False, "message": "缺少门店ID"}

    stores = config._data.get("stores", {})
    if store_id not in stores:
        return {"success": False, "message": "门店不存在"}

    stores[store_id]["visible"] = visible
    config._save()

    return {"success": True, "message": f"已{'显示' if visible else '隐藏'}门店"}


@app.get("/api/dishes")
async def get_dishes():
    return {"dishes": config.get_all_dishes()}


@app.post("/api/dishes/add")
async def add_dish(
    dish_id: str = Form(...), name: str = Form(...),
    price: float = Form(...), time_range: str = Form(default="00:00-23:59")
):
    """添加商品"""
    dishes = config._data.get("dishes", {})
    if dish_id in dishes:
        return {"success": False, "message": "商品ID已存在"}
    dishes[dish_id] = {"name": name, "price": price, "time_range": time_range}
    config._save()
    return {"success": True, "message": "添加成功"}


@app.post("/api/dishes/{dish_id}/update")
async def update_dish(
    dish_id: str, name: str = Form(...),
    price: float = Form(...), time_range: str = Form(default="00:00-23:59")
):
    """更新商品"""
    dishes = config._data.get("dishes", {})
    if dish_id not in dishes:
        return {"success": False, "message": "商品不存在"}
    dishes[dish_id] = {"name": name, "price": price, "time_range": time_range}
    config._save()
    return {"success": True, "message": "更新成功"}


@app.post("/api/dishes/{dish_id}/delete")
async def delete_dish(dish_id: str):
    """删除商品"""
    dishes = config._data.get("dishes", {})
    if dish_id not in dishes:
        return {"success": False, "message": "商品不存在"}
    del dishes[dish_id]
    config._save()
    return {"success": True, "message": "删除成功"}


@app.get("/api/orders/records")
async def get_order_records(
    start_date: str = None, end_date: str = None, store_id: int = None, pay_type: str = None, limit: int = 100
):
    """查询刷单记录"""
    from src.services.database import db
    records = db.get_order_records(start_date, end_date, store_id, pay_type, limit)
    stats = db.get_statistics(start_date, end_date, store_id, pay_type)
    return {"records": records, "statistics": stats}


@app.get("/api/orders/statistics")
async def get_order_statistics(start_date: str = None, end_date: str = None, store_id: int = None, pay_type: str = None):
    """获取刷单统计"""
    from src.services.database import db
    return db.get_statistics(start_date, end_date, store_id, pay_type)


@app.get("/api/members")
async def get_members():
    members = member_service.get_all_members()
    # 转换为字典格式(以 id 为 key)
    members_dict = {str(m["id"]): {
        "phone": m.get("phone", ""),
        "username": m.get("username", ""),
        "balance": m.get("balance", 0),
        "type": m.get("member_type", "None")
    } for m in members}
    return {"members": members_dict, "count": len(members)}


@app.post("/api/members/sync")
async def sync_members():
    result = member_service.sync_from_api()
    return {"success": result.get("code") == 1, "message": result.get("msg", "同步完成")}


@app.post("/api/members/{member_id}/type")
async def set_member_type(member_id: str, type: str = Form(...)):
    success = member_service.set_member_type(member_id, type)
    return {"success": success}


@app.post("/api/members/add")
async def add_member(
    id: str = Form(...),
    phone: str = Form(default=""),
    username: str = Form(default=""),
    balance: float = Form(default=0),
    type: str = Form(default="None")
):
    try:
        member_id = int(id)
    except ValueError:
        return {"success": False, "message": "会员 ID 必须是数字"}

    success = member_service.add_member(member_id, phone, username, balance, type)
    if success:
        return {"success": True, "message": "添加成功"}
    else:
        return {"success": False, "message": "会员 ID 已存在"}


@app.delete("/api/members/{member_id}")
async def delete_member(member_id: int):
    success = member_service.delete_member(member_id)
    return {"success": success}


@app.post("/api/token/start")
async def start_login():
    """启动登录流程,获取验证码图片"""
    global captcha_id_cache, login_driver

    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        import time as time_module
        import requests

        driver_path = Path(__file__).parent.parent / "chromedriver-win64" / "chromedriver.exe"

        options = Options()
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")

        # 启用 performance 日志和网络追踪
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        login_driver = webdriver.Chrome(service=Service(str(driver_path)), options=options)
        login_driver.set_window_size(1266, 1380)
        login_driver.set_window_rect(x=1300, y=0, width=1266, height=1380)

        # 启用网络追踪
        login_driver.execute_cdp_cmd("Network.enable", {})

        homepage = config._data.get("homepage", config.api_base_url + "/admin.html")
        login_driver.get(homepage)

        time_module.sleep(10)

        logs = login_driver.get_log("performance")
        captcha_id = None
        captcha_request_id = None

        for log in logs:
            try:
                data = json.loads(log["message"])
                message = data["message"]
                if message["method"] == "Network.responseReceivedExtraInfo":
                    headers = message["params"].get("headers", {})
                    if "gif-captcha-id" in headers:
                        captcha_id = headers["gif-captcha-id"]
                        captcha_request_id = message["params"].get("requestId")
                        break
            except:
                continue

        if not captcha_id:
            login_driver.quit()
            login_driver = None
            return {"success": False, "message": "未获取到验证码 ID"}

        captcha_id_cache = captcha_id

        # 用 CDP 直接从网络响应获取验证码 GIF 数据
        import base64
        captcha_body = None

        if captcha_request_id:
            try:
                body_response = login_driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": captcha_request_id})
                if body_response.get("base64Encoded"):
                    captcha_body = base64.b64decode(body_response["body"])
                else:
                    captcha_body = body_response["body"].encode()
            except Exception as e:
                login_driver.quit()
                login_driver = None
                return {"success": False, "message": f"获取验证码数据失败: {str(e)}"}

        if not captcha_body:
            login_driver.quit()
            login_driver = None
            return {"success": False, "message": "未获取到验证码图片数据"}

        # 保存到本地
        captcha_dir = Path(__file__).parent / "static" / "captcha"
        captcha_dir.mkdir(parents=True, exist_ok=True)
        captcha_file = captcha_dir / f"{captcha_id}.gif"

        with open(captcha_file, "wb") as f:
            f.write(captcha_body)

        # 不关闭浏览器,保留给用户输入验证码
        return {
            "success": True,
            "captcha_id": captcha_id,
            "captcha_url": f"/static/captcha/{captcha_id}.gif"
        }

    except Exception as e:
        if login_driver:
            login_driver.quit()
            login_driver = None
        return {"success": False, "message": f"启动失败: {str(e)}"}


@app.post("/api/token/submit")
async def submit_captcha(code: str = Form(...)):
    """提交验证码登录"""
    global captcha_id_cache, login_driver

    if not captcha_id_cache:
        return {"success": False, "message": "请先获取验证码"}

    try:
        # 用 API 登录
        login_data = {
            "username": config.username,
            "password": config.password,
            "verificationCode": code,
            "captchaName": captcha_id_cache
        }

        print(f"登录请求: {login_data}")

        response = api_client.post("login", data=login_data)
        print(f"登录响应: {response}")

        if response.get("code") == 1 and response.get("msg") == "OK":
            token = response["data"]["token"]
            auth_service._token = token
            api_client.set_token(token)
            auth_service._save_token(token)
            captcha_id_cache = None
            if login_driver:
                login_driver.quit()
                login_driver = None
            return {"success": True, "message": "登录成功"}
        else:
            return {"success": False, "message": response.get("msg", "验证码错误")}

    except Exception as e:
        return {"success": False, "message": f"登录失败: {str(e)}"}


@app.post("/api/token/get")
async def get_token():
    """获取 Token(已废弃)"""
    return {"success": False, "message": "请使用新的登录流程"}


@app.post("/api/chromedriver/update")
async def update_chromedriver():
    """更新 ChromeDriver"""
    global chromedriver_version

    if not chromedriver_download_url:
        return {"success": False, "message": "下载链接不可用"}

    success, message = download_and_update_chromedriver(chromedriver_download_url)

    if success:
        chromedriver_version = detect_chromedriver_version()

    return {
        "success": success,
        "message": message,
        "new_version": chromedriver_version
    }


@app.post("/api/orders/create")
async def create_order(
    store_id: int = Form(...), dish_id: int = Form(...),
    quantity: int = Form(...), pay_type: str = Form(...),
    member_type: str = Form(default="")
):
    result = order_service.create_order(store_id, dish_id, quantity, pay_type, member_type=member_type)

    if result.get("code") == 1:
        store_name = config.get_store_name(str(store_id))
        price = config.get_dish_price(str(dish_id))
        amount = round(price * quantity, 2)

        if store_name in today_orders:
            today_orders[store_name] = round(today_orders[store_name] + amount, 2)
        else:
            today_orders[store_name] = amount

    return {"success": result.get("code") == 1, "message": result.get("msg", "创建成功")}


@app.post("/api/orders/batch/amount")
async def batch_by_amount(
    store_id: int = Form(...), dish_id: int = Form(...),
    total_amount: float = Form(...), pay_type: str = Form(...),
    member_type: str = Form(default="")
):
    count = order_service.batch_create_orders_by_amount(
        store_id, dish_id, total_amount, pay_type, member_type=member_type
    )

    store_name = config.get_store_name(str(store_id))
    if store_name in today_orders:
        today_orders[store_name] = round(today_orders[store_name] + total_amount, 2)
    else:
        today_orders[store_name] = total_amount

    return {"success": True, "order_count": count}


@app.post("/api/orders/batch/quantity")
async def batch_by_quantity(
    store_id: int = Form(...), dish_id: int = Form(...),
    total_quantity: int = Form(...), pay_type: str = Form(...),
    member_type: str = Form(default=""),
    order_time: str = Form(default=""),
    remark: str = Form(default="")
):
    from datetime import datetime

    start_time = None
    if order_time:
        try:
            start_time = datetime.strptime(order_time, "%Y-%m-%dT%H:%M")
        except:
            pass

    count = order_service.batch_create_orders_by_quantity(
        store_id, dish_id, total_quantity, pay_type,
        start_time=start_time, member_type=member_type, remark=remark
    )

    store_name = config.get_store_name(str(store_id))
    price = config.get_dish_price(str(dish_id))
    estimated_amount = round(price * total_quantity, 2)

    if store_name in today_orders:
        today_orders[store_name] = round(today_orders[store_name] + estimated_amount, 2)
    else:
        today_orders[store_name] = estimated_amount

    return {"success": True, "order_count": count}


# === 订单查询 API ===

@app.get("/api/orders/list")
async def api_orders_list(
    page: int = Query(default=1),
    page_size: int = Query(default=15),
    order_code: Optional[str] = Query(default=None),
    store_id: Optional[int] = Query(default=None),
    pay_channel: Optional[str] = Query(default=None)
):
    """查询订单列表"""
    result = order_service_v2.query_orders(
        page=page,
        page_size=page_size,
        order_code=order_code,
        store_id=store_id,
        pay_channel=pay_channel
    )
    return result


@app.get("/api/orders/pay-channels")
async def api_pay_channels():
    """获取支付渠道列表"""
    channels = order_service_v2.get_pay_channels()
    return {"channels": channels}


@app.get("/api/supply-tasks/list")
async def list_supply_tasks():
    """获取所有要货任务列表"""
    tasks = supply_adjust_service.get_task_list()
    return {"tasks": tasks}


@app.get("/api/supply-tasks/{task_id}")
async def get_supply_task(task_id: str):
    """获取要货任务详情"""
    task = supply_adjust_service.get_task_detail(task_id)
    if not task:
        return {"success": False, "message": "任务不存在"}
    return {"success": True, "task": task}


@app.post("/api/supply-tasks/{task_id}/execute")
async def execute_supply_task(task_id: str):
    """执行补要货任务"""
    result = supply_adjust_service.execute_task(task_id)
    return result


@app.post("/api/supply-tasks/save")
async def save_supply_task(request: Request):
    """保存要货任务到 JSON 文件"""
    try:
        task_data = await request.json()

        # 确保任务目录存在
        tasks_dir = Path(__file__).parent.parent / "data" / "supply-tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        task_id = task_data.get("task_id", f"supply_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        file_path = tasks_dir / f"{task_id}.json"

        # 保存 JSON 文件
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(task_data, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "message": "要货任务保存成功",
            "file_path": str(file_path),
            "task_id": task_id
        }

    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/api/supply-tasks/list")
async def list_supply_tasks():
    """获取所有要货任务列表"""
    tasks_dir = Path(__file__).parent.parent / "data" / "supply-tasks"

    if not tasks_dir.exists():
        return {"tasks": []}

    tasks = []
    for file in tasks_dir.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                tasks.append({
                    "task_id": data.get("task_id"),
                    "task_name": data.get("task_name"),
                    "store_name": data.get("store_name"),
                    "total_amount": data.get("total_amount"),
                    "date_range": data.get("date_range"),
                    "created_at": data.get("created_at"),
                    "file_path": str(file)
                })
        except:
            continue

    # 按创建时间倒序排列
    tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return {"tasks": tasks}


@app.post("/api/tasks/save")
async def save_task(request: Request):
    """保存刷单任务到 JSON 文件"""
    try:
        task_data = await request.json()

        # 确保任务目录存在
        tasks_dir = Path(__file__).parent.parent / "data" / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        task_id = task_data.get("task_id", f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        file_path = tasks_dir / f"{task_id}.json"

        # 保存 JSON 文件
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(task_data, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "message": "任务保存成功",
            "file_path": str(file_path),
            "task_id": task_id
        }

    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/api/tasks/list")
async def list_tasks():
    """获取所有任务列表"""
    tasks_dir = Path(__file__).parent.parent / "data" / "tasks"

    if not tasks_dir.exists():
        return {"tasks": []}

    tasks = []
    for file in tasks_dir.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                tasks.append({
                    "task_id": data.get("task_id"),
                    "task_name": data.get("task_name"),
                    "store_name": data.get("store_name"),
                    "pay_type_name": data.get("pay_type_name"),
                    "total_amount": data.get("total_amount"),
                    "date_range": data.get("date_range"),
                    "created_at": data.get("created_at"),
                    "file_path": str(file)
                })
        except:
            continue

    # 按创建时间倒序排列
    tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return {"tasks": tasks}


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """获取单个任务详情"""
    tasks_dir = Path(__file__).parent.parent / "data" / "tasks"
    file_path = tasks_dir / f"{task_id}.json"

    if not file_path.exists():
        return {"success": False, "message": "任务不存在"}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"success": True, "task": data}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/tasks/{task_id}/execute")
async def execute_task(task_id: str, member_type: str = Form(default=""), remark: str = Form(default="111")):
    """执行刷单任务"""
    tasks_dir = Path(__file__).parent.parent / "data" / "tasks"
    file_path = tasks_dir / f"{task_id}.json"

    if not file_path.exists():
        return {"success": False, "message": "任务不存在"}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            task_data = json.load(f)

        result = order_service.execute_task(task_data, member_type=member_type, remark=remark)

        # 更新今日刷单统计
        store_name = task_data.get("store_name", "")
        total_amount = task_data.get("total_amount", 0)
        if store_name and total_amount:
            if store_name in today_orders:
                today_orders[store_name] = round(today_orders[store_name] + total_amount, 2)
            else:
                today_orders[store_name] = total_amount

        return {
            "success": result["success"],
            "message": f"任务执行完成,共 {result['total_orders']} 个订单",
            "result": result
        }

    except Exception as e:
        return {"success": False, "message": str(e)}


def run_server(host: str = "127.0.0.1", port: int = 8080):
    import uvicorn
    import webbrowser
    import threading
    import time
    import subprocess
    import signal
    import sys

    init_chrome_versions()

    # 加载 Token
    auth_service.load_token()

    url = f"http://{host}:{port}"
    chrome_process = None

    def open_browser():
        nonlocal chrome_process
        time.sleep(1)
        # 使用 Chrome 打开
        chrome_paths = [
            "chrome",
            "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        ]
        for path in chrome_paths:
            try:
                if Path(path).exists() if not path == "chrome" else True:
                    chrome_process = subprocess.Popen(
                        [path, url],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    return
            except FileNotFoundError:
                continue
        # 找不到 Chrome,用默认浏览器
        webbrowser.open(url)

    def close_browser(signum=None, frame=None):
        """关闭浏览器"""
        if chrome_process:
            try:
                chrome_process.terminate()
            except:
                pass
        sys.exit(0)

    # 注册信号处理
    signal.signal(signal.SIGINT, close_browser)
    signal.signal(signal.SIGTERM, close_browser)

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host=host, port=port, log_config=None)


# ==================== 订单查询 API ====================

@app.get("/api/orders/query")
async def query_orders(
    store_id: Optional[int] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    order_code: Optional[str] = None,
    dish_name: Optional[str] = None,
    page: int = 1,
    page_size: int = 100
):
    """查询平台订单(从 API 实时获取)"""
    result = order_query_service.query_orders(
        store_id=store_id,
        start_time=start_time,
        end_time=end_time,
        order_code=order_code,
        dish_name=dish_name,
        page=page,
        page_size=page_size
    )
    return result


@app.get("/api/orders/query-all")
async def query_all_orders(
    store_id: Optional[int] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None
):
    """查询所有订单(分页拉取)"""
    result = order_query_service.query_all_orders(
        store_id=store_id,
        start_time=start_time,
        end_time=end_time
    )
    return result


@app.get("/api/orders/export")
async def export_orders(
    store_id: Optional[int] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    order_code: Optional[str] = None,
    dish_name: Optional[str] = None
):
    """导出订单数据为 Excel"""
    from fastapi.responses import StreamingResponse
    from io import BytesIO
    import pandas as pd
    from urllib.parse import quote

    # 查询所有订单
    result = order_query_service.query_all_orders(
        store_id=store_id,
        start_time=start_time,
        end_time=end_time
    )

    if not result["success"] or not result["records"]:
        return {"success": False, "message": "暂无数据可导出"}

    records = result["records"]

    # 准备数据
    data = []
    for r in records:
        data.append({
            "订单号": r.get("orderCode", ""),
            "菜品名称": r.get("dishName", ""),
            "分类": r.get("dish", {}).get("categoryName", ""),
            "门店": r.get("storeName", ""),
            "数量": r.get("count", 0),
            "金额": r.get("discountPrice", 0),
            "创建时间": r.get("createTime", ""),
            "状态": "已退款" if r.get("refund") else "正常"
        })

    df = pd.DataFrame(data)

    # 导出 Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='订单数据', index=False)
    output.seek(0)

    # 生成文件名
    store_name = "全部门店" if not store_id else config.get_store_name(str(store_id))
    time_range = f"{start_time[:10] if start_time else ''}_{end_time[:10] if end_time else ''}"
    filename = f"订单数据_{store_name}_{time_range}.xlsx"
    encoded_filename = quote(filename)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )


# ==================== 门店管理 API ====================

@app.get("/api/stores/query")
async def query_stores_from_api():
    """从 API 查询门店列表"""
    result = store_query_service.query_all_stores()
    return result


@app.post("/api/stores/update")
async def update_stores_config():
    """更新本地门店配置"""
    result = store_query_service.update_config()
    return result


# ==================== 要货查询 API ====================

@app.get("/api/supply/query")
async def query_supply_orders(
    store_code: Optional[str] = None,
    cang_sub_category_name: Optional[str] = None,
    category_name: Optional[str] = None,
    product_name: Optional[str] = None,
    delivery_code: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    page: int = 1,
    page_size: int = 100
):
    """查询要货记录"""
    result = supply_query_service.query_supply_orders(
        store_code=store_code,
        cang_sub_category_name=cang_sub_category_name,
        category_name=category_name,
        product_name=product_name,
        delivery_code=delivery_code,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size
    )
    return result


@app.get("/api/supply/query-all")
async def query_all_supply_orders(
    store_code: Optional[str] = None,
    cang_sub_category_name: Optional[str] = None,
    category_name: Optional[str] = None,
    product_name: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None
):
    """查询所有要货记录"""
    result = supply_query_service.query_all_supply_orders(
        store_code=store_code,
        cang_sub_category_name=cang_sub_category_name,
        category_name=category_name,
        product_name=product_name,
        start_time=start_time,
        end_time=end_time
    )
    return result


@app.post("/api/supply/update-can-show")
async def update_supply_can_show(id: int, value: int):
    """更新要货明细的 canShow 字段"""
    try:
        # 调用平台 API 更新
        url = f"{config.api_base_url}/restful/shasha/supply/sordersDetail/updateField"
        params = {
            "field": "can_show",
            "value": value,
            "id": id
        }

        response = api_client.session.post(url, params=params, timeout=10, verify=False)
        result = response.json()

        if result.get("code") == 1:
            return {"success": True, "message": "更新成功"}
        else:
            return {"success": False, "message": result.get("msg", "更新失败")}

    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/api/supply/export")
async def export_supply_orders(
    store_code: Optional[str] = None,
    cang_sub_category_name: Optional[str] = None,
    category_name: Optional[str] = None,
    product_name: Optional[str] = None,
    delivery_code: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None
):
    """导出要货记录为 Excel"""
    from fastapi.responses import StreamingResponse
    from io import BytesIO
    import pandas as pd
    from urllib.parse import quote

    result = supply_query_service.query_all_supply_orders(
        store_code=store_code,
        cang_sub_category_name=cang_sub_category_name,
        category_name=category_name,
        product_name=product_name,
        start_time=start_time,
        end_time=end_time
    )

    if not result["success"] or not result["records"]:
        return {"success": False, "message": "暂无数据可导出"}

    records = result["records"]

    data = []
    for r in records:
        data.append({
            "配送单号": r.get("deliveryCode", ""),
            "门店": r.get("storeName", ""),
            "商品名称": r.get("productName", ""),
            "分类": r.get("productCategoryName", ""),
            "子分类": r.get("productSubcategoryName", ""),
            "订货数量": r.get("orderQuantity", 0),
            "单位": r.get("unit", ""),
            "已配送": r.get("deliveredQuantity", 0),
            "单价": r.get("truePrice") or r.get("unitPrice", 0),
            "总价": r.get("totalPriceD", 0),
            "创建时间": r.get("createTime", ""),
            "显示": "是" if r.get("canShow") == 1 else "否",
            "状态": "已收货" if r.get("receiveStatus") else ("配送中" if r.get("deliveredQuantity") else "待配送")
        })

    df = pd.DataFrame(data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='要货记录', index=False)
    output.seek(0)

    filename = f"要货记录_{store_code or '全部'}_{category_name or '全部'}.xlsx"
    encoded_filename = quote(filename)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )


# ==================== 基础库 API ====================

@app.get("/api/base/goods")
async def query_goods(page: int = 1, page_size: int = 100):
    """查询商品库"""
    result = base_library_service.query_goods(page=page, page_size=page_size)
    return result


@app.get("/api/base/goods/all")
async def query_all_goods():
    """查询所有商品"""
    result = base_library_service.query_all_goods()
    return result


@app.post("/api/base/goods/update")
async def update_goods_config():
    """更新本地商品配置"""
    result = base_library_service.update_goods_config()
    return result


@app.get("/api/base/cang-sub-cate")
async def query_cang_sub_cate():
    """查询档口分类"""
    result = base_library_service.query_all_product_sub_cate()
    return result


@app.post("/api/base/cang-sub-cate/update")
async def update_cang_sub_cate_config():
    """更新本地档口分类配置"""
    result = base_library_service.update_cang_sub_cate_config()
    return result


@app.get("/api/base/goods-sub-cate")
async def query_goods_sub_cate():
    """查询商品分类"""
    result = base_library_service.query_all_goods_sub_cate()
    return result


@app.post("/api/base/goods-sub-cate/update")
async def update_goods_sub_cate_config():
    """更新本地商品分类配置"""
    result = base_library_service.update_goods_sub_cate_config()
    return result


@app.get("/api/base/goods/local")
async def get_local_goods(search: str = None, category: str = None):
    """从数据库查询商品库"""
    from src.services.database import db
    records = db.get_goods(search=search, category=category)
    return {"success": True, "records": records, "total": len(records)}


@app.get("/api/base/goods-sub-cate/local")
async def get_local_goods_sub_cate():
    """从数据库查询商品分类"""
    from src.services.database import db
    records = db.get_goods_sub_cate()
    return {"success": True, "records": records, "total": len(records)}


@app.get("/api/base/cang-sub-cate/local")
async def get_local_cang_sub_cate():
    """从数据库查询档口分类"""
    from src.services.database import db
    records = db.get_cang_sub_cate()
    return {"success": True, "records": records, "total": len(records)}


@app.post("/api/base/goods-sub-cate/{cate_id}/type")
async def update_goods_sub_cate_type(cate_id: int, cate_type: str = Form(...)):
    """更新商品分类类型"""
    from src.services.database import db
    if cate_type not in ["食品", "非食品", "饮料", ""]:
        return {"success": False, "message": "类型必须是食品、非食品或饮料"}
    success = db.update_goods_sub_cate_type(cate_id, cate_type)
    if not success:
        # 检查记录是否存在
        records = db.get_goods_sub_cate()
        if not any(r.get('id') == cate_id for r in records):
            return {"success": False, "message": "记录不存在,请先同步数据"}
    return {"success": success, "message": "更新成功" if success else "更新失败"}


@app.post("/api/base/goods-sub-cate/{cate_id}/ratio")
async def update_goods_sub_cate_ratio(cate_id: int, ratio: float = Form(...)):
    """更新商品分类配销比例"""
    from src.services.database import db
    success = db.update_goods_sub_cate_ratio(cate_id, ratio)
    if not success:
        records = db.get_goods_sub_cate()
        if not any(r.get('id') == cate_id for r in records):
            return {"success": False, "message": "记录不存在,请先同步数据"}
    return {"success": success, "message": "更新成功" if success else "更新失败"}


@app.post("/api/base/goods/update-distribution-price")
async def update_goods_distribution_price():
    """重新计算所有商品的配销价格"""
    from src.services.database import db
    from src.services.base_library import base_library_service
    
    # 获取所有商品
    result = base_library_service.query_all_goods()
    if not result["success"]:
        return result
    
    # 同步商品（会自动计算配销价格）
    count = db.sync_goods(result["records"])
    return {"success": True, "message": f"已更新 {count} 条商品的配销价格"}


# ==================== 月订货统计 API ====================

@app.get("/api/monthly-order/stats")
async def get_monthly_order_stats(
    store_ids: List[str] = Query([]),
    start_time: str = None,
    end_time: str = None
):
    """月订货统计"""
    if not store_ids:
        return {"success": False, "message": "请选择门店"}
    if not start_time or not end_time:
        return {"success": False, "message": "请选择时间区间"}

    result = monthly_order_service.calculate_statistics(
        store_ids=store_ids,
        start_time=start_time,
        end_time=end_time
    )
    return result


@app.post("/api/monthly-order/export")
async def export_monthly_order(request: Request):
    """导出月订货统计"""
    from fastapi.responses import StreamingResponse
    import pandas as pd
    from urllib.parse import quote

    data = await request.json()

    if not data.get("store_stats"):
        return {"success": False, "message": "没有数据可导出"}

    # 生成 Excel
    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine='openpyxl') as wb:
        # 门店统计表
        store_df = pd.DataFrame(data["store_stats"])
        # 重命名列
        store_df = store_df.rename(columns={
            'store_name': '门店名称',
            'food': '食品',
            'non_food': '非食品',
            'drink': '饮料'
        })

        # 选择需要的列
        export_columns = ['门店名称'] + data['cang_names'] + ['食品', '非食品', '饮料']
        store_df_export = store_df[[c for c in export_columns if c in store_df.columns]]
        store_df_export.to_excel(wb, sheet_name='门店统计', index=False)

    buffer.seek(0)

    filename = f"月订货统计_{data.get('start_time', '')}_{data.get('end_time', '')}.xlsx"
    encoded_filename = quote(filename)

    return StreamingResponse(
        buffer,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
    )


# ==================== 数据分析 API ==================

@app.get("/api/analysis/products")
async def analyze_products(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    store_id: Optional[int] = None
):
    """菜品分析 - 汇总单品数据"""
    if not start_time or not end_time:
        return {"success": False, "message": "请选择时间范围", "products": []}

    # 查询所有订单
    result = order_query_service.query_all_orders(
        store_id=store_id,
        start_time=start_time,
        end_time=end_time
    )

    if not result["success"]:
        return {"success": False, "message": result["message"], "products": []}

    records = result["records"]

    if not records:
        return {"success": True, "message": "暂无数据", "products": [], "stats": {}}

    # 汇总商品数据
    products = {}
    total_sales = 0
    total_quantity = 0
    total_refund_quantity = 0
    total_refund_sales = 0
    order_codes = set()

    for record in records:
        dish_id = record.get("dishId")
        if not dish_id:
            continue

        order_codes.add(record.get("orderCode"))

        dish_name = record.get("dishName", "")
        dish_info = record.get("dish") or {}
        category = dish_info.get("categoryName", "")
        quantity = record.get("count", 0)
        refund_count = record.get("refundCount", 0)
        price = record.get("discountPrice", 0)
        # 实际销量 = 下单数量 - 退单数量
        actual_quantity = quantity - refund_count
        # 实际销售额 = 实际销量 * 单价
        actual_sales = actual_quantity * price
        is_refund = record.get("refund", 0)

        if dish_id not in products:
            products[dish_id] = {
                "id": dish_id,
                "name": dish_name,
                "category": category,
                "quantity": 0,
                "price": price,
                "total_sales": 0,
                "refund_quantity": 0,
                "refund_sales": 0
            }

        if is_refund:
            # 退款统计
            products[dish_id]["refund_quantity"] += quantity
            products[dish_id]["refund_sales"] += quantity * price
            total_refund_quantity += quantity
            total_refund_sales += quantity * price
        else:
            # 正常销售统计
            products[dish_id]["quantity"] += actual_quantity
            products[dish_id]["total_sales"] += actual_sales
            total_sales += actual_sales
            total_quantity += actual_quantity


        # 更新单价(取最新)
        if price > 0:
            products[dish_id]["price"] = price

    # 转为列表并排序
    product_list = list(products.values())
    product_list.sort(key=lambda x: x["total_sales"], reverse=True)

    # 计算占比
    for p in product_list:
        p["percentage"] = (p["total_sales"] / total_sales * 100) if total_sales > 0 else 0

    return {
        "success": True,
        "products": product_list,
        "stats": {
            "total_sales": total_sales,
            "total_quantity": total_quantity,
            "total_refund_quantity": total_refund_quantity,
            "total_refund_sales": total_refund_sales,
            "order_count": len(order_codes)
        }
    }


@app.get("/api/analysis/categories")
async def analyze_categories(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    store_id: Optional[int] = None
):
    """分类分析 - 按分类汇总数据"""
    if not start_time or not end_time:
        return {"success": False, "message": "请选择时间范围", "categories": []}

    # 查询所有订单
    result = order_query_service.query_all_orders(
        store_id=store_id,
        start_time=start_time,
        end_time=end_time
    )

    if not result["success"]:
        return {"success": False, "message": result["message"], "categories": []}

    records = result["records"]

    if not records:
        return {"success": True, "message": "暂无数据", "categories": [], "stats": {}}

    # 按分类汇总
    categories = {}
    total_sales = 0
    total_quantity = 0
    total_refund_quantity = 0
    total_refund_sales = 0
    order_codes = set()

    for record in records:
        dish_id = record.get("dishId")
        if not dish_id:
            continue

        order_codes.add(record.get("orderCode"))

        dish_info = record.get("dish") or {}
        category_name = dish_info.get("categoryName", "未分类")
        category_code = dish_info.get("categoryCode", "")
        quantity = record.get("count", 0)
        refund_count = record.get("refundCount", 0)
        price = record.get("discountPrice", 0)
        actual_quantity = quantity - refund_count
        actual_sales = actual_quantity * price
        is_refund = record.get("refund", 0)

        # 用 category_code 作为 key,没有则用 category_name
        cat_key = category_code if category_code else category_name

        if cat_key not in categories:
            categories[cat_key] = {
                "code": category_code,
                "name": category_name,
                "dish_count": 0,
                "dishes": set(),
                "quantity": 0,
                "total_sales": 0,
                "refund_quantity": 0,
                "refund_sales": 0
            }

        categories[cat_key]["dishes"].add(dish_id)

        if is_refund:
            categories[cat_key]["refund_quantity"] += quantity
            categories[cat_key]["refund_sales"] += quantity * price
            total_refund_quantity += quantity
            total_refund_sales += quantity * price
        else:
            categories[cat_key]["quantity"] += actual_quantity
            categories[cat_key]["total_sales"] += actual_sales
            total_sales += actual_sales
            total_quantity += actual_quantity

    # 转为列表并处理
    category_list = []
    for cat in categories.values():
        cat["dish_count"] = len(cat["dishes"])
        del cat["dishes"]  # 移除临时字段
        del cat["code"]
        category_list.append(cat)

    # 排序
    category_list.sort(key=lambda x: x["total_sales"], reverse=True)

    # 计算占比
    for c in category_list:
        c["percentage"] = (c["total_sales"] / total_sales * 100) if total_sales > 0 else 0

    return {
        "success": True,
        "categories": category_list,
        "stats": {
            "total_sales": total_sales,
            "total_quantity": total_quantity,
            "total_refund_quantity": total_refund_quantity,
            "total_refund_sales": total_refund_sales,
            "order_count": len(order_codes)
        }
    }


@app.get("/api/analysis/categories/export")
async def export_categories_excel(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    store_id: Optional[int] = None
):
    """导出分类分析结果为 Excel"""
    from fastapi.responses import StreamingResponse
    from io import BytesIO
    import pandas as pd
    from urllib.parse import quote

    # 获取分析数据
    result = await analyze_categories(start_time, end_time, store_id)

    if not result["success"] or not result["categories"]:
        return {"success": False, "message": "暂无数据可导出"}

    categories = result["categories"]
    stats = result["stats"]

    # 准备数据
    data = []
    for i, c in enumerate(categories, 1):
        data.append({
            "排名": i,
            "分类名称": c["name"],
            "商品数": c.get("dish_count", 0),
            "销量": c["quantity"],
            "退款数量": c.get("refund_quantity", 0),
            "总销售额": c["total_sales"],
            "退款金额": c.get("refund_sales", 0),
            "占比(%)": round(c.get("percentage", 0), 2)
        })

    df = pd.DataFrame(data)

    # 导出 Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='分类分析', index=False)

        # 添加汇总行
        summary_df = pd.DataFrame([{
            "排名": "",
            "分类名称": "合计",
            "商品数": "",
            "销量": stats["total_quantity"],
            "退款数量": stats["total_refund_quantity"],
            "总销售额": stats["total_sales"],
            "退款金额": stats["total_refund_sales"],
            "占比(%)": 100
        }])
        summary_df.to_excel(writer, sheet_name='分类分析', startrow=len(df) + 2, index=False)

    output.seek(0)

    # 生成文件名
    store_name = "全部门店" if not store_id else config.get_store_name(str(store_id))
    filename = f"分类分析_{store_name}_{start_time[:10]}_{end_time[:10]}.xlsx"
    encoded_filename = quote(filename)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )


@app.get("/api/analysis/products/export")
async def export_products_excel(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    store_id: Optional[int] = None
):
    """导出菜品分析结果为 Excel"""
    from fastapi.responses import StreamingResponse
    from io import BytesIO
    import pandas as pd

    # 获取分析数据
    result = await analyze_products(start_time, end_time, store_id)

    if not result["success"] or not result["products"]:
        return {"success": False, "message": "暂无数据可导出"}

    products = result["products"]
    stats = result["stats"]

    # 准备数据
    data = []
    for i, p in enumerate(products, 1):
        data.append({
            "排名": i,
            "商品名称": p["name"],
            "分类": p.get("category", ""),
            "销量": p["quantity"],
            "退款数量": p.get("refund_quantity", 0),
            "单价": p.get("price", 0),
            "总销售额": p["total_sales"],
            "退款金额": p.get("refund_sales", 0),
            "占比(%)": round(p.get("percentage", 0), 2)
        })

    df = pd.DataFrame(data)

    # 导出到 Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='菜品分析', index=False)

        # 添加汇总行
        summary_df = pd.DataFrame([{
            "排名": "",
            "商品名称": "合计",
            "分类": "",
            "销量": stats["total_quantity"],
            "退款数量": stats["total_refund_quantity"],
            "单价": "",
            "总销售额": stats["total_sales"],
            "退款金额": stats["total_refund_sales"],
            "占比(%)": 100
        }])
        summary_df.to_excel(writer, sheet_name='菜品分析', startrow=len(df) + 2, index=False)

    output.seek(0)

    # 生成文件名
    store_name = "全部门店" if not store_id else config.get_store_name(str(store_id))
    filename = f"菜品分析_{store_name}_{start_time[:10]}_{end_time[:10]}.xlsx"

    from urllib.parse import quote
    encoded_filename = quote(filename)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )


# ==================== 供应商管理 API ====================

@app.get("/api/base/suppliers")
async def query_suppliers(page: int = 1, page_size: int = 100):
    """查询供应商"""
    result = base_library_service.query_suppliers(page=page, page_size=page_size)
    return result

@app.get("/api/base/suppliers/all")
async def query_all_suppliers():
    """查询所有供应商"""
    result = base_library_service.query_all_suppliers()
    return result

@app.post("/api/base/suppliers/update")
async def update_suppliers_config():
    """更新本地供应商配置"""
    result = base_library_service.update_suppliers_config()
    return result

@app.get("/api/base/suppliers/local")
async def get_local_suppliers(search: str = None):
    """从数据库查询供应商"""
    from src.services.database import db
    records = db.get_suppliers(search=search)
    return {"success": True, "records": records, "total": len(records)}

@app.post("/api/base/suppliers/{supplier_id}/entity")
async def update_supplier_entity(supplier_id: int, entity_name: str = Form(...)):
    """更新供应商汇总主体"""
    from src.services.database import db
    success = db.update_supplier_entity(supplier_id, entity_name)
    return {"success": success, "message": "更新成功" if success else "更新失败"}

@app.post("/api/base/suppliers/batch-entity")
async def batch_update_supplier_entity(entity_name: str = Form(...)):
    """批量更新所有空汇总主体的供应商"""
    from src.services.database import db
    count = db.batch_update_supplier_entity(entity_name)
    return {"success": True, "message": f"已更新 {count} 条供应商", "count": count}

# ==================== 汇总主体管理 API ====================

@app.get("/api/summary-entities")
async def get_summary_entities():
    """获取所有汇总主体"""
    from src.services.database import db
    records = db.get_summary_entities()
    return {"success": True, "records": records}

@app.post("/api/summary-entities")
async def add_summary_entity(name: str = Form(...)):
    """添加汇总主体"""
    from src.services.database import db
    success = db.add_summary_entity(name)
    if success:
        return {"success": True, "message": "添加成功"}
    else:
        return {"success": False, "message": "名称已存在"}

@app.put("/api/summary-entities/{entity_id}")
async def update_summary_entity(entity_id: int, name: str = Form(...)):
    """更新汇总主体"""
    from src.services.database import db
    success = db.update_summary_entity(entity_id, name)
    if success:
        return {"success": True, "message": "更新成功"}
    else:
        return {"success": False, "message": "名称已存在或记录不存在"}

@app.delete("/api/summary-entities/{entity_id}")
async def delete_summary_entity(entity_id: int):
    """删除汇总主体"""
    from src.services.database import db
    success = db.delete_summary_entity(entity_id)
    return {"success": success, "message": "删除成功" if success else "删除失败"}

# ==================== 采购查询 API ====================

@app.get("/api/purchase/details/local")
async def get_purchase_details_local():
    """从本地数据库获取采购明细"""
    try:
        records = db.get_purchase_details_local()
        return {"success": True, "records": records, "total": len(records)}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e), "records": [], "total": 0}

@app.post("/api/purchase/details/sync")
async def sync_purchase_details():
    """从 API 同步采购明细到本地数据库"""
    # 分页拉取全部数据
    all_records = []
    page = 1
    while True:
        result = base_library_service.query_purchase_orders(page=page, page_size=1000)
        if not result["success"]:
            return {"success": False, "message": result.get("message", "查询失败")}
        records = result.get("records", [])
        if not records:
            break
        all_records.extend(records)
        if len(records) < 1000:
            break
        page += 1

    # 同步到本地数据库
    count = db.sync_purchase_details(all_records)
    return {"success": True, "message": f"已同步 {count} 条采购明细", "total": count}

@app.get("/api/purchase/orders")
async def query_purchase_orders(
    page: int = 1,
    page_size: int = 100,
    startTime: Optional[str] = None,
    endTime: Optional[str] = None,
    detailCode: Optional[str] = None,
    supplierCode: Optional[str] = None,
    supplierName: Optional[str] = None,
    purchaseCode: Optional[str] = None,
    purchaser: Optional[str] = None,
    categoryCode: Optional[str] = None,
    categoryName: Optional[str] = None,
    subCategoryCode: Optional[str] = None,
    subCategoryName: Optional[str] = None,
    cangSubCategoryCode: Optional[str] = None,
    cangSubCategoryName: Optional[str] = None,
    productCode: Optional[str] = None,
    productName: Optional[str] = None,
    inboundStatus: Optional[str] = None,
    inOrderId: Optional[str] = None,
):
    """查询采购明细"""
    filters = {
        "detailCode": detailCode or "",
        "supplierCode": supplierCode or "",
        "supplierName": supplierName or "",
        "purchaseCode": purchaseCode or "",
        "purchaser": purchaser or "",
        "categoryCode": categoryCode or "",
        "categoryName": categoryName or "",
        "subCategoryCode": subCategoryCode or "",
        "subCategoryName": subCategoryName or "",
        "cangSubCategoryCode": cangSubCategoryCode or "",
        "cangSubCategoryName": cangSubCategoryName or "",
        "productCode": productCode or "",
        "productName": productName or "",
        "inboundStatus": inboundStatus or "",
        "inOrderId": inOrderId or "",
        "startTime": startTime or "",
        "endTime": endTime or "",
    }
    result = base_library_service.query_purchase_orders(page=page, page_size=page_size, **filters)
    return result

@app.post("/api/purchase/detail/update-can-show")
async def update_purchase_detail_can_show(
    detail_id: int = Form(...),
    can_show: int = Form(default=0),
):
    """更新采购明细显示状态"""
    result = base_library_service.close_purchase_detail(detail_id=detail_id, can_show=can_show)
    if result.get("success"):
        # 同时更新本地数据库
        db.update_purchase_detail_can_show(detail_id, can_show)
    return result

@app.get("/api/purchase/order-list")
async def query_purchase_order_list(
    page: int = 1,
    page_size: int = 100,
    supplierCode: Optional[str] = None,
    supplierName: Optional[str] = None,
    purchaseCode: Optional[str] = None,
    purchaser: Optional[str] = None,
):
    """查询采购订单列表"""
    filters = {
        "supplierCode": supplierCode or "",
        "supplierName": supplierName or "",
        "purchaseCode": purchaseCode or "",
        "purchaser": purchaser or "",
    }
    result = base_library_service.query_purchase_order_list(page=page, page_size=page_size, **filters)
    return result

@app.post("/api/purchase/detail/add")
async def add_purchase_detail(
    purchase_code: str = Form(...),
    product_ids: str = Form(...),  # 逗号分隔的商品 ID
    quantity: int = Form(default=1),
    purchaser: str = Form(default="system"),
    purchase_time: Optional[str] = Form(default=None),
):
    """增加采购明细"""
    # 解析商品 ID 列表
    pid_list = [p.strip() for p in product_ids.split(",") if p.strip()]

    if not pid_list:
        return {"success": False, "message": "请提供商品 ID"}

    result = base_library_service.add_purchase_detail(
        purchase_code=purchase_code,
        product_ids=pid_list,
        quantity=quantity,
        purchaser=purchaser,
        purchase_time=purchase_time,
    )
    return result

@app.post("/api/purchase/inbound/add")
async def add_inbound_detail(
    purchase_code: str = Form(...),
    product_ids: str = Form(...),  # 逗号分隔的商品 ID
    quantity: int = Form(default=1),
    purchaser: str = Form(default="system"),
    purchase_time: Optional[str] = Form(default=None),
):
    """添加采购明细并入库"""
    # 解析商品 ID 列表
    pid_list = [p.strip() for p in product_ids.split(",") if p.strip()]

    if not pid_list:
        return {"success": False, "message": "请提供商品 ID"}

    result = base_library_service.add_inbound_detail(
        purchase_code=purchase_code,
        product_ids=pid_list,
        quantity=quantity,
        purchaser=purchaser,
        purchase_time=purchase_time,
    )
    return result

@app.post("/api/purchase/order/create")
async def create_purchase_order(
    supplier_id: int = Form(...),
    purchase_time: str = Form(...),
    purchaser: str = Form(default="system"),
):
    """创建采购订单"""
    result = base_library_service.create_purchase_order(
        supplier_id=supplier_id,
        purchase_time=purchase_time,
        purchaser=purchaser,
    )
    return result

@app.post("/api/purchase/detail/close")
async def close_purchase_detail(
    detail_id: int = Form(...),
):
    """关闭采购明细"""
    result = base_library_service.close_purchase_detail(detail_id=detail_id)
    return result

@app.post("/api/purchase/task/save")
async def save_purchase_task(request: Request):
    """保存采购任务"""
    import json
    from datetime import datetime

    data = await request.json()

    # 生成文件名
    summary_entity = data.get("summary_entity", "unknown")
    start_date = data.get("start_date", "")
    end_date = data.get("end_date", "")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    filename = f"{summary_entity}_{start_date}_{end_date}_{timestamp}.json"

    # 保存到文件
    tasks_dir = Path(__file__).parent.parent / "data" / "purchase-tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    file_path = tasks_dir / filename

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return {"success": True, "message": "任务已保存", "filename": filename}

@app.get("/api/purchase/task/list")
async def list_purchase_tasks():
    """获取采购任务列表"""
    import json
    from datetime import datetime

    tasks_dir = Path(__file__).parent.parent / "data" / "purchase-tasks"

    if not tasks_dir.exists():
        return {"success": True, "tasks": []}

    tasks = []
    for file in tasks_dir.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
            tasks.append({
                "filename": file.name,
                "summary_entity": data.get("summary_entity"),
                "total_amount": data.get("total_amount"),
                "start_date": data.get("start_date"),
                "end_date": data.get("end_date"),
                "days_count": len(data.get("days", [])),
                "created_at": data.get("created_at"),
            })
        except:
            continue

    # 按创建时间倒序
    tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return {"success": True, "tasks": tasks}

@app.get("/api/purchase/task/{filename}")
async def get_purchase_task(filename: str):
    """获取采购任务详情"""
    import json

    tasks_dir = Path(__file__).parent.parent / "data" / "purchase-tasks"
    file_path = tasks_dir / filename

    if not file_path.exists():
        return {"success": False, "message": "任务不存在"}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"success": True, "task": data}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.post("/api/purchase/sync-details")
async def sync_purchase_details():
    """同步采购明细到本地库"""
    from src.services.database import db

    # 拉取全部采购明细
    result = base_library_service.query_purchase_orders(page=1, page_size=10000)

    if not result["success"]:
        return {"success": False, "message": "查询采购明细失败"}

    records = result["records"]
    count = db.sync_purchase_details(records)

    return {"success": True, "message": f"已同步 {count} 条采购明细", "count": count}


@app.get("/api/purchase/export")
async def export_purchase_details(
    summary_entity: Optional[str] = None,
    supplier_code: Optional[str] = None,
    product_name: Optional[str] = None,
    purchaser: Optional[str] = None,
    inbound_status: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
):
    """导出采购明细为 Excel"""
    from fastapi.responses import StreamingResponse
    from io import BytesIO
    import pandas as pd
    from urllib.parse import quote

    # 从本地数据库获取数据
    records = db.get_purchase_details_local()

    if not records:
        return {"success": False, "message": "暂无数据可导出"}

    # 筛选逻辑(与前端一致)
    filtered_records = list(records)

    # 按汇总主体筛选
    if summary_entity:
        suppliers_result = db.get_suppliers()
        if suppliers_result:
            entity_supplier_codes = [s.get('supplier_code') for s in suppliers_result if s.get('summary_entity') == summary_entity]
            filtered_records = [r for r in filtered_records if r.get('supplier_code') in entity_supplier_codes]

    # 按供应商筛选
    if supplier_code:
        filtered_records = [r for r in filtered_records if r.get('supplier_code') == supplier_code]

    # 按商品名称筛选
    if product_name:
        keyword = product_name.lower()
        filtered_records = [r for r in filtered_records if (r.get('product_name') or '').lower().find(keyword) >= 0]

    # 按采购人筛选
    if purchaser:
        keyword = purchaser.lower()
        filtered_records = [r for r in filtered_records if (r.get('purchaser') or '').lower().find(keyword) >= 0]

    # 按入库状态筛选
    if inbound_status:
        filtered_records = [r for r in filtered_records if str(r.get('inbound_status')) == inbound_status]

    # 按进货时间筛选
    if start_time:
        filtered_records = [r for r in filtered_records if (r.get('purchase_time') or '').split(' ')[0] >= start_time]
    if end_time:
        filtered_records = [r for r in filtered_records if (r.get('purchase_time') or '').split(' ')[0] <= end_time]

    if not filtered_records:
        return {"success": False, "message": "筛选后无数据可导出"}

    # 计算汇总
    total_all = sum(r.get('total_price', 0) for r in filtered_records)
    total_show = sum(r.get('total_price', 0) for r in filtered_records if r.get('can_show') == 1)
    total_hide = sum(r.get('total_price', 0) for r in filtered_records if r.get('can_show') != 1)

    # 准备导出数据
    data = []
    for r in filtered_records:
        data.append({
            "明细编号": r.get("detail_code", ""),
            "采购单号": r.get("purchase_code", ""),
            "供应商": r.get("supplier_name", ""),
            "商品名称": r.get("product_name", ""),
            "分类": r.get("category_name", ""),
            "子分类": r.get("sub_category_name", ""),
            "数量": r.get("quantity", 0),
            "单价": r.get("unit_price", 0),
            "金额": r.get("total_price", 0),
            "采购人": r.get("purchaser", ""),
            "入库状态": "已入库" if r.get("inbound_status") == 1 else "未入库",
            "创建时间": r.get("create_time", ""),
            "进货时间": r.get("purchase_time", ""),
            "显示": "是" if r.get("can_show") == 1 else "否",
        })

    df = pd.DataFrame(data)

    # 导出 Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='采购明细', index=False)

        # 添加汇总行
        summary_df = pd.DataFrame([{
            "明细编号": "",
            "采购单号": "",
            "供应商": "合计",
            "商品名称": "",
            "分类": "",
            "子分类": "",
            "数量": "",
            "单价": "",
            "金额": total_all,
            "采购人": "",
            "入库状态": "",
            "创建时间": "",
            "进货时间": "",
            "显示": f"显示:{total_show:.2f} 隐藏:{total_hide:.2f}",
        }])
        summary_df.to_excel(writer, sheet_name='采购明细', startrow=len(df) + 2, index=False)

    output.seek(0)

    # 生成文件名
    time_range = f"{start_time or ''}_{end_time or ''}".strip('_') or '全部'
    filename = f"采购明细_{summary_entity or '全部'}_{time_range}.xlsx"
    encoded_filename = quote(filename)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )

@app.post("/api/purchase/adjust-day")
async def adjust_purchase_day(request: Request):
    """执行单日补采购(自动同步数据)"""
    import json
    from datetime import datetime
    from src.services.database import db

    data = await request.json()
    date_str = data.get("date")
    summary_entity = data.get("summary_entity")
    target_amount = data.get("target_amount")
    purchase_time = data.get("purchase_time")
    purchaser = data.get("purchaser")

    # 0. 先同步采购明细到本地库(分页拉取全部数据)
    print("同步采购明细...")
    all_records = []
    page = 1
    while True:
        sync_result = base_library_service.query_purchase_orders(page=page, page_size=1000)
        if not sync_result["success"]:
            print(f"查询采购明细失败: {sync_result.get('message')}")
            break
        records = sync_result.get("records", [])
        if not records:
            break
        all_records.extend(records)
        if len(records) < 1000:
            break
        page += 1

    if all_records:
        db.sync_purchase_details(all_records)
        print(f"已同步 {len(all_records)} 条采购明细")

    # 1. 获取属于该汇总主体的供应商
    suppliers = db.get_suppliers()
    entity_suppliers = [s for s in suppliers if s.get("summary_entity") == summary_entity]
    entity_supplier_codes = [s.get("supplier_code") for s in entity_suppliers]

    if not entity_supplier_codes:
        return {"success": False, "message": f"汇总主体 {summary_entity} 下没有供应商"}

    # 2. 从本地库查询当天的采购明细(按进货时间筛选)
    valid_details = db.get_purchase_details_by_date(date_str, entity_supplier_codes)
    valid_details = [d for d in valid_details if d.get("can_show", 1) == 1]

    # 3. 计算当前总金额
    current_amount = sum(d.get("total_price", 0) or 0 for d in valid_details)
    diff_amount = target_amount - current_amount

    print(f"目标金额: {target_amount}, 当前金额: {current_amount}, 差额: {diff_amount}")

    result_log = {
        "date": date_str,
        "target_amount": target_amount,
        "current_amount": current_amount,
        "diff_amount": diff_amount,
        "actions": [],
    }

    # 4. 调整策略
    if diff_amount < 0:
        # 需要关闭明细(从最接近差额的开始)
        sorted_details = sorted(valid_details, key=lambda d: abs(d.get("total_price", 0) - abs(diff_amount)))
        close_amount = 0
        for d in sorted_details:
            if current_amount - close_amount <= target_amount:
                break
            detail_id = d.get("id")
            close_result = base_library_service.close_purchase_detail(detail_id)
            if close_result["success"]:
                close_amount += d.get("total_price", 0) or 0
                # 同步更新本地库
                db.update_purchase_detail_can_show(detail_id, 0)
                result_log["actions"].append({"action": "close", "detail_id": detail_id, "amount": d.get("total_price", 0)})
        current_amount -= close_amount
        diff_amount = target_amount - current_amount
        print(f"关闭明细后: 当前金额={current_amount}, 差额={diff_amount}")

    # 6. 如果差额 > 0,需要增加采购
    if diff_amount > 0.01:
        # 获取商品库中属于该汇总主体的商品(只使用贸易品)
        goods_result = base_library_service.query_all_goods()
        if not goods_result["success"]:
            return {"success": False, "message": "查询商品库失败"}

        # 排除的供应商代码
        excluded_supplier_codes = ["G00003", "G00004"]

        entity_goods = []
        for g in goods_result["records"]:
            supplier_code = g.get("supplierCode", "")
            category_name = g.get("categoryName", "")
            cang_sub_category_name = g.get("cangSubCategoryName", "")

            # 排除现采和加工品
            if category_name in ["现采", "加工品"]:
                continue
            # 排除档口分类包含"现采"的商品
            if cang_sub_category_name and "现采" in cang_sub_category_name:
                continue
            # 排除指定供应商
            if supplier_code in excluded_supplier_codes:
                continue
            # 只取上架状态的商品
            if g.get("status", 1) != 1:
                continue

            if supplier_code in entity_supplier_codes:
                entity_goods.append(g)

        print(f"筛选商品: 总数 {len(goods_result['records'])}, 符合条件 {len(entity_goods)}")

        if not entity_goods:
            return {"success": False, "message": f"汇总主体 {summary_entity} 下没有可用的商品"}

        # 7. 贪心算法选择商品(返回商品ID和数量)
        selected_goods_map = greedy_select_goods(diff_amount, entity_goods)
        print(f"贪心选择商品: {len(selected_goods_map)} 种,目标差额: {diff_amount}")

        # 打印选择的商品详情
        for pid, item in selected_goods_map.items():
            g = item["goods"]
            print(f"  - {g.get('productName')}: {item['quantity']} x {g.get('unitPrice') or g.get('inPrice')} = {(g.get('unitPrice') or g.get('inPrice') or 0) * item['quantity']}")

        if not selected_goods_map:
            return {"success": False, "message": f"无法找到合适的商品组合来填补差额 ¥{diff_amount:.2f}"}

        # 8. 按供应商分组处理商品
        add_amount = 0

        # 先按供应商分组
        supplier_groups = {}
        for product_id, item in selected_goods_map.items():
            g = item["goods"]
            supplier_code = g.get("supplierCode")
            if supplier_code not in supplier_groups:
                supplier_groups[supplier_code] = []
            supplier_groups[supplier_code].append({"product_id": product_id, "item": item})

        print(f"按供应商分组: {len(supplier_groups)} 个供应商")
        for sc, items in supplier_groups.items():
            total_amount = sum((it["item"]["goods"].get("unitPrice") or it["item"]["goods"].get("inPrice") or 0) * it["item"]["quantity"] for it in items)
            print(f"  {sc}: {len(items)} 个商品, 金额 {total_amount:.2f}")

        # 按供应商处理
        for supplier_code, items in supplier_groups.items():
            # 找到供应商 ID
            supplier_id = None
            for s in entity_suppliers:
                if s.get("supplier_code") == supplier_code:
                    supplier_id = s.get("id")
                    break

            print(f"\n处理供应商: {supplier_code}, ID={supplier_id}")

            if not supplier_id:
                print(f"  未找到供应商ID,跳过")
                continue

            # 查询该供应商今天的采购单
            existing_order = None
            existing_orders = base_library_service.query_purchase_order_list(
                supplierCode=supplier_code,
                purchaser=purchaser,
                page_size=10,
            )
            if existing_orders["success"] and existing_orders["records"]:
                # 找到今天创建的采购单
                for order in existing_orders["records"]:
                    if order.get("purchaseTime", "").startswith(date_str):
                        existing_order = order
                        print(f"  找到现有采购单: {order.get('purchaseCode')}")
                        break

            # 如果没有现有采购单,创建新的
            if not existing_order:
                order_result = base_library_service.create_purchase_order(
                    supplier_id=supplier_id,
                    purchase_time=purchase_time,
                    purchaser=purchaser,
                )
                print(f"  创建采购订单: {order_result}")

                if not order_result["success"]:
                    result_log["actions"].append({"action": "create_order_failed", "supplier_code": supplier_code, "message": order_result["message"]})
                    continue

                # 获取新创建的采购单
                new_orders = base_library_service.query_purchase_order_list(
                    supplierCode=supplier_code,
                    purchaser=purchaser,
                    page_size=10,
                )
                if new_orders["success"] and new_orders["records"]:
                    existing_order = new_orders["records"][0]
                    print(f"  新创建的采购单: {existing_order.get('purchaseCode')}")
                else:
                    print(f"  未找到新创建的订单")
                    continue

            purchase_code = existing_order.get("purchaseCode")

            # 处理该供应商的所有商品
            for entry in items:
                product_id = entry["product_id"]
                item = entry["item"]
                g = item["goods"]
                quantity = item["quantity"]

                print(f"  处理商品: {g.get('productName')}, 数量={quantity}")

                # 添加采购明细并入库(add_inbound_detail 内部会调用 add_purchase_detail)
                inbound_result = base_library_service.add_inbound_detail(
                    purchase_code=purchase_code,
                    product_ids=[product_id],
                    quantity=quantity,
                    purchaser="system",
                    purchase_time=purchase_time,
                )
                print(f"    添加明细并入库: {inbound_result}")

                if inbound_result["success"]:
                    price = g.get("unitPrice") or g.get("inPrice") or 0
                    item_amount = price * quantity
                    add_amount += item_amount
                    result_log["actions"].append({
                        "action": "add",
                        "purchase_code": purchase_code,
                        "product_id": product_id,
                        "name": g.get("productName"),
                        "price": price,
                        "quantity": quantity,
                        "amount": item_amount,
                        "inbound": True
                    })
                else:
                    print(f"    添加明细失败: {inbound_result.get('message')}")


        current_amount += add_amount
        diff_amount = target_amount - current_amount

    # 9. 验算: 重新查询采购明细并计算总金额
    print("=== 开始验算 ===")
    all_verify_records = []
    page = 1
    while True:
        sync_result = base_library_service.query_purchase_orders(page=page, page_size=1000)
        if not sync_result["success"]:
            break
        records = sync_result.get("records", [])
        if not records:
            break
        all_verify_records.extend(records)
        if len(records) < 1000:
            break
        page += 1

    if all_verify_records:
        db.sync_purchase_details(all_verify_records)
        print(f"验算同步: {len(all_verify_records)} 条采购明细")

    verify_details = db.get_purchase_details_by_date(date_str, entity_supplier_codes)
    verify_details = [d for d in verify_details if d.get("can_show", 1) == 1]
    verify_amount = sum(d.get("total_price", 0) or 0 for d in verify_details)
    verify_diff = target_amount - verify_amount
    print(f"验算结果: 目标={target_amount:.2f}, 实际={verify_amount:.2f}, 差额={verify_diff:.2f}")
    print("=== 验算完成 ===")

    result_log["final_current_amount"] = verify_amount
    result_log["final_diff_amount"] = verify_diff
    result_log["verify_details_count"] = len(verify_details)

    return {
        "success": True,
        "message": f"调整完成,验算金额 ¥{verify_amount:.2f},差额 ¥{verify_diff:.2f}",
        "current_amount": verify_amount,
        "diff_amount": verify_diff,
        "log": result_log,
    }


def greedy_select_goods(target_amount: float, goods_list: list) -> dict:
    """贪心算法选择商品组合(精确补齐到 0.01 元级别)

    算法流程:
    1. 按价格排序(从大到小)
    2. 用大金额商品填满大部分差额
    3. 用小金额商品精确补齐零头(0.1 元、0.01 元)

    Args:
        target_amount: 目标差额金额
        goods_list: 可用商品列表

    Returns:
        dict: {商品ID: {"goods": 商品对象, "quantity": 数量}}
    """
    # 按价格排序(从大到小)
    sorted_goods = sorted(goods_list, key=lambda g: g.get("unitPrice") or g.get("inPrice") or 0, reverse=True)

    # 过滤掉价格为 0 的商品
    valid_goods = [g for g in sorted_goods if (g.get("unitPrice") or g.get("inPrice") or 0) > 0]

    if not valid_goods:
        return {}

    # 分离大金额商品和小金额商品(用于补零头)
    # 小金额商品: 价格 <= 1 元的(如 1 元、0.1 元、0.01 元)
    big_goods = [g for g in valid_goods if (g.get("unitPrice") or g.get("inPrice") or 0) > 1]
    small_goods = [g for g in valid_goods if (g.get("unitPrice") or g.get("inPrice") or 0) <= 1]

    selected = {}  # {商品ID: {"goods": 商品对象, "quantity": 数量}}
    remaining = target_amount

    # 第一阶段: 用大金额商品填满大部分差额
    for g in big_goods:
        price = g.get("unitPrice") or g.get("inPrice") or 0
        product_id = str(g.get("id"))

        # 计算可以选多少个(整数)
        count = int(remaining / price)

        if count > 0:
            selected[product_id] = {
                "goods": g,
                "quantity": count
            }
            remaining -= price * count

        # 如果剩余已经小于最小大金额商品,可以切换到小金额商品
        if remaining <= 1.01:
            break

    # 第二阶段: 用小金额商品精确补齐零头
    # 按价格排序(从大到小),确保能精确补齐
    small_goods_sorted = sorted(small_goods, key=lambda g: g.get("unitPrice") or g.get("inPrice") or 0, reverse=True)

    for g in small_goods_sorted:
        price = g.get("unitPrice") or g.get("inPrice") or 0
        product_id = str(g.get("id"))

        # 计算可以选多少个
        count = int(remaining / price)

        if count > 0:
            if product_id in selected:
                selected[product_id]["quantity"] += count
            else:
                selected[product_id] = {
                    "goods": g,
                    "quantity": count
                }
            remaining -= price * count

        # 如果已经精确补齐(剩余 <= 0.005),退出
        if remaining <= 0.005:
            break

    # 第三阶段: 如果还有极小剩余(如 0.003),用最小价格商品补一个
    if remaining > 0.005 and small_goods_sorted:
        min_price_goods = small_goods_sorted[-1]  # 最小价格商品
        min_price = min_price_goods.get("unitPrice") or min_price_goods.get("inPrice") or 0
        min_product_id = str(min_price_goods.get("id"))

        if min_product_id in selected:
            selected[min_product_id]["quantity"] += 1
        else:
            selected[min_product_id] = {
                "goods": min_price_goods,
                "quantity": 1
            }
        remaining -= min_price

    # 计算最终总金额
    total_selected = sum(
        (item["goods"].get("unitPrice") or item["goods"].get("inPrice") or 0) * item["quantity"]
        for item in selected.values()
    )
    print(f"贪心算法完成: 选择金额={total_selected:.2f}, 剩余差额={remaining:.2f}")

    return selected


# ========== 补全进货时间 API ========== 
import random

def parse_purchase_code_date(purchase_code: str) -> str | None:
    """从采购单号解析日期
    
    例如: JH260202262 -> 2026-02-02
    格式: JH + YYMMDD + 序号
    """
    if not purchase_code or not purchase_code.startswith('JH'): 
        return None
    
    # 提取日期部分 (JH 后的 6 位)
    date_part = purchase_code[2:8]
    if len(date_part) != 6:
        return None
    
    try:
        yy = int(date_part[0:2])
        mm = int(date_part[2:4])
        dd = int(date_part[4:6])
        # 年份处理: 26 -> 2026
        year = 2000 + yy if yy >= 0 else 1900 + yy
        return f"{year:04d}-{mm:02d}-{dd:02d}"
    except:
        return None

def generate_random_work_time() -> str:
    """生成随机工作时间 (08:00-20:00)"""
    hour = random.randint(8, 19)  # 8点到19点（20点不算在内）
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return f"{hour:02d}:{minute:02d}:{second:02d}"

@app.get("/api/purchase/validate-time")
async def validate_purchase_time():
    """检验采购订单与明细的进货时间是否一致
    
    返回:
    - orders_with_mismatch: 订单进货时间与明细进货时间不在同一天的列表
    - details_without_time: 没有进货时间的明细列表
    """
    # 从本地库获取所有采购明细
    all_details = db.get_all_purchase_details()
    
    if not all_details:
        return {
            "success": False,
            "message": "本地库没有采购明细数据，请先同步数据",
            "orders_with_mismatch": [],
            "details_without_time": []
        }
    
    # 按采购单号分组
    order_groups = {}
    for d in all_details:
        purchase_code = d.get("purchase_code") or ""
        if purchase_code not in order_groups:
            order_groups[purchase_code] = []
        order_groups[purchase_code].append(d)
    
    # 检验结果
    orders_with_mismatch = []
    details_without_time = []
    
    for purchase_code, details in order_groups.items():
        if not purchase_code:
            # 没有采购单号的明细，检查是否有进货时间
            for d in details:
                if not d.get("purchase_time"):
                    details_without_time.append({
                        "id": d.get("id"),
                        "detail_code": d.get("detail_code"),
                        "purchase_code": purchase_code,
                        "supplier_name": d.get("supplier_name"),
                        "product_name": d.get("product_name"),
                        "total_price": d.get("total_price"),
                        "purchase_time": d.get("purchase_time"),
                        "create_time": d.get("create_time"),
                    })
            continue
        
        # 从采购单号解析日期
        parsed_date = parse_purchase_code_date(purchase_code)
        if not parsed_date:
            continue
        
        # 检查每条明细
        for d in details:
            purchase_time = d.get("purchase_time")
            
            if not purchase_time:
                # 没有进货时间
                details_without_time.append({
                    "id": d.get("id"),
                    "detail_code": d.get("detail_code"),
                    "purchase_code": purchase_code,
                    "supplier_name": d.get("supplier_name"),
                    "product_name": d.get("product_name"),
                    "total_price": d.get("total_price"),
                    "purchase_time": purchase_time,
                    "create_time": d.get("create_time"),
                    "parsed_date": parsed_date,  # 解析出的日期
                })
            else:
                # 检查日期是否一致
                detail_date = purchase_time.split(" ")[0] if " " in purchase_time else purchase_time[:10]
                if detail_date != parsed_date:
                    orders_with_mismatch.append({
                        "id": d.get("id"),
                        "detail_code": d.get("detail_code"),
                        "purchase_code": purchase_code,
                        "supplier_name": d.get("supplier_name"),
                        "product_name": d.get("product_name"),
                        "total_price": d.get("total_price"),
                        "purchase_time": purchase_time,
                        "parsed_date": parsed_date,
                    })
    
    return {
        "success": True,
        "message": f"检验完成: {len(orders_with_mismatch)} 条时间不一致, {len(details_without_time)} 条缺失进货时间",
        "orders_with_mismatch": orders_with_mismatch,
        "details_without_time": details_without_time,
        "total_details": len(all_details),
        "total_orders": len(order_groups),
    }

@app.post("/api/purchase/fill-time")
async def fill_purchase_time(request: Request):
    """补全采购明细的进货时间
    
    支持两种模式:
    - type=orders, targets=[purchase_code, ...] - 按采购单号补全（根据订单号解析日期）
    - type=details, targets=[detail_id, ...] - 按明细ID补全（根据订单的进货时间）
    """
    import random
    
    def generate_random_work_time() -> str:
        """生成随机工作时间 (08:00-20:00)"""
        hour = random.randint(8, 19)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        return f"{hour:02d}:{minute:02d}:{second:02d}"
    
    data = await request.json()
    fill_type = data.get("type", "details")  # orders 或 details
    targets = data.get("targets", [])
    
    # 获取所有明细
    all_details = db.get_all_purchase_details()
    detail_map = {d.get("id"): d for d in all_details}
    
    # 构建订单进货时间映射（订单 -> 该订单下第一条有进货时间的明细的时间）
    order_purchase_time = {}
    for d in all_details:
        code = d.get("purchase_code") or ""
        if d.get("purchase_time") and code not in order_purchase_time:
            order_purchase_time[code] = d.get("purchase_time")
    
    success_count = 0
    fail_count = 0
    skip_count = 0
    results = []
    
    if fill_type == "orders":
        # 订单模式：根据订单号解析日期，更新订单的进货时间
        for purchase_code in targets:
            parsed_date = parse_purchase_code_date(purchase_code)
            if not parsed_date:
                fail_count += 1
                results.append({
                    "target": purchase_code,
                    "type": "订单",
                    "success": False,
                    "message": f"无法解析采购单号 {purchase_code}"
                })
                continue
            
            # 生成随机工作时间
            random_time = generate_random_work_time()
            new_time = f"{parsed_date} {random_time}"
            
            # 调用 API 更新订单进货时间
            try:
                update_result = base_library_service.update_purchase_order_time(purchase_code, new_time)
                
                if update_result["success"]:
                    success_count += 1
                    results.append({
                        "target": purchase_code,
                        "type": "订单",
                        "success": True,
                        "new_time": new_time,
                        "message": "订单进货时间更新成功"
                    })
                else:
                    fail_count += 1
                    results.append({
                        "target": purchase_code,
                        "type": "订单",
                        "success": False,
                        "message": update_result.get("message", "更新失败")
                    })
            except Exception as e:
                fail_count += 1
                results.append({
                    "target": purchase_code,
                    "type": "订单",
                    "success": False,
                    "message": str(e)
                })
    
    else:
        # 明细模式：根据订单的进货时间补全明细
        for detail_id in targets:
            detail_id = int(detail_id)
            detail = detail_map.get(detail_id)
            if not detail:
                fail_count += 1
                results.append({
                    "target": detail_id,
                    "type": "明细",
                    "success": False,
                    "message": "明细不存在"
                })
                continue
            
            purchase_code = detail.get("purchase_code") or ""
            old_time = detail.get("purchase_time")
            
            # 获取订单的进货时间
            order_time = order_purchase_time.get(purchase_code)
            if not order_time:
                fail_count += 1
                results.append({
                    "target": purchase_code or detail_id,
                    "type": "明细",
                    "success": False,
                    "old_time": old_time,
                    "message": "订单没有进货时间，请先整理订单"
                })
                continue
            
            # 提取日期部分
            order_date = order_time.split(" ")[0] if " " in order_time else order_time[:10]
            
            # 如果明细已有进货时间且日期一致，跳过
            if old_time:
                old_date = old_time.split(" ")[0] if " " in old_time else old_time[:10]
                if old_date == order_date:
                    skip_count += 1
                    results.append({
                        "target": purchase_code,
                        "type": "明细",
                        "success": True,
                        "skipped": True,
                        "old_time": old_time,
                        "new_time": old_time,
                        "message": "日期已一致，跳过"
                    })
                    continue
            
            # 生成随机工作时间
            random_time = generate_random_work_time()
            new_time = f"{order_date} {random_time}"
            
            # 调用 API 更新
            try:
                update_url = f"/restful/shasha/supply/ordersDetail/updateField?field=purchaseTime&value={new_time}&id={detail_id}"
                api_result = api_client.post(update_url, data={})
                
                if api_result.get("code") == 1:
                    db.update_purchase_detail_time(detail_id, new_time)
                    success_count += 1
                    results.append({
                        "target": purchase_code,
                        "type": "明细",
                        "success": True,
                        "old_time": old_time,
                        "new_time": new_time,
                        "message": "更新成功"
                    })
                else:
                    fail_count += 1
                    results.append({
                        "target": purchase_code,
                        "type": "明细",
                        "success": False,
                        "old_time": old_time,
                        "new_time": new_time,
                        "message": api_result.get("msg", "API 返回错误")
                    })
            except Exception as e:
                fail_count += 1
                results.append({
                    "target": purchase_code,
                    "type": "明细",
                    "success": False,
                    "old_time": old_time,
                    "message": str(e)
                })
    
    return {
        "success": True,
        "message": f"处理完成: 成功 {success_count}, 失败 {fail_count}, 跳过 {skip_count}",
        "updated": success_count,
        "failed": fail_count,
        "skipped": skip_count,
        "results": results,
    }

# ========== 摸鱼游戏 API ========== 
from src.game import typing as typing_game
from src.game import findcow as findcow_game

@app.get("/api/game/typing/vocabs")
async def api_game_typing_vocabs():
    """获取打字练习词库列表"""
    return {"vocabs": typing_game.get_vocab_list()}


@app.get("/api/game/typing/word")
async def api_game_typing_word(vocab: str = "programmer"):
    """获取随机单词"""
    return typing_game.get_random_word(vocab)


@app.post("/api/game/typing/verify")
async def api_game_typing_verify(vocab: str = Form(...), word: str = Form(...), user_input: str = Form(...)):
    """验证用户输入"""
    return typing_game.verify_word(vocab, word, user_input)


@app.post("/api/game/findcow/generate")
async def api_game_findcow_generate(size: int = Form(6)):
    """生成找牛关卡"""
    return findcow_game.generate_puzzle(size)


@app.post("/api/game/findcow/verify")
async def api_game_findcow_verify(puzzle: str = Form(...), row: int = Form(...), col: int = Form(...)):
    """验证用户猜测"""
    puzzle_data = json.loads(puzzle)
    return findcow_game.verify_cow(puzzle_data, row, col)


# ========== RPG 游戏页面 ==========

@app.get("/rpg", response_class=HTMLResponse)
async def rpg_game():
    """RPG 游戏页面"""
    return render_template("game.html", {})

@app.get("/editor", response_class=HTMLResponse)
async def game_editor():
    """游戏编辑器页面"""
    return render_template("editor.html", {})


# ========== 耗用管理 API ==========

from src.services.consume_query import consume_query_service
from src.services.stock_flow import stock_flow_service
from src.services.consume_task import consume_task_service
from src.services.data_sync import data_sync_service

@app.get("/consume-query", response_class=HTMLResponse)
async def consume_query_page():
    """耗用查询页面"""
    return render_template("consume_query.html", {})

@app.get("/stock-flow", response_class=HTMLResponse)
async def stock_flow_page():
    """库存流水页面"""
    return render_template("stock_flow.html", {})

@app.get("/stock-query", response_class=HTMLResponse)
async def stock_query_page():
    """库存查询页面"""
    return render_template("stock_query.html", {})

@app.get("/consume-task", response_class=HTMLResponse)
async def consume_task_page():
    """耗用任务页面"""
    return render_template("consume_task.html", {})

@app.get("/consume-adjust", response_class=HTMLResponse)
async def consume_adjust_page(task: str = None):
    """补耗用页面"""
    return render_template("consume_adjust.html", {})

# ========== 数据同步 API ==========

@app.get("/api/sync/status")
async def api_sync_status():
    """获取同步状态"""
    return stock_flow_service.get_sync_status()

@app.get("/api/sync/supply")
async def api_sync_supply(store_id: Optional[int] = None):
    """同步要货数据到本地"""
    return stock_flow_service.sync_supply_orders(store_id)

@app.get("/api/sync/consume")
async def api_sync_consume(store_id: Optional[int] = None):
    """同步耗用数据到本地"""
    return stock_flow_service.sync_consume_records(store_id)

@app.get("/api/sync/all")
async def api_sync_all(store_id: Optional[int] = None):
    """同步全部数据（要货 + 耗用）"""
    return stock_flow_service.sync_all(store_id)

# ========== 耗用查询 API ==========

@app.get("/api/consume/query")
async def api_consume_query(
    store_id: Optional[int] = None,
    category_name: Optional[str] = None,
    product_name: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    page: int = 1,
    page_size: int = 50
):
    """查询耗用记录（从本地数据库）"""
    # 获取全部数据的汇总
    summary = db.get_consume_summary(
        store_id=store_id,
        category_name=category_name,
        product_name=product_name,
        start_time=start_time,
        end_time=end_time
    )
    
    # 获取分页数据
    records = db.get_consume_records(
        store_id=store_id,
        category_name=category_name,
        product_name=product_name,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size
    )
    
    total = summary["total_records"]
    total_pages = max(1, (total + page_size - 1) // page_size)
    
    return {
        "success": True,
        "total": total,
        "pages": total_pages,
        "current": page,
        "records": records,
        "total_quantity": summary["total_quantity"],
        "total_amount": summary["total_amount"]
    }

# ========== 库存流水 API ==========

@app.get("/api/stock/flows")
async def api_stock_flows(
    store_id: Optional[int] = None,
    product_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 500
):
    """获取库存流水（从本地缓存）"""
    return stock_flow_service.get_stock_flows(
        store_id=store_id,
        product_id=product_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )

@app.get("/api/stock/current")
async def api_stock_current(store_id: Optional[int] = None):
    """获取当前库存"""
    return stock_flow_service.get_current_stock(store_id)

@app.post("/api/stock/snapshot")
async def api_stock_snapshot(store_id: Optional[int] = None):
    """保存库存快照"""
    return stock_flow_service.save_snapshot(store_id)

# ========== 耗用任务 API ==========

@app.get("/api/consume-tasks/list")
async def api_consume_tasks_list():
    """获取耗用任务列表"""
    tasks = consume_task_service.get_task_list()
    return {"success": True, "tasks": tasks}

@app.get("/api/consume-tasks/{task_id}")
async def api_consume_task_get(task_id: str):
    """获取单个耗用任务"""
    task = consume_task_service.get_task(task_id)
    if task:
        return {"success": True, "task": task}
    return {"success": False, "message": "任务不存在"}

@app.post("/api/consume-tasks/save")
async def api_consume_task_save(request: Request):
    """保存耗用任务"""
    data = await request.json()
    return consume_task_service.save_task(data)

@app.get("/api/consume-task/preview")
async def api_consume_task_preview(
    store_id: int,
    start_date: str,
    end_date: str,
    total_amount: float,
    daily_float_percent: float = 0.1,
    excluded_dates: str = None
):
    """预览耗用方案"""
    # 解析排除日期
    excluded_list = []
    if excluded_dates:
        excluded_list = [d.strip() for d in excluded_dates.split(',') if d.strip()]
    
    task = {
        "store_id": store_id,
        "start_date": start_date,
        "end_date": end_date,
        "total_amount": total_amount,
        "daily_float_percent": daily_float_percent,
        "excluded_dates": excluded_list
    }
    return consume_task_service.generate_consume_plan(task)

@app.post("/api/consume-task/execute-all")
async def api_consume_task_execute_all(task_id: str):
    """执行完整耗用任务"""
    return consume_task_service.execute_task(task_id)