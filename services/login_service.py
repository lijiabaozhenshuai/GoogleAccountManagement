# -*- coding: utf-8 -*-
"""
自动登录服务
"""
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from models import db, Account, LoginLog, BrowserEnv
from services import hubstudio_service


def add_login_log(account_id, browser_env_id, action, status, message):
    """添加登录日志"""
    log = LoginLog(
        account_id=account_id,
        browser_env_id=browser_env_id,
        action=action,
        status=status,
        message=message
    )
    db.session.add(log)
    db.session.commit()
    return log


def get_available_browser_env():
    """获取一个可用的浏览器环境"""
    # 首先从本地数据库查找未使用的环境
    local_env = BrowserEnv.query.filter_by(status=False).first()
    if local_env:
        return local_env
    
    # 如果本地没有，从HubStudio获取并同步到本地
    try:
        result = hubstudio_service.get_browsers(page=1, page_size=100)
        browsers = result.get('browsers', [])
        for browser in browsers:
            container_code = browser.get("containerCode")
            existing = BrowserEnv.query.filter_by(container_code=container_code).first()
            if not existing:
                new_env = BrowserEnv(
                    container_code=container_code,
                    container_name=browser.get("containerName", ""),
                    status=False
                )
                db.session.add(new_env)
                db.session.commit()
                return new_env
    except Exception as e:
        print(f"获取浏览器环境失败: {e}")
    
    return None


def detect_login_page_state(driver):
    """检测登录页面的当前状态"""
    try:
        current_url = driver.current_url
        
        # 检查是否已经登录成功
        if "myaccount.google.com" in current_url:
            return "logged_in"
        
        # 检查是否在登录页面
        if "accounts.google.com" in current_url:
            # 检查是否需要输入邮箱
            try:
                driver.find_element(By.ID, "identifierId")
                return "need_email"
            except:
                pass
            
            # 检查是否需要输入密码
            try:
                driver.find_element(By.NAME, "Passwd")
                return "need_password"
            except:
                pass
            
            # 检查是否密码错误
            try:
                error_element = driver.find_element(By.XPATH, "//span[contains(text(), 'Wrong password') or contains(text(), '密码不正确')]")
                if error_element:
                    return "password_error"
            except:
                pass
            
            # 检查是否需要2FA
            if "challenge" in current_url or "2step" in current_url:
                return "need_2fa"
            
            # 检查是否需要验证手机号
            try:
                phone_element = driver.find_element(By.XPATH, "//span[contains(text(), 'Verify your phone number') or contains(text(), '验证您的电话号码')]")
                if phone_element:
                    return "need_phone"
            except:
                pass
            
            # 检查账号是否被禁用
            try:
                disabled_element = driver.find_element(By.XPATH, "//span[contains(text(), 'disabled') or contains(text(), '已停用')]")
                if disabled_element:
                    return "disabled"
            except:
                pass
        
        return "unknown"
    except Exception as e:
        print(f"检测页面状态失败: {e}")
        return "unknown"


def perform_login(driver, account, password):
    """执行登录操作"""
    try:
        # 导航到Google账号页面
        driver.get('https://accounts.google.com/')
        time.sleep(3)
        
        # 检查当前状态
        state = detect_login_page_state(driver)
        
        if state == "logged_in":
            return "success", "已登录状态"
        
        # 输入邮箱
        if state == "need_email":
            try:
                email_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "identifierId"))
                )
                email_input.clear()
                email_input.send_keys(account)
                
                # 点击下一步
                next_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "identifierNext"))
                )
                next_button.click()
                time.sleep(3)
            except Exception as e:
                return "failed", f"输入邮箱失败: {e}"
        
        # 重新检测状态
        state = detect_login_page_state(driver)
        
        # 输入密码
        if state == "need_password":
            try:
                password_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "Passwd"))
                )
                password_input.clear()
                password_input.send_keys(password)
                
                # 点击下一步
                next_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "passwordNext"))
                )
                next_button.click()
                time.sleep(5)
            except Exception as e:
                return "failed", f"输入密码失败: {e}"
        
        # 最终检测状态
        final_state = detect_login_page_state(driver)
        
        if final_state == "logged_in":
            return "success", "登录成功"
        elif final_state == "password_error":
            return "password_error", "密码错误"
        elif final_state == "need_phone":
            return "need_phone", "需要绑定手机号"
        elif final_state == "need_2fa":
            return "need_2fa", "需要2FA验证"
        elif final_state == "disabled":
            return "disabled", "账号被禁用"
        else:
            return "failed", f"登录状态未知: {final_state}"
        
    except Exception as e:
        return "failed", f"登录过程发生错误: {e}"


def auto_login_task(app, account_id):
    """自动登录任务（在后台线程中执行）"""
    with app.app_context():
        account = Account.query.get(account_id)
        if not account:
            return
        
        # 更新状态为登录中
        account.login_status = 'logging'
        db.session.commit()
        add_login_log(account_id, None, 'auto_login', 'start', '开始自动登录')
        
        # 获取可用的浏览器环境
        browser_env = get_available_browser_env()
        if not browser_env:
            account.login_status = 'failed'
            db.session.commit()
            add_login_log(account_id, None, 'auto_login', 'failed', '没有可用的浏览器环境')
            return
        
        # 标记环境为已使用
        browser_env.status = True
        browser_env.account_id = account_id
        account.browser_env_id = browser_env.container_code
        db.session.commit()
        add_login_log(account_id, browser_env.container_code, 'auto_login', 'info', f'分配浏览器环境: {browser_env.container_name}')
        
        driver = None
        try:
            # 打开浏览器
            driver = hubstudio_service.open_browser(browser_env.container_code)
            if not driver:
                account.login_status = 'failed'
                db.session.commit()
                add_login_log(account_id, browser_env.container_code, 'auto_login', 'failed', '无法打开浏览器')
                return
            
            add_login_log(account_id, browser_env.container_code, 'auto_login', 'info', '浏览器已打开，开始登录')
            
            # 执行登录
            status, message = perform_login(driver, account.account, account.password)
            
            # 更新账号状态
            account.login_status = status
            account.status = (status == 'success')
            db.session.commit()
            
            add_login_log(account_id, browser_env.container_code, 'auto_login', status, message)
            
        except Exception as e:
            account.login_status = 'failed'
            db.session.commit()
            add_login_log(account_id, browser_env.container_code, 'auto_login', 'failed', f'登录过程发生异常: {str(e)}')
        
        finally:
            # 关闭浏览器
            if driver:
                try:
                    driver.quit()
                except:
                    pass
                hubstudio_service.close_browser(browser_env.container_code)


def sync_browser_envs():
    """同步HubStudio浏览器环境到本地"""
    try:
        result = hubstudio_service.get_browsers(page=1, page_size=500)
        browsers = result.get('browsers', [])
        synced_count = 0
        
        for browser in browsers:
            container_code = browser.get("containerCode")
            existing = BrowserEnv.query.filter_by(container_code=container_code).first()
            if not existing:
                new_env = BrowserEnv(
                    container_code=container_code,
                    container_name=browser.get("containerName", ""),
                    status=False
                )
                db.session.add(new_env)
                synced_count += 1
            else:
                existing.container_name = browser.get("containerName", "")
        
        db.session.commit()
        return synced_count, len(browsers)
        
    except Exception as e:
        raise e

