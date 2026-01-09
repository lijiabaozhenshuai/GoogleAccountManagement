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
        print(f"[状态检测] 当前 URL: {current_url}")
        
        # 优先通过 URL 判断（最可靠的方法）
        if "myaccount.google.com" in current_url:
            return "logged_in"
        
        # 检查是否是密码输入页面（通过 URL 判断）
        if "/signin/challenge/pwd" in current_url or "/challenge/pwd" in current_url:
            try:
                password_input = driver.find_element(By.NAME, "Passwd")
                if password_input:
                    print(f"[状态检测] 检测到密码页面")
                    return "need_password"
            except:
                pass
        
        # 检查是否需要验证手机号
        if "challenge/iap" in current_url or "speedbump/idvreenable" in current_url or "challenge/dp" in current_url:
            print(f"[状态检测] 检测到手机验证页面")
            return "need_phone"
        
        # 检查是否需要2FA
        if "challenge/totp" in current_url or "challenge/ipp" in current_url or "2step" in current_url:
            print(f"[状态检测] 检测到2FA验证页面")
            return "need_2fa"
        
        # 检查验证码页面
        if "challenge/recaptcha" in current_url or "recaptcha" in current_url or "captcha" in current_url:
            print(f"[状态检测] 检测到验证码页面")
            return "need_captcha"
        
        # 检查账号被禁用
        if "disabled" in current_url:
            print(f"[状态检测] 检测到账号被禁用")
            return "disabled"
        
        # 检查是否是 Passkey 注册页面
        if "passkeyenrollment" in current_url or "speedbump/passkey" in current_url:
            print(f"[状态检测] 检测到 Passkey 注册页面")
            return "passkey_enrollment"
        
        # 如果 URL 判断不明确，再通过页面元素判断
        if "accounts.google.com" in current_url:
            # 检查是否是 "Verify it's you" 验证页面
            try:
                verify_title = driver.find_element(By.XPATH, "//h1[contains(text(), \"Verify it's you\") or contains(text(), '验证您的身份')]")
                if verify_title and verify_title.is_displayed():
                    print(f"[状态检测] 检测到 'Verify it's you' 验证页面")
                    return "verify_identity"
            except:
                pass
            
            # 检查是否密码错误
            try:
                error_element = driver.find_element(By.XPATH, "//span[contains(text(), 'Wrong password') or contains(text(), '密码不正确')]")
                if error_element:
                    return "password_error"
            except:
                pass
            
            # 检查是否需要输入密码（元素判断）
            try:
                password_input = driver.find_element(By.NAME, "Passwd")
                if password_input:
                    return "need_password"
            except:
                pass
            
            # 最后检查是否需要输入邮箱
            try:
                driver.find_element(By.ID, "identifierId")
                return "need_email"
            except:
                pass
        
        return "unknown"
    except Exception as e:
        print(f"[状态检测错误] {e}")
        import traceback
        traceback.print_exc()
        return "unknown"


def handle_passkey_enrollment_page(driver):
    """处理 Passkey 注册页面，点击 Not now 跳过"""
    try:
        print(f"[Passkey注册] 检测到 Passkey 注册页面，准备点击 Not now...")
        
        # 等待页面加载
        time.sleep(2)
        
        # 查找并点击 "Not now" 按钮
        try:
            # 多种方式尝试定位 "Not now" 按钮
            not_now_button = None
            
            try:
                # 方式1: 通过文本内容查找
                not_now_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Not now') or contains(text(), '暂时不用')]"))
                )
            except:
                try:
                    # 方式2: 通过 div 文本查找
                    not_now_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Not now') or contains(text(), '暂时不用')]"))
                    )
                except:
                    # 方式3: 通过任何包含 "not" 的按钮
                    not_now_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//*[contains(translate(text(), 'NOT', 'not'), 'not now')]"))
                    )
            
            if not_now_button:
                print(f"[Passkey注册] 找到 'Not now' 按钮，准备点击...")
                # 滚动到按钮可见
                driver.execute_script("arguments[0].scrollIntoView(true);", not_now_button)
                time.sleep(1)
                # 点击按钮
                not_now_button.click()
                print(f"[Passkey注册] 已点击 'Not now' 按钮")
                
                # 等待页面跳转
                time.sleep(3)
                
                # 检查结果
                current_url = driver.current_url
                print(f"[Passkey注册] 跳过后 URL: {current_url}")
                
                if "myaccount.google.com" in current_url:
                    print(f"[Passkey注册] 跳过成功，已登录")
                    return "success"
                else:
                    print(f"[Passkey注册] 跳过完成，继续后续流程")
                    return "continue"
            else:
                print(f"[Passkey注册错误] 未找到 'Not now' 按钮")
                return "button_not_found"
                
        except Exception as e:
            error_msg = f"点击 'Not now' 按钮失败: {str(e)}"
            print(f"[Passkey注册错误] {error_msg}")
            import traceback
            traceback.print_exc()
            return "click_failed"
            
    except Exception as e:
        error_msg = f"处理 Passkey 注册页面失败: {str(e)}"
        print(f"[Passkey注册错误] {error_msg}")
        import traceback
        traceback.print_exc()
        return "error"


