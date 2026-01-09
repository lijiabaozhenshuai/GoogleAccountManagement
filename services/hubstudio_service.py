# -*- coding: utf-8 -*-
"""
HubStudio 浏览器服务
"""
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from config import HUBSTUDIO_CONFIG


def get_hubstudio_headers():
    """获取HubStudio API请求头"""
    return {
        "Content-Type": "application/json",
        "app-id": HUBSTUDIO_CONFIG["app_id"],
        "app-secret": HUBSTUDIO_CONFIG["app_secret"]
    }


def check_api_status():
    """检查HubStudio API连接状态"""
    try:
        response = requests.post(
            f"{HUBSTUDIO_CONFIG['base_url']}/api/v1/group/list",
            headers=get_hubstudio_headers(),
            timeout=5
        )
        if response.status_code == 200:
            result = response.json()
            return result.get("code") == 0
        return False
    except Exception:
        return False


def get_groups():
    """获取HubStudio分组列表"""
    try:
        response = requests.post(
            f"{HUBSTUDIO_CONFIG['base_url']}/api/v1/group/list",
            headers=get_hubstudio_headers(),
            timeout=10
        )
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                return result.get("data", [])
        return []
    except Exception:
        return []


def get_browsers(page=1, page_size=20, search='', group_code=''):
    """获取HubStudio浏览器窗口列表"""
    try:
        request_data = {
            "page": page,
            "limit": page_size
        }
        
        if search:
            request_data["containerName"] = search
        if group_code:
            request_data["tagCode"] = group_code
        
        response = requests.post(
            f"{HUBSTUDIO_CONFIG['base_url']}/api/v1/env/list",
            headers=get_hubstudio_headers(),
            json=request_data,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                data = result.get("data", {})
                return {
                    'browsers': data.get("list", []),
                    'total': data.get("total", 0)
                }
        return {'browsers': [], 'total': 0}
    except Exception:
        return {'browsers': [], 'total': 0}


def open_browser(container_code, is_headless=False):
    """打开HubStudio浏览器并返回WebDriver"""
    try:
        request_data = {
            "containerCode": container_code,
            "isHeadless": is_headless,
            "isWebDriverReadOnlyMode": False
        }
        
        response = requests.post(
            f"{HUBSTUDIO_CONFIG['base_url']}/api/v1/browser/start",
            headers=get_hubstudio_headers(),
            json=request_data,
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"API请求失败: HTTP {response.status_code}")
        
        data = response.json()
        if data.get("code") != 0:
            raise Exception(f"启动浏览器失败: {data.get('msg', '未知错误')}")
        
        debug_info = data.get("data", {})
        debugging_port = debug_info.get("debuggingPort")
        webdriver_path = debug_info.get("webdriver")
        
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_experimental_option("debuggerAddress", f"localhost:{debugging_port}")
        
        chrome_service = Service(webdriver_path)
        driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
        return driver
        
    except Exception as e:
        print(f"打开浏览器失败: {e}")
        return None


def close_browser(container_code):
    """关闭HubStudio浏览器"""
    try:
        response = requests.post(
            f"{HUBSTUDIO_CONFIG['base_url']}/api/v1/browser/stop",
            headers=get_hubstudio_headers(),
            json={"containerCode": container_code},
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"关闭浏览器失败: {e}")
        return False


def create_environment(env_name, group_name, proxy_server, proxy_port, proxy_account, proxy_password, core_version):
    """创建HubStudio浏览器环境"""
    try:
        request_data = {
            "containerName": env_name,
            "tagName": group_name,
            "asDynamicType": 1,
            "proxyTypeName": "Socks5",
            "proxyServer": proxy_server,
            "proxyPort": proxy_port,
            "proxyAccount": proxy_account,
            "proxyPassword": proxy_password,
            "coreVersion": core_version
        }
        
        response = requests.post(
            f"{HUBSTUDIO_CONFIG['base_url']}/api/v1/env/create",
            headers=get_hubstudio_headers(),
            json=request_data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                return True, result.get("data", {}).get("containerCode", "")
            else:
                return False, result.get('msg', '未知错误')
        else:
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)

