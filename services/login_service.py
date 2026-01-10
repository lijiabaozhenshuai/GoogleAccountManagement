# -*- coding: utf-8 -*-
"""
自动登录服务
"""
import time
import json
import re
import requests
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from models import db, Account, LoginLog, BrowserEnv, Phone
from services import hubstudio_service
from config import CAPTCHA_CONFIG


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
        try:
            current_url = driver.current_url
            print(f"[状态检测] 当前 URL: {current_url}")
        except Exception as e:
            print(f"[状态检测错误] 无法获取URL，浏览器可能已关闭: {str(e)}")
            raise Exception("浏览器连接失败")
        
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
        
        # 检查是否是"Verify it's you"页面 - 需要直接点击Next按钮的
        if "confirmidentifier" in current_url or "signin/v2/challenge" in current_url or "challenge/selection" in current_url:
            print(f"[状态检测] URL包含Verify关键词，检查页面元素...")
            try:
                # 检查是否有"Verify it's you"标题
                verify_title = driver.find_element(By.XPATH, "//h1[contains(text(), \"Verify it's you\") or contains(text(), '验证您的身份')]")
                if verify_title and verify_title.is_displayed():
                    print(f"[状态检测] 找到 'Verify it's you' 标题")
                    # 检查是否有Next按钮（多种方式检测）
                    next_button_found = False
                    try:
                        # 方式1: 通过jsname属性
                        next_button = driver.find_element(By.XPATH, "//button[@jsname='LgbsSe']")
                        next_button_found = True
                        print(f"[状态检测] 通过jsname找到Next按钮")
                    except:
                        try:
                            # 方式2: 通过span的jsname和文本
                            next_button = driver.find_element(By.XPATH, "//span[@jsname='V67aGc' and contains(text(), 'Next')]")
                            next_button_found = True
                            print(f"[状态检测] 通过span jsname找到Next按钮")
                        except:
                            try:
                                # 方式3: 通过普通文本查找
                                next_button = driver.find_element(By.XPATH, "//button[@type='button']//span[contains(text(), 'Next') or contains(text(), '下一步')]")
                                next_button_found = True
                                print(f"[状态检测] 通过文本找到Next按钮")
                            except:
                                print(f"[状态检测警告] 有Verify标题但未找到Next按钮")
                                pass
                    
                    if next_button_found:
                        print(f"[状态检测] ✅ 确认为需要点击Next的 'Verify it's you' 页面")
                        return "verify_click_next"
                else:
                    print(f"[状态检测] Verify标题不可见")
            except Exception as e:
                print(f"[状态检测] 未找到Verify标题，尝试通过Next按钮判断: {str(e)}")
                # 即使没有标题，如果URL明确是confirmidentifier且有Next按钮，也应该点击
                try:
                    next_button = driver.find_element(By.XPATH, "//button[@jsname='LgbsSe']")
                    if next_button:
                        print(f"[状态检测] ✅ 通过URL+Next按钮确认为Verify页面")
                        return "verify_click_next"
                except:
                    print(f"[状态检测] 也未找到Next按钮")
                    pass
        
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
            # 检查是否是 "Verify it's you" 页面（两种类型）
            try:
                verify_title = driver.find_element(By.XPATH, "//h1[contains(text(), \"Verify it's you\") or contains(text(), '验证您的身份')]")
                if verify_title and verify_title.is_displayed():
                    # 检查是否有Next按钮（需要直接点击的类型）
                    try:
                        next_button = driver.find_element(By.XPATH, "//button[@jsname='LgbsSe']")
                        if next_button:
                            print(f"[状态检测] 检测到需要点击Next的 'Verify it's you' 页面")
                            return "verify_click_next"
                    except:
                        pass
                    
                    # 如果没有Next按钮，可能是需要选择验证方式的页面
                    print(f"[状态检测] 检测到 'Verify it's you' 验证身份页面")
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
            
            # 最后检查是否需要输入邮箱（必须确保不是Verify it's you页面）
            try:
                # 先确认不是"Verify it's you"页面
                try:
                    verify_title = driver.find_element(By.XPATH, "//h1[contains(text(), \"Verify it's you\") or contains(text(), '验证您的身份')]")
                    if verify_title and verify_title.is_displayed():
                        # 如果有"Verify it's you"标题，不应该输入邮箱
                        print(f"[状态检测] 检测到Verify it's you标题，但未找到Next按钮，返回verify_click_next")
                        return "verify_click_next"
                except:
                    pass
                
                # 确认有identifierId元素，并且该元素是可编辑的
                email_input = driver.find_element(By.ID, "identifierId")
                if email_input:
                    # 检查元素是否可编辑（不是readonly或disabled）
                    is_readonly = email_input.get_attribute("readonly")
                    is_disabled = email_input.get_attribute("disabled")
                    is_displayed = email_input.is_displayed()
                    
                    # 只有当元素显示且可编辑时才认为需要输入邮箱
                    if is_displayed and not is_readonly and not is_disabled:
                        print(f"[状态检测] 检测到可编辑的邮箱输入框")
                        return "need_email"
                    else:
                        print(f"[状态检测] 发现邮箱元素但不可编辑 (readonly={is_readonly}, disabled={is_disabled}, displayed={is_displayed})")
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