def handle_verify_identity_page(driver, backup_email):
    """处理 'Verify it's you' 验证身份页面"""
    try:
        print(f"[验证身份] 开始处理 'Verify it's you' 页面...")
        
        if not backup_email:
            print(f"[验证身份错误] 账号没有设置辅助邮箱")
            return "no_backup_email"
        
        # 等待页面加载
        time.sleep(2)
        
        # 查找并点击 "Confirm your recovery email" 选项
        try:
            print(f"[验证身份] 查找 'Confirm your recovery email' 选项...")
            # 多种方式尝试定位这个选项
            recovery_email_option = None
            
            try:
                # 方式1: 通过文本内容查找
                recovery_email_option = driver.find_element(By.XPATH, 
                    "//div[contains(text(), 'Confirm your recovery email') or contains(text(), '确认您的恢复电子邮件地址')]")
            except:
                try:
                    # 方式2: 通过图标和文本组合查找
                    recovery_email_option = driver.find_element(By.XPATH,
                        "//div[contains(@class, 'JDAKTe') and .//div[contains(text(), 'recovery email')]]")
                except:
                    # 方式3: 查找包含 recovery 的任何选项
                    recovery_email_option = driver.find_element(By.XPATH,
                        "//*[contains(text(), 'recovery') and contains(text(), 'email')]")
            
            if recovery_email_option:
                print(f"[验证身份] 找到 'Confirm your recovery email' 选项，准备点击...")
                # 滚动到元素可见
                driver.execute_script("arguments[0].scrollIntoView(true);", recovery_email_option)
                time.sleep(1)
                # 点击选项
                recovery_email_option.click()
                print(f"[验证身份] 已点击 'Confirm your recovery email'")
                time.sleep(3)
            else:
                print(f"[验证身份错误] 未找到 'Confirm your recovery email' 选项")
                return "option_not_found"
                
        except Exception as e:
            error_msg = f"点击 'Confirm your recovery email' 失败: {str(e)}"
            print(f"[验证身份错误] {error_msg}")
            import traceback
            traceback.print_exc()
            return "click_failed"
        
        # 输入辅助邮箱
        try:
            print(f"[验证身份] 等待邮箱输入框...")
            email_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='email']"))
            )
            email_input.clear()
            email_input.send_keys(backup_email)
            print(f"[验证身份] 已输入辅助邮箱: {backup_email}")
            
            # 点击下一步
            print(f"[验证身份] 查找下一步按钮...")
            next_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@type='button']//span[contains(text(), 'Next') or contains(text(), '下一步')]"))
            )
            next_button.click()
            print(f"[验证身份] 已点击下一步")
            
            # 等待页面跳转
            time.sleep(5)
            
            # 检查结果
            current_url = driver.current_url
            print(f"[验证身份] 验证后 URL: {current_url}")
            
            if "myaccount.google.com" in current_url:
                print(f"[验证身份] 验证成功，已登录")
                return "success"
            else:
                print(f"[验证身份] 验证完成，继续后续流程")
                return "continue"
                
        except Exception as e:
            error_msg = f"输入辅助邮箱失败: {str(e)}"
            print(f"[验证身份错误] {error_msg}")
            import traceback
            traceback.print_exc()
            return "input_failed"
            
    except Exception as e:
        error_msg = f"处理验证身份页面失败: {str(e)}"
        print(f"[验证身份错误] {error_msg}")
        import traceback
        traceback.print_exc()
        return "error"


