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
from src.services.order_query import order_query_service
from src.services.store_query import store_query_service
from src.services.supply_query import supply_query_service
from src.services.base_library import base_library_service
from src.services.monthly_order import monthly_order_service


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

@app.get("/order-query", response_class=HTMLResponse)
async def order_query_page(request: Request):
    return render_template("order_query.html", {"request": request, "page": "order-query"})

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
    """获取门店列表，只返回可见门店"""
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
    return {"members": member_service.get_all_members(), "count": len(member_service.get_all_members())}


@app.post("/api/members/sync")
async def sync_members():
    result = member_service.sync_from_api()
    return {"success": result.get("code") == 1, "message": result.get("msg", "同步完成")}


@app.post("/api/members/{member_id}/type")
async def set_member_type(member_id: str, type: str = Form(...)):
    success = member_service.set_member_type(member_id, type)
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
async def execute_task(task_id: str, member_type: str = Form(default="")):
    """执行刷单任务"""
    tasks_dir = Path(__file__).parent.parent / "data" / "tasks"
    file_path = tasks_dir / f"{task_id}.json"

    if not file_path.exists():
        return {"success": False, "message": "任务不存在"}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            task_data = json.load(f)

        result = order_service.execute_task(task_data, member_type=member_type)

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

    init_chrome_versions()

    # 加载 Token
    auth_service.load_token()

    url = f"http://{host}:{port}"

    def open_browser():
        time.sleep(1)
        webbrowser.open(url)

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
        category = record.get("dish", {}).get("categoryName", "")
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

        category_name = record.get("dish", {}).get("categoryName", "未分类")
        category_code = record.get("dish", {}).get("categoryCode", "")
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