def handle_verify_click_next_page(driver):
    """处理 'Verify it's you' 页面 - 直接点击Next按钮"""
    try:
        print(f"[验证身份] 检测到需要点击Next的 'Verify it's you' 页面...")
        
        # 等待页面加载
        time.sleep(2)
        
        # 查找并点击 "Next" 按钮
        try:
            print(f"[验证身份] 查找 'Next' 按钮...")
            next_button = None
            
            # 方式1: 通过jsname属性查找按钮
            try:
                next_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@jsname='LgbsSe']"))
                )
                print(f"[验证身份] 通过jsname找到 'Next' 按钮")
            except:
                # 方式2: 通过span标签的jsname和文本查找
                try:
                    next_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//span[@jsname='V67aGc' and contains(text(), 'Next')]"))
                    )
                    print(f"[验证身份] 通过span的jsname找到 'Next' 按钮")
                except:
                    # 方式3: 通过button元素包含Next文本的span
                    try:
                        next_button = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, "//button[@type='button']//span[contains(text(), 'Next') or contains(text(), '下一步')]"))
                        )
                        print(f"[验证身份] 通过文本找到 'Next' 按钮")
                    except:
                        # 方式4: 通过包含特定class的按钮
                        next_button = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'VfPpkd-LgbsSe')]//span[contains(text(), 'Next')]"))
                        )
                        print(f"[验证身份] 通过class找到 'Next' 按钮")
            
            if next_button:
                print(f"[验证身份] 找到 'Next' 按钮，准备点击...")
                # 滚动到按钮可见
                driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                time.sleep(1)
                
                # 尝试多种点击方式
                try:
                    # 先尝试普通点击
                    next_button.click()
                    print(f"[验证身份] 已点击 'Next' 按钮（普通点击）")
                except:
                    try:
                        # 如果普通点击失败，使用JavaScript点击
                        driver.execute_script("arguments[0].click();", next_button)
                        print(f"[验证身份] 已点击 'Next' 按钮（JS点击）")
                    except Exception as click_error:
                        print(f"[验证身份错误] 点击失败: {str(click_error)}")
                        return "click_failed"
                
                # 等待页面跳转
                time.sleep(5)
                
                # 检查结果
                current_url = driver.current_url
                print(f"[验证身份] 点击Next后 URL: {current_url}")
                
                if "myaccount.google.com" in current_url:
                    print(f"[验证身份] 验证成功，已登录")
                    return "success"
                elif "recaptcha" in current_url or "captcha" in current_url:
                    print(f"[验证身份] 进入人机验证页面")
                    return "need_captcha"
                else:
                    print(f"[验证身份] 点击完成，继续后续流程")
                    return "continue"
            else:
                print(f"[验证身份错误] 未找到 'Next' 按钮")
                return "button_not_found"
                
        except Exception as e:
            error_msg = f"查找或点击 'Next' 按钮失败: {str(e)}"
            print(f"[验证身份错误] {error_msg}")
            import traceback
            traceback.print_exc()
            return "click_failed"
            
    except Exception as e:
        error_msg = f"处理验证身份页面失败: {str(e)}"
        print(f"[验证身份错误] {error_msg}")
        import traceback
        traceback.print_exc()
        return "error"