def handle_password_page(driver, password):
    """处理密码页面"""
    try:
        print(f"[密码页面] 开始处理密码输入...")
        # 等待并输入密码
        password_input = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, "Passwd"))
        )
        password_input.clear()
        password_input.send_keys(password)
        print(f"[密码页面] 已输入密码")
        
        # 点击下一步按钮
        next_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "passwordNext"))
        )
        next_button.click()
        print(f"[密码页面] 已点击下一步")
        
        # 等待页面加载
        time.sleep(5)
        
        # 记录当前URL
        current_url = driver.current_url
        print(f"[密码页面] 密码处理后 URL: {current_url}")
        
        # 通过URL判断下一步状态
        if "myaccount.google.com" in current_url:
            print(f"[密码页面] 检测到已登录状态")
            return "success"
        elif "speedbump/idvreenable" in current_url or "challenge/dp" in current_url or "challenge/iap" in current_url:
            print(f"[密码页面] 检测到手机验证页面")
            return "need_phone"
        elif "2step" in current_url or "challenge/totp" in current_url or "challenge/ipp" in current_url:
            print(f"[密码页面] 检测到二次验证页面")
            return "need_2fa"
        elif "disabled" in current_url:
            print(f"[密码页面] 检测到账号被禁用")
            return "disabled"
        
        # 检查是否有密码错误提示
        try:
            error_element = driver.find_element(By.XPATH, "//span[contains(text(), 'Wrong password') or contains(text(), '密码不正确')]")
            if error_element and error_element.is_displayed():
                print(f"[密码页面] 检测到密码错误")
                return "password_error"
        except:
            pass
        
        print(f"[密码页面] 未知状态，URL: {current_url}")
        return "unknown"
        
    except Exception as e:
        error_msg = f"密码页面处理失败: {str(e)}"
        print(f"[密码页面错误] {error_msg}")
        import traceback
        traceback.print_exc()
        return "error"


