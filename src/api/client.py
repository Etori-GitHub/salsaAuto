"""API 客户端"""

import json
from typing import Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import config


class APIClient:
    """API 客户端"""
    
    def __init__(self) -> None:
        self.session = self._create_session()
        self._token: Optional[str] = None
    
    def _create_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        requests.packages.urllib3.disable_warnings()
        return session
    
    def set_token(self, token: str) -> None:
        self._token = token
        self.session.headers.update({
            "authorization": f"Bearer {token}",
            "source-type": "admin",
        })
    
    def get_token(self) -> Optional[str]:
        return self._token
    
    def _request(self, method: str, endpoint: str, params: Optional[dict] = None, 
                 data: Optional[dict] = None, **kwargs) -> dict:
        # 判断是端点名称还是完整路径
        if endpoint.startswith("/"):
            # 已经是路径，直接拼接
            url = f"{config.api_base_url}{endpoint}"
        elif endpoint.startswith("http"):
            url = endpoint
        else:
            # 端点名称，从配置获取
            url = config.get_api_url(endpoint)
        
        try:
            response = self.session.request(
                method=method, url=url, params=params, data=data,
                timeout=10, verify=False, **kwargs
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": True, "message": str(e)}
    
    def get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        return self._request("GET", endpoint, params=params)
    
    def get_raw(self, endpoint: str, params: Optional[list] = None) -> dict:
        """GET 请求，支持重复参数名（如 createTime）
        
        Args:
            endpoint: 端点名称或完整路径
            params: 参数列表，格式为 [(key, value), ...]
        """
        from urllib.parse import quote
        
        # 判断是端点名称还是完整路径
        if endpoint.startswith("http"):
            url = endpoint
        elif "/" in endpoint:
            # 已经是路径，直接拼接
            if not endpoint.startswith("/"):
                endpoint = "/" + endpoint
            url = f"{config.api_base_url}{endpoint}"
        else:
            # 端点名称，从配置获取
            url = config.get_api_url(endpoint)
        
        try:
            # 构建带参数的 URL（对参数值进行 URL 编码）
            if params:
                param_parts = []
                for k, v in params:
                    if v is not None and v != "":
                        # 对参数值进行 URL 编码
                        encoded_v = quote(str(v), safe='')
                        param_parts.append(f"{k}={encoded_v}")
                if param_parts:
                    url = f"{url}?{'&'.join(param_parts)}"
            
            response = self.session.request(
                method="GET", url=url,
                timeout=30, verify=False
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": True, "message": str(e)}
    
    def post(self, endpoint: str, data: Optional[dict] = None, params: Optional[dict] = None) -> dict:
        return self._request("POST", endpoint, params=params, data=data)
    
    def post_json(self, endpoint: str, json_data: Optional[dict] = None, params: Optional[dict] = None) -> dict:
        """POST 请求，使用 JSON 格式"""
        # 判断是端点名称还是完整路径
        if endpoint.startswith("/"):
            url = f"{config.api_base_url}{endpoint}"
        elif endpoint.startswith("http"):
            url = endpoint
        else:
            url = config.get_api_url(endpoint)
        
        try:
            response = self.session.request(
                method="POST", url=url, params=params, json=json_data,
                timeout=10, verify=False
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": True, "message": str(e)}
    
    def post_form(self, endpoint: str, data: Optional[dict] = None, params: Optional[dict] = None) -> dict:
        """POST 请求，使用 application/x-www-form-urlencoded 格式"""
        # 判断是端点名称还是完整路径
        if endpoint.startswith("/"):
            url = f"{config.api_base_url}{endpoint}"
        elif endpoint.startswith("http"):
            url = endpoint
        else:
            url = config.get_api_url(endpoint)
        
        try:
            response = self.session.request(
                method="POST", url=url, params=params, data=data,
                timeout=10, verify=False,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": True, "message": str(e)}


api_client = APIClient()