def find_callback_path(driver):
    """查找reCAPTCHA回调路径"""
    print(f"[验证码] 查找reCAPTCHA回调路径...")
    script = """
    function findRecaptchaClients() {
        if (typeof (___grecaptcha_cfg) !== 'undefined') {
            return Object.entries(___grecaptcha_cfg.clients).map(([cid, client]) => {
                const data = { id: cid, version: cid >= 10000 ? 'V3' : 'V2' };
                const objects = Object.entries(client).filter(([_, value]) => value && typeof value === 'object');

                objects.forEach(([toplevelKey, toplevel]) => {
                    if (typeof toplevel === 'object' && toplevel instanceof HTMLElement && toplevel['tagName'] === 'DIV'){
                        data.pageurl = toplevel.baseURI;
                    }

                    const found = Object.entries(toplevel).find(([_, value]) => (
                        value && typeof value === 'object' && 'sitekey' in value && 'size' in value
                    ));

                    if (found) {
                        const [sublevelKey, sublevel] = found;
                        data.sitekey = sublevel.sitekey;
                        const callbackKey = data.version === 'V2' ? 'callback' : 'promise-callback';
                        const callback = sublevel[callbackKey];
                        data.function = callback || {};
                        data.clientId = cid;
                        data.toplevelKey = toplevelKey;
                        data.sublevelKey = sublevelKey;
                        data.callbackKey = callbackKey;
                    }
                });
                return data;
            });
        }
        return [];
    }
    return findRecaptchaClients();
    """

    max_retries = 5
    for attempt in range(max_retries):
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[title*='recaptcha']"))
            )
            time.sleep(3)
            results = driver.execute_script(script)

            if results and len(results) > 0:
                for result in results:
                    if (result.get('clientId') is not None and
                            result.get('toplevelKey') and
                            result.get('sublevelKey') and
                            result.get('sitekey')):
                        callback_info = {
                            'clientId': result['clientId'],
                            'toplevelKey': result['toplevelKey'],
                            'sublevelKey': result['sublevelKey'],
                            'sitekey': result.get('sitekey'),
                            'pageurl': result.get('pageurl')
                        }
                        print(f"[验证码] 找到有效的callback信息")
                        print(f"[验证码] callback 信息: {json.dumps(callback_info, indent=2)}")
                        return callback_info

                if attempt < max_retries - 1:
                    time.sleep(5)

        except Exception as e:
            print(f"[验证码错误] 查找回调路径出错 (尝试 {attempt + 1}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(5)

    return None


def solve_recaptcha(api_key, sitekey, page_url):
    """解决验证码"""
    try:
        print(f"[验证码] 开始解决验证码: sitekey={sitekey}")
        
        # 构建验证码请求数据
        captcha_data = {
            "key": api_key,
            "method": "userrecaptcha",
            "googlekey": sitekey,
            "pageurl": page_url,
            "json": 1
        }

        # 发送到2captcha API
        response = requests.post('https://2captcha.com/in.php', data=captcha_data)
        if response.ok:
            result = response.json()
            if result['status'] == 1:
                # 获取请求ID
                request_id = result['request']
                print(f"[验证码] 验证码请求已提交，ID: {request_id}")

                # 等待结果
                for _ in range(30):  # 最多等待30次
                    time.sleep(5)  # 每5秒检查一次
                    result_response = requests.get(
                        'https://2captcha.com/res.php',
                        params={
                            'key': api_key,
                            'action': 'get',
                            'id': request_id,
                            'json': 1
                        }
                    )
                    if result_response.ok:
                        result_json = result_response.json()
                        if result_json['status'] == 1:
                            print(f"[验证码] 验证码解决成功！")
                            return result_json['request']

            print(f"[验证码错误] 验证码解决失败")
            return None

    except Exception as e:
        print(f"[验证码错误] 解决验证码过程出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def execute_callback(driver, token, callback_info):
    """执行验证码回调"""
    callback_js = f"""
    try {{
        if (___grecaptcha_cfg.clients['{callback_info['clientId']}']['{callback_info['toplevelKey']}']['{callback_info['sublevelKey']}']['callback']) {{
            ___grecaptcha_cfg.clients['{callback_info['clientId']}']['{callback_info['toplevelKey']}']['{callback_info['sublevelKey']}']['callback']('{token}');
            return true;
        }}
        return false;
    }} catch(e) {{
        console.error(e);
        return false;
    }}
    """

    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"[验证码] 尝试执行回调...")
            result = driver.execute_script(callback_js)
            if result:
                print(f"[验证码] 回调执行成功")
                return True
            elif attempt < max_retries - 1:
                print(f"[验证码] 回调执行失败，将在3秒后重试 ({attempt + 1}/{max_retries})")
                time.sleep(3)
        except Exception as e:
            print(f"[验证码错误] 回调执行出错: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(3)

    return False


def handle_captcha_page(driver):
    """处理人机验证页面"""
    try:
        print(f"[验证码] 开始处理人机验证页面...")
        
        # 检查是否启用了验证码解决功能
        if not CAPTCHA_CONFIG.get('enabled', False):
            print(f"[验证码错误] 验证码解决功能未启用")
            return "not_enabled"
        
        api_key = CAPTCHA_CONFIG.get('api_key')
        if not api_key or api_key == "your_2captcha_api_key_here":
            print(f"[验证码错误] 未配置2captcha API密钥")
            return "no_api_key"
        
        # 查找验证码回调路径
        callback_info = find_callback_path(driver)
        if not callback_info:
            print(f"[验证码错误] 未找到验证码回调路径")
            return "callback_not_found"
        
        # 解决验证码
        token = solve_recaptcha(
            api_key=api_key,
            sitekey=callback_info['sitekey'],
            page_url=callback_info['pageurl']
        )
        
        if not token:
            print(f"[验证码错误] 获取验证码令牌失败")
            return "token_failed"
        
        # 执行回调
        if not execute_callback(driver, token, callback_info):
            print(f"[验证码错误] 执行验证码回调失败")
            return "callback_failed"
        
        print(f"[验证码] 验证码处理成功")
        time.sleep(3)
        
        # 尝试查找并点击"下一步"按钮
        try:
            print(f"[验证码] 查找下一步按钮...")
            next_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[@jsname='V67aGc' and contains(text(), 'Next')]"))
            )
            print(f"[验证码] 找到下一步按钮，准备点击")
            next_button.click()
            print(f"[验证码] 已点击下一步按钮")
            time.sleep(5)
            
            # 检查结果
            current_url = driver.current_url
            print(f"[验证码] 验证后 URL: {current_url}")
            
            if "myaccount.google.com" in current_url:
                print(f"[验证码] 验证成功，已登录")
                return "success"
            else:
                print(f"[验证码] 验证完成，继续后续流程")
                return "continue"
        except Exception as e:
            print(f"[验证码] 未找到下一步按钮或点击失败: {str(e)}")
            # 即使没有找到下一步按钮，也返回continue让后续流程继续检测
            return "continue"
            
    except Exception as e:
        error_msg = f"处理验证码页面失败: {str(e)}"
        print(f"[验证码错误] {error_msg}")
        import traceback
        traceback.print_exc()
        return "error"


def get_available_phone():
    """获取一个可用的手机号（未使用且未过期）"""
    try:
        now = datetime.now()
        # 查找未使用且未过期的手机号
        phone = Phone.query.filter(
            Phone.status == False,
            db.or_(Phone.expire_time == None, Phone.expire_time > now)
        ).first()
        
        if phone:
            print(f"[手机号] 找到可用手机号: {phone.phone_number}")
            return phone
        else:
            print(f"[手机号错误] 没有可用的手机号")
            return None
    except Exception as e:
        print(f"[手机号错误] 获取手机号失败: {str(e)}")
        return None


def get_sms_code(sms_url, max_retries=12, interval=10):
    """从接码URL获取验证码
    
    Args:
        sms_url: 接码URL
        max_retries: 最大重试次数，默认12次
        interval: 重试间隔（秒），默认10秒
    
    Returns:
        str: 验证码，如 "123456"，失败返回 None
    """
    try:
        print(f"[验证码] 开始从接码URL获取验证码...")
        print(f"[验证码] URL: {sms_url}")
        
        for attempt in range(max_retries):
            try:
                print(f"[验证码] 第 {attempt + 1}/{max_retries} 次尝试...")
                
                # 请求接码URL
                response = requests.get(sms_url, timeout=30)
                if response.status_code == 200:
                    content = response.text
                    print(f"[验证码] 获取到内容: {content[:200] if len(content) > 200 else content}")
                    
                    # 从内容中提取验证码，格式如 "G-123456"
                    match = re.search(r'G-(\d{5,6})', content)
                    if match:
                        code = match.group(1)
                        print(f"[验证码] ✅ 成功获取验证码: {code}")
                        return code
                    else:
                        print(f"[验证码] 未找到验证码格式 G-XXXXXX，继续等待...")
                else:
                    print(f"[验证码] 请求失败，状态码: {response.status_code}")
                
                # 如果还没到最后一次，等待后继续
                if attempt < max_retries - 1:
                    print(f"[验证码] 等待 {interval} 秒后重试...")
                    time.sleep(interval)
                    
            except requests.RequestException as e:
                print(f"[验证码错误] 请求异常: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(interval)
        
        print(f"[验证码错误] 超过最大重试次数 {max_retries}，获取失败")
        return None
        
    except Exception as e:
        print(f"[验证码错误] 获取验证码异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def handle_phone_verification(driver, account_id):
    """处理手机号验证页面
    
    Args:
        driver: Selenium WebDriver
        account_id: 账号ID
    
    Returns:
        str: 处理结果 "success"/"no_phone"/"failed"
    """
    try:
        print(f"[手机验证] 开始处理手机号验证...")
        
        # 1. 获取可用手机号
        phone = get_available_phone()
        if not phone:
            print(f"[手机验证错误] 没有可用的手机号")
            return "no_phone"
        
        if not phone.sms_url:
            print(f"[手机验证错误] 手机号 {phone.phone_number} 没有配置接码URL")
            return "no_sms_url"
        
        # 2. 输入手机号
        try:
            print(f"[手机验证] 查找手机号输入框...")
            # 等待手机号输入框出现
            phone_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='tel' or @id='phoneNumberId']"))
            )
            
            # 输入手机号（带+号）
            full_phone = f"+{phone.phone_number}"
            print(f"[手机验证] 输入手机号: {full_phone}")
            phone_input.clear()
            phone_input.send_keys(full_phone)
            time.sleep(2)
            
            # 点击"下一步"按钮
            print(f"[手机验证] 查找并点击下一步按钮...")
            next_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@type='button']//span[contains(text(), 'Next') or contains(text(), '下一步')]"))
            )
            next_button.click()
            print(f"[手机验证] 已点击下一步")
            
            # 等待验证码输入框出现
            time.sleep(5)
            
        except Exception as e:
            error_msg = f"输入手机号失败: {str(e)}"
            print(f"[手机验证错误] {error_msg}")
            import traceback
            traceback.print_exc()
            return "input_phone_failed"
        
        # 3. 获取验证码
        print(f"[手机验证] 开始获取验证码...")
        sms_code = get_sms_code(phone.sms_url, max_retries=12, interval=10)
        if not sms_code:
            print(f"[手机验证错误] 获取验证码失败")
            return "sms_code_failed"
        
        # 4. 输入验证码
        try:
            print(f"[手机验证] 查找验证码输入框...")
            code_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='tel' or @id='code' or contains(@name, 'code')]"))
            )
            
            print(f"[手机验证] 输入验证码: {sms_code}")
            code_input.clear()
            code_input.send_keys(sms_code)
            time.sleep(2)
            
            # 点击"下一步"或"验证"按钮
            print(f"[手机验证] 查找并点击验证按钮...")
            try:
                verify_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@type='button']//span[contains(text(), 'Next') or contains(text(), '下一步') or contains(text(), 'Verify') or contains(text(), '验证')]"))
                )
                verify_button.click()
                print(f"[手机验证] 已点击验证按钮")
            except:
                # 有些页面可能自动提交
                print(f"[手机验证] 未找到验证按钮，可能自动提交")
            
            # 等待页面跳转
            time.sleep(5)
            
            # 5. 检查结果
            current_url = driver.current_url
            print(f"[手机验证] 验证后 URL: {current_url}")
            
            if "myaccount.google.com" in current_url:
                print(f"[手机验证] ✅ 验证成功，已登录")
                
                # 6. 更新数据库
                try:
                    # 标记手机号为已使用
                    phone.status = True
                    db.session.commit()
                    
                    # 绑定手机号到账号
                    account = Account.query.get(account_id)
                    if account:
                        account.phone_id = phone.id
                        db.session.commit()
                        print(f"[手机验证] 已绑定手机号到账号")
                    
                except Exception as e:
                    print(f"[手机验证警告] 更新数据库失败: {str(e)}")
                
                return "success"
            else:
                # 检查是否还在验证页面（可能验证码错误）
                try:
                    error_element = driver.find_element(By.XPATH, "//span[contains(text(), 'wrong') or contains(text(), 'incorrect') or contains(text(), '错误')]")
                    if error_element:
                        print(f"[手机验证错误] 验证码错误")
                        return "code_error"
                except:
                    pass
                
                print(f"[手机验证] 验证完成，继续后续流程")
                
                # 更新数据库
                try:
                    phone.status = True
                    account = Account.query.get(account_id)
                    if account:
                        account.phone_id = phone.id
                    db.session.commit()
                except Exception as e:
                    print(f"[手机验证警告] 更新数据库失败: {str(e)}")
                
                return "continue"
                
        except Exception as e:
            error_msg = f"输入验证码失败: {str(e)}"
            print(f"[手机验证错误] {error_msg}")
            import traceback
            traceback.print_exc()
            return "input_code_failed"
            
    except Exception as e:
        error_msg = f"处理手机验证失败: {str(e)}"
        print(f"[手机验证错误] {error_msg}")
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