def perform_login(driver, account, password, backup_email=None):
    """执行登录操作（使用状态机模式）"""
    try:
        # 导航到Google账号页面
        print(f"[登录] 正在访问 Google 账号页面...")
        driver.get('https://accounts.google.com/')
        time.sleep(3)
        
        # 循环处理登录流程（最多5次状态转换）
        max_attempts = 5
        for attempt in range(max_attempts):
            print(f"\n[登录] ===== 第 {attempt + 1} 次状态检测 =====")
            current_state = detect_login_page_state(driver)
            print(f"[登录] 当前状态: {current_state}")
            
            if current_state == "logged_in":
                return "success", "已登录状态"
            
            elif current_state == "need_email":
                # 处理邮箱输入页面
                try:
                    print(f"[登录] 开始输入邮箱: {account}")
                    email_input = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "identifierId"))
                    )
                    email_input.clear()
                    email_input.send_keys(account)
                    
                    # 点击下一步
                    print(f"[登录] 点击邮箱下一步按钮")
                    next_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.ID, "identifierNext"))
                    )
                    next_button.click()
                    
                    # 等待页面跳转
                    print(f"[登录] 等待页面跳转...")
                    time.sleep(5)
                    
                    # 继续下一次循环检测
                    continue
                    
                except Exception as e:
                    error_msg = f"输入邮箱失败: {str(e)}"
                    print(f"[登录错误] {error_msg}")
                    return "failed", error_msg
            
            elif current_state == "need_password":
                # 处理密码页面
                status = handle_password_page(driver, password)
                
                if status == "success":
                    return "success", "登录成功"
                elif status == "need_phone":
                    return "need_phone", "需要绑定手机号"
                elif status == "need_2fa":
                    return "need_2fa", "需要2FA验证"
                elif status == "disabled":
                    return "disabled", "账号被禁用"
                elif status == "password_error":
                    return "password_error", "密码错误"
                elif status == "error":
                    return "failed", "密码处理错误"
                else:
                    # 未知状态，继续循环检测
                    print(f"[登录] 密码处理后返回未知状态，继续检测...")
                    time.sleep(2)
                    continue
            
            elif current_state == "verify_identity":
                # 处理 "Verify it's you" 验证身份页面
                status = handle_verify_identity_page(driver, backup_email)
                
                if status == "success":
                    return "success", "验证成功，已登录"
                elif status == "continue":
                    # 继续下一轮检测
                    print(f"[登录] 验证身份完成，继续检测后续状态...")
                    time.sleep(2)
                    continue
                elif status == "no_backup_email":
                    return "failed", "需要辅助邮箱验证，但账号未设置辅助邮箱"
                else:
                    return "failed", f"验证身份失败: {status}"
            
            elif current_state == "passkey_enrollment":
                # 处理 Passkey 注册页面
                status = handle_passkey_enrollment_page(driver)
                
                if status == "success":
                    return "success", "Passkey 跳过成功，已登录"
                elif status == "continue":
                    # 继续下一轮检测
                    print(f"[登录] Passkey 跳过完成，继续检测后续状态...")
                    time.sleep(2)
                    continue
                else:
                    return "failed", f"Passkey 页面处理失败: {status}"
            
            elif current_state == "need_phone":
                return "need_phone", "需要绑定手机号"
            
            elif current_state == "need_2fa":
                return "need_2fa", "需要2FA验证"
            
            elif current_state == "disabled":
                return "disabled", "账号被禁用"
            
            elif current_state == "need_captcha":
                return "failed", "需要验证码"
            
            elif current_state == "password_error":
                return "password_error", "密码错误"
            
            else:
                # 未知状态，等待后继续
                print(f"[登录] 未知状态，等待后重新检测...")
                time.sleep(3)
                continue
        
        # 超过最大尝试次数
        final_url = driver.current_url
        return "failed", f"登录流程超过最大尝试次数，最终 URL: {final_url}"
        
    except Exception as e:
        error_msg = f"登录过程发生错误: {str(e)}"
        print(f"[登录异常] {error_msg}")
        import traceback
        traceback.print_exc()
        return "failed", error_msg


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
        
        # 优先使用账号已绑定的浏览器环境
        browser_env = None
        if account.browser_env_id:
            browser_env = BrowserEnv.query.filter_by(container_code=account.browser_env_id).first()
            if browser_env:
                add_login_log(account_id, browser_env.container_code, 'auto_login', 'info', f'使用已绑定的浏览器环境: {browser_env.container_name}')
        
        # 如果没有绑定或绑定的环境不存在，获取新的可用环境
        if not browser_env:
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
            print(f"[自动登录] 正在打开浏览器环境: {browser_env.container_code}")
            try:
                driver = hubstudio_service.open_browser(browser_env.container_code)
            except Exception as open_error:
                error_msg = f'打开浏览器异常: {str(open_error)}'
                print(f"[自动登录错误] {error_msg}")
                account.login_status = 'failed'
                db.session.commit()
                add_login_log(account_id, browser_env.container_code, 'auto_login', 'failed', error_msg)
                return
            
            if not driver:
                error_msg = '无法打开浏览器，请检查: 1) HubStudio 是否运行 2) 浏览器环境是否存在 3) 网络连接是否正常'
                account.login_status = 'failed'
                db.session.commit()
                add_login_log(account_id, browser_env.container_code, 'auto_login', 'failed', error_msg)
                print(f"[自动登录错误] {error_msg}")
                return
            
            print(f"[自动登录] 浏览器已打开，开始登录")
            add_login_log(account_id, browser_env.container_code, 'auto_login', 'info', '浏览器已打开，开始登录')
            
            # 执行登录（传递辅助邮箱）
            status, message = perform_login(driver, account.account, account.password, account.backup_email)
            print(f"[自动登录] 登录结果 - 状态: {status}, 消息: {message}")
            
            # 更新账号状态
            account.login_status = status
            account.status = (status == 'success')
            db.session.commit()
            
            add_login_log(account_id, browser_env.container_code, 'auto_login', status, message)
            
        except Exception as e:
            error_msg = f'登录过程发生异常: {str(e)}'
            print(f"[自动登录异常] {error_msg}")
            import traceback
            traceback.print_exc()
            account.login_status = 'failed'
            db.session.commit()
            add_login_log(account_id, browser_env.container_code, 'auto_login', 'failed', error_msg)
        
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

