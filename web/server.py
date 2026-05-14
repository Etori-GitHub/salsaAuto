"""Web UI 服务"""

import json
import subprocess
import re
import os
import zipfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional
from io import BytesIO

import requests

from fastapi import FastAPI, Request, Form
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

# 浏览器实例（保持打开）
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
    return render_template("index.html", {"request": request})


@app.get("/stores", response_class=HTMLResponse)
async def stores_page(request: Request):
    return render_template("stores.html", {"request": request})


@app.get("/dishes", response_class=HTMLResponse)
async def dishes_page(request: Request):
    return render_template("dishes.html", {"request": request})


@app.get("/members", response_class=HTMLResponse)
async def members_page(request: Request):
    return render_template("members.html", {"request": request})


@app.get("/orders", response_class=HTMLResponse)
async def orders_page(request: Request):
    return render_template("orders.html", {"request": request})


@app.get("/calculator", response_class=HTMLResponse)
async def calculator_page(request: Request):
    return render_template("calculator.html", {"request": request})


@app.get("/records", response_class=HTMLResponse)
async def records_page(request: Request):
    return render_template("records.html", {"request": request})


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
    return {"stores": config.get_all_stores()}


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
    start_date: str = None, end_date: str = None, store_id: int = None, limit: int = 100
):
    """查询刷单记录"""
    from src.services.database import db
    records = db.get_order_records(start_date, end_date, store_id, limit)
    stats = db.get_statistics(start_date, end_date)
    return {"records": records, "statistics": stats}


@app.get("/api/orders/statistics")
async def get_order_statistics(start_date: str = None, end_date: str = None):
    """获取刷单统计"""
    from src.services.database import db
    return db.get_statistics(start_date, end_date)


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
    """启动登录流程，获取验证码图片"""
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
        
        # 不关闭浏览器，保留给用户输入验证码
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
    """获取 Token（已废弃）"""
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
            "message": f"任务执行完成，共 {result['total_orders']} 个订单",
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