def perform_login(driver, account, password, account_id=None, backup_email=None):
    """执行登录操作（使用状态机模式）
    
    Args:
        driver: Selenium WebDriver
        account: 账号邮箱
        password: 密码
        account_id: 账号ID（用于绑定手机号）
        backup_email: 辅助邮箱
    """
    import time as time_module
    start_time = time_module.time()
    max_total_time = 600  # 最大总时间10分钟，超过则认为登录失败
    
    try:
        # 导航到Google账号页面
        print(f"[登录] 正在访问 Google 账号页面...")
        try:
            driver.get('https://accounts.google.com/')
            time.sleep(3)
        except Exception as e:
            print(f"[登录错误] 访问页面失败，浏览器可能已关闭: {str(e)}")
            return "failed", "浏览器连接失败，可能已被关闭"
        
        # 循环处理登录流程（最多8次状态转换，增加重试机会）
        max_attempts = 8
        for attempt in range(max_attempts):
            # 检查是否超时
            elapsed_time = time_module.time() - start_time
            if elapsed_time > max_total_time:
                print(f"[登录超时] 登录流程超过 {max_total_time} 秒")
                return "failed", f"登录超时（超过{max_total_time}秒）"
            print(f"\n[登录] ===== 第 {attempt + 1} 次状态检测 =====")
            try:
                # 先输出当前URL
                try:
                    current_url = driver.current_url
                    print(f"[登录] 当前 URL: {current_url}")
                except:
                    pass
                
                current_state = detect_login_page_state(driver)
                print(f"[登录] 检测到状态: {current_state}")
            except Exception as e:
                print(f"[登录错误] 检测页面状态失败，浏览器可能已关闭: {str(e)}")
                return "failed", "浏览器连接失败，可能已被关闭"
            
            if current_state == "logged_in":
                return "success", "已登录状态"
            
            elif current_state == "need_email":
                # 处理邮箱输入页面
                try:
                    # 双重检查：确保不是"Verify it's you"页面
                    try:
                        verify_title = driver.find_element(By.XPATH, "//h1[contains(text(), \"Verify it's you\") or contains(text(), '验证您的身份')]")
                        if verify_title and verify_title.is_displayed():
                            print(f"[登录警告] 误检测为need_email，实际是Verify it's you页面，重新检测...")
                            time.sleep(2)
                            continue
                    except:
                        pass
                    
                    print(f"[登录] 开始输入邮箱: {account}")
                    email_input = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "identifierId"))
                    )
                    
                    # 检查输入框是否可编辑
                    if email_input.get_attribute("readonly") or email_input.get_attribute("disabled"):
                        print(f"[登录警告] 邮箱输入框不可编辑，重新检测状态...")
                        time.sleep(2)
                        continue
                    
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
                    # 如果输入失败，尝试重新检测状态而不是直接返回失败
                    print(f"[登录] 尝试重新检测页面状态...")
                    time.sleep(2)
                    continue
            
            elif current_state == "need_password":
                # 处理密码页面
                status = handle_password_page(driver, password)
                
                if status == "success":
                    return "success", "登录成功"
                elif status == "need_phone":
                    # 不直接返回，而是继续循环让下一轮处理手机验证
                    print(f"[登录] 密码处理后需要手机验证，继续下一轮循环处理...")
                    time.sleep(2)
                    continue
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
            
            elif current_state == "verify_click_next":
                # 处理需要点击Next的 "Verify it's you" 页面
                status = handle_verify_click_next_page(driver)
                
                if status == "success":
                    return "success", "验证成功，已登录"
                elif status == "need_captcha":
                    # 进入人机验证流程
                    print(f"[登录] 检测到人机验证，开始处理...")
                    captcha_status = handle_captcha_page(driver)
                    
                    if captcha_status == "success":
                        return "success", "人机验证成功，已登录"
                    elif captcha_status == "continue":
                        # 继续下一轮检测
                        print(f"[登录] 人机验证完成，继续检测后续状态...")
                        time.sleep(2)
                        continue
                    elif captcha_status == "not_enabled":
                        return "failed", "需要人机验证，但验证码解决功能未启用"
                    elif captcha_status == "no_api_key":
                        return "failed", "需要人机验证，但未配置2captcha API密钥"
                    else:
                        return "failed", f"人机验证处理失败: {captcha_status}"
                elif status == "continue":
                    # 继续下一轮检测
                    print(f"[登录] 点击Next完成，继续检测后续状态...")
                    time.sleep(2)
                    continue
                else:
                    return "failed", f"验证身份页面处理失败: {status}"
            
            elif current_state == "need_captcha":
                # 直接处理人机验证页面
                status = handle_captcha_page(driver)
                
                if status == "success":
                    return "success", "人机验证成功，已登录"
                elif status == "continue":
                    # 继续下一轮检测
                    print(f"[登录] 人机验证完成，继续检测后续状态...")
                    time.sleep(2)
                    continue
                elif status == "not_enabled":
                    return "failed", "需要人机验证，但验证码解决功能未启用"
                elif status == "no_api_key":
                    return "failed", "需要人机验证，但未配置2captcha API密钥"
                else:
                    return "failed", f"人机验证处理失败: {status}"
            
            elif current_state == "need_phone":
                # 处理手机号验证
                print(f"[登录] 开始处理手机号验证...")
                status = handle_phone_verification(driver, account_id)
                
                if status == "success":
                    return "success", "手机号验证成功，已登录"
                elif status == "continue":
                    # 继续下一轮检测
                    print(f"[登录] 手机号验证完成，继续检测后续状态...")
                    time.sleep(2)
                    continue
                elif status == "no_phone":
                    return "failed", "需要手机号验证，但没有可用的手机号"
                elif status == "no_sms_url":
                    return "failed", "手机号没有配置接码URL"
                elif status == "sms_code_failed":
                    return "failed", "获取验证码失败（超过12次重试）"
                else:
                    return "failed", f"手机号验证失败: {status}"
            
            elif current_state == "need_2fa":
                return "need_2fa", "需要2FA验证"
            
            elif current_state == "disabled":
                return "disabled", "账号被禁用"
            
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
            
            # 执行登录（传递账号ID和辅助邮箱）
            status, message = perform_login(driver, account.account, account.password, account_id=account_id, backup_email=account.backup_email)
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

