"""认证服务"""

import json
import time
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from src.config import config
from src.api.client import api_client


class AuthService:
    """认证服务"""
    
    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._driver: Optional[webdriver.Chrome] = None
        self._token_file = Path(__file__).parent.parent.parent / "config" / "token.json"
    
    def _create_driver(self, headless: bool = False) -> webdriver.Chrome:
        """创建 Chrome 驱动
        
        Args:
            headless: 是否无头模式，登录时需要看到页面所以用 False
        """
        options = Options()
        
        if headless:
            options.add_argument("--headless")
        
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        driver_path = Path(__file__).parent.parent.parent / "chromedriver-win64" / "chromedriver.exe"
        driver = webdriver.Chrome(service=Service(str(driver_path)), options=options)
        driver.set_window_size(1266, 1380)
        driver.set_window_rect(x=1300, y=0, width=1266, height=1380)
        driver.implicitly_wait(2)
        return driver
    
    def login_with_captcha(self) -> bool:
        """登录并获取 Token"""
        try:
            # 启动浏览器（非无头模式，用户需要看到验证码）
            print("正在启动浏览器...")
            self._driver = self._create_driver(headless=False)
            
            homepage = config._data.get("homepage", config.api_base_url + "/admin.html")
            print(f"打开首页: {homepage}")
            self._driver.get(homepage)
            
            print("正在抓取 Chrome 性能日志，请等待...")
            time.sleep(10)
            
            logs = self._driver.get_log("performance")
            captcha_id = self._extract_captcha_id(logs)
            
            if not captcha_id:
                print("未能获取验证码 ID")
                return False
            
            print(f"验证码 ID: {captcha_id}")
            verification_code = input("请输入验证码: ")
            
            login_data = {
                "username": config.username,
                "password": config.password,
                "verificationCode": verification_code,
                "captchaName": captcha_id
            }
            
            response = api_client.post("login", data=login_data)
            
            if response.get("code") == 1 and response.get("msg") == "OK":
                token = response["data"]["token"]
                self._token = token
                api_client.set_token(token)
                self._save_token(token)
                print("登录成功！")
                return True
            else:
                print(f"登录失败: {response.get('msg', '未知错误')}")
                return False
                
        except Exception as e:
            print(f"登录出错: {e}")
            return False
        finally:
            # 关闭浏览器
            if self._driver:
                self._driver.quit()
                self._driver = None
    
    def _extract_captcha_id(self, logs: list) -> Optional[str]:
        for log in logs:
            try:
                data = json.loads(log["message"])
                message = data["message"]
                if message["method"] == "Network.responseReceivedExtraInfo":
                    headers = message["params"].get("headers", {})
                    if "gif-captcha-id" in headers:
                        return headers["gif-captcha-id"]
            except (json.JSONDecodeError, KeyError):
                continue
        return None
    
    def _save_token(self, token: str) -> None:
        from datetime import datetime
        self._token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._token_file, "w", encoding="utf-8") as f:
            json.dump({
                "token": token,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }, f, indent=2)
        print(f"Token 已保存到: {self._token_file}")
    
    def load_token(self) -> bool:
        if not self._token_file.exists():
            return False
        try:
            with open(self._token_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                token = data.get("token")
                if token:
                    self._token = token
                    api_client.set_token(token)
                    return True
        except (json.JSONDecodeError, KeyError):
            pass
        return False
    
    def get_token_info(self) -> Optional[dict]:
        """获取 token 信息（包含更新时间）"""
        if not self._token_file.exists():
            return None
        try:
            with open(self._token_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "token": data.get("token"),
                    "updated_at": data.get("updated_at")
                }
        except:
            return None
    
    def get_token(self) -> Optional[str]:
        return self._token


auth_service = AuthService()