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
from config import CAPTCHA_CONFIG, APPEAL_TEXT_PATH
import pandas as pd
import os


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


def get_appeal_text_from_excel():
    """从Excel文件中随机获取一条申诉文案
    
    Returns:
        str: 申诉文案，失败返回 None
    """
    try:
        # 检查配置
        if not APPEAL_TEXT_PATH:
            print(f"[申诉] 错误: 未配置申诉文案Excel路径")
            return None
        
        if not os.path.exists(APPEAL_TEXT_PATH):
            print(f"[申诉] 错误: 申诉文案文件不存在: {APPEAL_TEXT_PATH}")
            return None
        
        print(f"[申诉] 开始读取申诉文案Excel文件: {APPEAL_TEXT_PATH}")
        
        # 读取Excel文件
        df = pd.read_excel(APPEAL_TEXT_PATH)
        
        # 检查是否有数据
        if df.empty:
            print(f"[申诉] 错误: Excel文件为空")
            return None
        
        # 获取第二列的数据（索引为1，因为从0开始）
        if len(df.columns) < 2:
            print(f"[申诉] 错误: Excel文件列数不足，需要至少2列")
            return None
        
        # 获取第二列的所有非空值
        appeal_texts = df.iloc[:, 1].dropna().tolist()
        
        if not appeal_texts:
            print(f"[申诉] 错误: 第二列没有可用的申诉文案")
            return None
        
        # 随机选择一条
        import random
        appeal_text = random.choice(appeal_texts)
        
        print(f"[申诉] 成功获取申诉文案（共{len(appeal_texts)}条可用）")
        print(f"[申诉] 文案内容: {appeal_text[:100]}...")  # 只显示前100个字符
        
        return str(appeal_text)
        
    except Exception as e:
        print(f"[申诉] 读取申诉文案失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def handle_appeal_flow(driver, backup_email):
    """处理申诉流程
    
    Args:
        driver: Selenium WebDriver
        backup_email: 辅助邮箱
    
    Returns:
        str: 处理结果 "success"/"failed"
    """
    try:
        print(f"[申诉] 开始处理申诉流程...")
        
        # 1. 检查是否在禁用页面
        current_url = driver.current_url
        print(f"[申诉] 当前URL: {current_url}")
        
        if "speedbump/disabled/explanation" not in current_url:
            print(f"[申诉] 错误: 不在申诉起始页面")
            return "not_appeal_page"
        
        # 等待页面加载
        time.sleep(3)
        
        # 2. 点击 "Start appeal" 按钮
        try:
            print(f"[申诉] 查找 'Start appeal' 按钮...")
            start_appeal_button = None
            
            try:
                # 方式1: 通过文本查找
                start_appeal_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Start appeal') or contains(text(), '开始申诉')]"))
                )
                print(f"[申诉] 通过文本找到按钮")
            except:
                try:
                    # 方式2: 查找所有button，找包含appeal的
                    buttons = driver.find_elements(By.TAG_NAME, "button")
                    for btn in buttons:
                        if btn.is_displayed() and 'appeal' in btn.text.lower():
                            start_appeal_button = btn
                            print(f"[申诉] 通过遍历找到按钮")
                            break
                except:
                    pass
            
            if not start_appeal_button:
                print(f"[申诉] 错误: 未找到 'Start appeal' 按钮")
                return "start_button_not_found"
            
            # 滚动并点击
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", start_appeal_button)
            time.sleep(1)
            
            try:
                start_appeal_button.click()
                print(f"[申诉] 已点击 'Start appeal' 按钮")
            except:
                driver.execute_script("arguments[0].click();", start_appeal_button)
                print(f"[申诉] 已点击 'Start appeal' 按钮（JS方式）")
            
            time.sleep(3)
            
        except Exception as e:
            error_msg = f"点击 'Start appeal' 按钮失败: {str(e)}"
            print(f"[申诉] 错误: {error_msg}")
            import traceback
            traceback.print_exc()
            return "click_start_failed"
        
        # 3. 在 reviewconsent 页面点击 Next
        try:
            current_url = driver.current_url
            print(f"[申诉] 当前URL: {current_url}")
            
            if "reviewconsent" in current_url:
                print(f"[申诉] 在 reviewconsent 页面，查找 Next 按钮...")
                
                next_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Next') or contains(., '下一步')]"))
                )
                
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                time.sleep(1)
                
                try:
                    next_button.click()
                    print(f"[申诉] 已点击 Next 按钮")
                except:
                    driver.execute_script("arguments[0].click();", next_button)
                    print(f"[申诉] 已点击 Next 按钮（JS方式）")
                
                time.sleep(3)
            
        except Exception as e:
            print(f"[申诉] 警告: reviewconsent 页面处理失败: {str(e)}")
            # 继续执行，可能已经自动跳转
        
        # 4. 在 additionalinformation 页面填写申诉文案
        try:
            current_url = driver.current_url
            print(f"[申诉] 当前URL: {current_url}")
            
            if "additionalinformation" not in current_url:
                print(f"[申诉] 警告: 未到达 additionalinformation 页面，等待跳转...")
                time.sleep(5)
                current_url = driver.current_url
                print(f"[申诉] 等待后URL: {current_url}")
            
            # 获取申诉文案
            appeal_text = get_appeal_text_from_excel()
            if not appeal_text:
                print(f"[申诉] 错误: 无法获取申诉文案")
                return "no_appeal_text"
            
            # 查找输入框
            print(f"[申诉] 查找申诉文案输入框...")
            text_input = None
            
            try:
                # 尝试多种方式查找输入框
                input_selectors = [
                    "//textarea",
                    "//input[@type='text']",
                    "//textarea[@aria-label='Enter appeal reason']",
                    "//div[@contenteditable='true']"
                ]
                
                for selector in input_selectors:
                    try:
                        text_input = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, selector))
                        )
                        if text_input and text_input.is_displayed():
                            print(f"[申诉] 找到输入框，使用选择器: {selector}")
                            break
                        else:
                            text_input = None
                    except:
                        continue
                
                if not text_input:
                    print(f"[申诉] 错误: 未找到申诉文案输入框")
                    return "input_not_found"
                
                # 滚动到输入框
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", text_input)
                time.sleep(1)
                
                # 输入申诉文案
                try:
                    text_input.click()
                    time.sleep(0.5)
                    text_input.clear()
                    text_input.send_keys(appeal_text)
                    print(f"[申诉] 已输入申诉文案（普通方式）")
                except:
                    # 使用JS方式
                    driver.execute_script(f"arguments[0].value = '{appeal_text}';", text_input)
                    driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", text_input)
                    print(f"[申诉] 已输入申诉文案（JS方式）")
                
                time.sleep(2)
                
                # 点击 Next 按钮
                print(f"[申诉] 查找 Next 按钮...")
                next_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Next') or contains(., '下一步')]"))
                )
                
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                time.sleep(1)
                
                try:
                    next_button.click()
                    print(f"[申诉] 已点击 Next 按钮")
                except:
                    driver.execute_script("arguments[0].click();", next_button)
                    print(f"[申诉] 已点击 Next 按钮（JS方式）")
                
                time.sleep(3)
                
            except Exception as e:
                error_msg = f"输入申诉文案失败: {str(e)}"
                print(f"[申诉] 错误: {error_msg}")
                import traceback
                traceback.print_exc()
                return "input_appeal_failed"
            
        except Exception as e:
            error_msg = f"处理 additionalinformation 页面失败: {str(e)}"
            print(f"[申诉] 错误: {error_msg}")
            import traceback
            traceback.print_exc()
            return "additional_info_failed"
        
        # 5. 在 contactaddress 页面填写辅助邮箱
        try:
            current_url = driver.current_url
            print(f"[申诉] 当前URL: {current_url}")
            
            if "contactaddress" not in current_url:
                print(f"[申诉] 警告: 未到达 contactaddress 页面，等待跳转...")
                time.sleep(5)
                current_url = driver.current_url
                print(f"[申诉] 等待后URL: {current_url}")
            
            if not backup_email:
                print(f"[申诉] 错误: 账号未设置辅助邮箱")
                return "no_backup_email"
            
            # 查找邮箱输入框
            print(f"[申诉] 查找联系邮箱输入框...")
            email_input = None
            
            try:
                email_input_selectors = [
                    "//input[@type='email']",
                    "//input[contains(@placeholder, 'email')]",
                    "//input[contains(@aria-label, 'email')]"
                ]
                
                for selector in email_input_selectors:
                    try:
                        email_input = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, selector))
                        )
                        if email_input and email_input.is_displayed():
                            print(f"[申诉] 找到邮箱输入框，使用选择器: {selector}")
                            break
                        else:
                            email_input = None
                    except:
                        continue
                
                if not email_input:
                    print(f"[申诉] 错误: 未找到邮箱输入框")
                    return "email_input_not_found"
                
                # 滚动到输入框
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", email_input)
                time.sleep(1)
                
                # 输入辅助邮箱
                try:
                    email_input.click()
                    time.sleep(0.5)
                    email_input.clear()
                    email_input.send_keys(backup_email)
                    print(f"[申诉] 已输入辅助邮箱: {backup_email}")
                except:
                    # 使用JS方式
                    driver.execute_script(f"arguments[0].value = '{backup_email}';", email_input)
                    driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", email_input)
                    print(f"[申诉] 已输入辅助邮箱（JS方式）: {backup_email}")
                
                time.sleep(2)
                
                # 点击 Submit appeal 按钮
                print(f"[申诉] 查找 'Submit appeal' 按钮...")
                submit_button = None
                
                try:
                    # 方式1: 通过文本查找
                    submit_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Submit appeal') or contains(., '提交申诉')]"))
                    )
                    print(f"[申诉] 通过文本找到 Submit 按钮")
                except:
                    try:
                        # 方式2: 查找所有button，找包含submit的
                        buttons = driver.find_elements(By.TAG_NAME, "button")
                        for btn in buttons:
                            if btn.is_displayed() and ('submit' in btn.text.lower() or '提交' in btn.text):
                                submit_button = btn
                                print(f"[申诉] 通过遍历找到 Submit 按钮")
                                break
                    except:
                        pass
                
                if not submit_button:
                    print(f"[申诉] 错误: 未找到 'Submit appeal' 按钮")
                    return "submit_button_not_found"
                
                # 滚动并点击
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_button)
                time.sleep(1)
                
                try:
                    submit_button.click()
                    print(f"[申诉] 已点击 'Submit appeal' 按钮")
                except:
                    driver.execute_script("arguments[0].click();", submit_button)
                    print(f"[申诉] 已点击 'Submit appeal' 按钮（JS方式）")
                
                time.sleep(5)
                
                # 检查是否成功
                current_url = driver.current_url
                print(f"[申诉] 提交后URL: {current_url}")
                
                if "confirmation" in current_url or "submitted" in current_url:
                    print(f"[申诉] ✅ 申诉提交成功！")
                    return "success"
                else:
                    # 检查页面是否有成功提示
                    try:
                        success_element = driver.find_element(By.XPATH, "//h1[contains(text(), 'submitted') or contains(text(), '已提交')]")
                        if success_element and success_element.is_displayed():
                            print(f"[申诉] ✅ 检测到成功提示，申诉提交成功！")
                            return "success"
                    except:
                        pass
                    
                    print(f"[申诉] 警告: 无法确认申诉是否提交成功")
                    return "unknown"
                
            except Exception as e:
                error_msg = f"输入辅助邮箱或提交申诉失败: {str(e)}"
                print(f"[申诉] 错误: {error_msg}")
                import traceback
                traceback.print_exc()
                return "submit_appeal_failed"
            
        except Exception as e:
            error_msg = f"处理 contactaddress 页面失败: {str(e)}"
            print(f"[申诉] 错误: {error_msg}")
            import traceback
            traceback.print_exc()
            return "contact_address_failed"
        
    except Exception as e:
        error_msg = f"申诉流程处理失败: {str(e)}"
        print(f"[申诉] 错误: {error_msg}")
        import traceback
        traceback.print_exc()
        return "error"


def detect_login_page_state(driver):
    """检测登录页面的当前状态"""
    try:
        try:
            current_url = driver.current_url
            print(f"[状态检测] 当前 URL: {current_url}")
        except Exception as e:
            print(f"[状态检测错误] 无法获取URL，浏览器可能已关闭: {str(e)}")
            raise Exception("浏览器连接失败")
        
        # 优先检查是否是身份验证失败页面
        if "signin/rejected" in current_url:
            print(f"[状态检测] 检测到身份验证失败页面 (We couldn't verify it's you)")
            print(f"[状态检测] 尝试点击 'Try again' 链接...")
            
            try:
                # 尝试多种方式查找"Try again"链接
                try_again_clicked = False
                
                # 方法1: 通过aria-label属性查找a标签（最准确）
                try:
                    try_again_link = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, "//a[@aria-label='Try again']"))
                    )
                    try_again_link.click()
                    print(f"[状态检测] ✅ 成功点击 'Try again' 链接 (方法1: aria-label)")
                    try_again_clicked = True
                except Exception as e:
                    print(f"[状态检测] 方法1失败: {str(e)}")
                
                # 方法2: 通过jsname属性查找
                if not try_again_clicked:
                    try:
                        try_again_link = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, "//a[@jsname='hSRGPd']"))
                        )
                        try_again_link.click()
                        print(f"[状态检测] ✅ 成功点击 'Try again' 链接 (方法2: jsname)")
                        try_again_clicked = True
                    except Exception as e:
                        print(f"[状态检测] 方法2失败: {str(e)}")
                
                # 方法3: 通过href包含restart的a标签
                if not try_again_clicked:
                    try:
                        try_again_link = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/restart')]"))
                        )
                        try_again_link.click()
                        print(f"[状态检测] ✅ 成功点击 'Try again' 链接 (方法3: restart href)")
                        try_again_clicked = True
                    except Exception as e:
                        print(f"[状态检测] 方法3失败: {str(e)}")
                
                # 方法4: 通过class和data-navigation属性
                if not try_again_clicked:
                    try:
                        try_again_link = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, "//a[@data-navigation='server' and contains(@class, 'WpHeLc')]"))
                        )
                        try_again_link.click()
                        print(f"[状态检测] ✅ 成功点击 'Try again' 链接 (方法4: class+data-navigation)")
                        try_again_clicked = True
                    except Exception as e:
                        print(f"[状态检测] 方法4失败: {str(e)}")
                
                if try_again_clicked:
                    time.sleep(3)  # 等待页面重新加载
                    return "need_retry"  # 返回需要重试状态
                else:
                    print(f"[状态检测] ⚠️ 未找到 'Try again' 链接")
                    print(f"[状态检测] ⚠️ 这是一个无法验证身份的页面，需要使用熟悉的设备/网络")
                    return "identity_verification_failed"  # 无法验证身份
                    
            except Exception as e:
                print(f"[状态检测] 点击 'Try again' 链接失败: {str(e)}")
            
            return "identity_verification_failed"  # 无法验证身份
        
        # 优先通过 URL 判断（最可靠的方法）
        if "myaccount.google.com" in current_url:
            # 检查是否是修改密码页面
            if "signinoptions/password" in current_url:
                print(f"[状态检测] 检测到修改密码页面，检查是否需要安全验证...")
                # 检查是否有安全验证要求
                try:
                    # 查找是否有安全验证相关的文本
                    body_text = driver.find_element(By.TAG_NAME, 'body').text.lower()
                    if any(keyword in body_text for keyword in ['verify', 'security', 'original device', '原设备', '安全验证', '验证身份']):
                        # 但如果页面有"New password"和"Confirm new password"输入框，说明是正常的修改密码页面
                        try:
                            new_pwd = driver.find_element(By.XPATH, "//input[contains(@placeholder, 'New password') or contains(@aria-label, 'New password')]")
                            confirm_pwd = driver.find_element(By.XPATH, "//input[contains(@placeholder, 'Confirm') or contains(@aria-label, 'Confirm')]")
                            if new_pwd and confirm_pwd:
                                print(f"[状态检测] 检测到正常的修改密码页面（有新密码输入框）")
                                return "logged_in"
                        except:
                            # 如果找不到新密码输入框，可能是需要安全验证
                            print(f"[状态检测] 检测到需要安全验证的修改密码页面")
                            return "need_security_verification"
                    else:
                        # 没有安全验证关键词，正常的修改密码页面
                        print(f"[状态检测] 正常的修改密码页面，登录成功")
                        return "logged_in"
                except Exception as e:
                    print(f"[状态检测] 检查安全验证失败: {str(e)}，默认为登录成功")
                    return "logged_in"
            else:
                # 其他myaccount页面，直接认为登录成功
                return "logged_in"
        
        # 检查是否是选择账号页面
        if "accountchooser" in current_url or "chooseaccount" in current_url:
            print(f"[状态检测] 检测到选择账号页面")
            return "choose_account"
        
        # 检查是否是密码输入页面（通过 URL 判断）
        if "/signin/challenge/pwd" in current_url or "/challenge/pwd" in current_url:
            try:
                password_input = driver.find_element(By.NAME, "Passwd")
                if password_input:
                    print(f"[状态检测] 检测到密码页面")
                    return "need_password"
            except:
                pass
        
        # 检查是否是恢复选项页面（添加手机号和邮箱）
        if "recoveryoptions" in current_url:
            print(f"[状态检测] 检测到恢复选项设置页面")
            return "recovery_options"
        
        # 检查是否是设置住址页面
        if "homeaddress" in current_url:
            print(f"[状态检测] 检测到设置住址页面")
            return "home_address"
        
        # 检查是否需要验证手机号
        if "challenge/iap" in current_url or "speedbump/idvreenable" in current_url or "challenge/dp" in current_url:
            print(f"[状态检测] 检测到手机验证页面")
            return "need_phone"
        
        # 检查是否是需要点击Send发送验证码的手机验证页面（ipp/consent）
        if "ipp/consent" in current_url:
            print(f"[状态检测] 检测到需要点击Send发送验证码的手机验证页面")
            return "need_phone_consent"
        
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
            
            # 先检查是否是选择验证方式的页面（有 "Confirm your recovery email" 选项）
            try:
                recovery_email_option = driver.find_element(By.XPATH, "//div[contains(text(), 'Confirm your recovery email') or contains(text(), '确认您的恢复电子邮件')]")
                if recovery_email_option and recovery_email_option.is_displayed():
                    print(f"[状态检测] ✅ 检测到选择验证方式页面（需要点击recovery email）")
                    return "verify_identity"
            except:
                pass
            
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
                                print(f"[状态检测警告] 有Verify标题但未找到Next按钮，可能是选择页面")
                                # 如果有标题但没有Next按钮，可能是选择验证方式的页面
                                return "verify_identity"
                    
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
                    # 如果URL是selection且没有Next按钮，很可能是选择验证方式页面
                    if "selection" in current_url:
                        print(f"[状态检测] URL包含selection，判断为选择验证方式页面")
                        return "verify_identity"
                    pass
        
        # 检查账号被禁用（区分是否需要申诉）
        if "disabled" in current_url:
            # 检查是否是申诉起始页面（explanation）
            if "speedbump/disabled/explanation" in current_url:
                print(f"[状态检测] 检测到账号被禁用，需要申诉")
                return "need_appeal"
            else:
                print(f"[状态检测] 检测到账号被禁用")
                return "disabled"
        
        # 检查是否是 Passkey 注册页面
        if "passkeyenrollment" in current_url or "speedbump/passkey" in current_url:
            print(f"[状态检测] 检测到 Passkey 注册页面")
            return "passkey_enrollment"
        
        # 如果 URL 判断不明确，再通过页面元素判断
        if "accounts.google.com" in current_url:
            # 检查页面是否显示 "We couldn't verify it's you"
            try:
                couldnt_verify = driver.find_element(By.XPATH, "//h1[contains(text(), \"We couldn't verify\") or contains(text(), \"couldn't verify\")]")
                if couldnt_verify and couldnt_verify.is_displayed():
                    print(f"[状态检测] 检测到 'We couldn't verify it's you' 页面（通过文本内容检测）")
                    print(f"[状态检测] ⚠️ 无法验证身份，需要使用熟悉的设备或网络")
                    return "identity_verification_failed"
            except:
                pass
            
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
                # 方式1: 通过文本内容查找（区分大小写和不区分）
                recovery_email_option = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Confirm your recovery email')]"))
                )
                print(f"[验证身份] 方式1找到选项")
            except:
                try:
                    # 方式2: 不区分大小写
                    recovery_email_option = driver.find_element(By.XPATH,
                        "//div[contains(translate(text(), 'CONFIRM', 'confirm'), 'confirm') and contains(translate(text(), 'RECOVERY', 'recovery'), 'recovery') and contains(translate(text(), 'EMAIL', 'email'), 'email')]")
                    print(f"[验证身份] 方式2找到选项")
                except:
                    try:
                        # 方式3: 查找包含 recovery email 的任何可见元素
                        elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'recovery') and contains(text(), 'email')]")
                        for elem in elements:
                            if elem.is_displayed() and 'Confirm' in elem.text:
                                recovery_email_option = elem
                                print(f"[验证身份] 方式3找到选项")
                                break
                    except:
                        pass
            
            if recovery_email_option:
                print(f"[验证身份] 找到 'Confirm your recovery email' 选项，准备点击...")
                print(f"[验证身份] 选项文本: {recovery_email_option.text}")
                # 滚动到元素可见
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", recovery_email_option)
                time.sleep(1)
                
                # 尝试多种点击方式
                try:
                    recovery_email_option.click()
                    print(f"[验证身份] 已点击（普通点击）")
                except:
                    try:
                        driver.execute_script("arguments[0].click();", recovery_email_option)
                        print(f"[验证身份] 已点击（JS点击）")
                    except Exception as click_err:
                        print(f"[验证身份错误] 点击失败: {str(click_err)}")
                        return "click_failed"
                
                time.sleep(3)
            else:
                print(f"[验证身份错误] 未找到 'Confirm your recovery email' 选项")
                # 打印页面所有可见文本帮助调试
                try:
                    page_text = driver.find_element(By.TAG_NAME, 'body').text
                    print(f"[验证身份调试] 页面内容: {page_text[:500]}")
                except:
                    pass
                return "option_not_found"
                
        except Exception as e:
            error_msg = f"查找或点击 'Confirm your recovery email' 失败: {str(e)}"
            print(f"[验证身份错误] {error_msg}")
            import traceback
            traceback.print_exc()
            return "click_failed"
        
        # 输入辅助邮箱
        try:
            print(f"[验证身份] 等待邮箱输入框可交互...")
            
            # 先尝试通过ID查找（最精确）
            email_input = None
            try:
                email_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "knowledge-preregistered-email-response"))
                )
                print(f"[验证身份] 通过ID找到邮箱输入框")
            except:
                # 如果ID找不到，尝试通过name属性
                try:
                    email_input = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.NAME, "knowledgePreregisteredEmailResponse"))
                    )
                    print(f"[验证身份] 通过name找到邮箱输入框")
                except:
                    # 最后尝试通过type=email
                    email_input = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@type='email']"))
                    )
                    print(f"[验证身份] 通过type找到邮箱输入框")
            
            if not email_input:
                print(f"[验证身份错误] 未找到邮箱输入框")
                return "input_not_found"
            
            # 滚动到元素位置
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", email_input)
            time.sleep(1)
            
            # 等待元素真正可交互（最多等待10秒）
            try:
                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(email_input)
                )
                print(f"[验证身份] 邮箱输入框已可交互")
            except:
                print(f"[验证身份警告] 输入框等待超时，尝试直接操作")
            
            # 尝试点击激活输入框
            try:
                email_input.click()
                time.sleep(0.5)
                print(f"[验证身份] 已点击激活输入框")
            except Exception as click_err:
                print(f"[验证身份警告] 点击输入框失败: {str(click_err)}")
            
            # 清空并输入
            try:
                email_input.clear()
                email_input.send_keys(backup_email)
                print(f"[验证身份] 已输入辅助邮箱（普通方式）: {backup_email}")
            except Exception as input_error:
                # 如果常规方式失败，使用JavaScript直接设置值
                print(f"[验证身份] 常规输入失败，尝试使用JS输入: {str(input_error)}")
                try:
                    driver.execute_script(f"arguments[0].value = '{backup_email}';", email_input)
                    # 触发input事件以确保页面识别到输入
                    driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", email_input)
                    driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", email_input)
                    print(f"[验证身份] 已使用JS输入辅助邮箱: {backup_email}")
                except Exception as js_error:
                    print(f"[验证身份错误] JS输入也失败: {str(js_error)}")
                    return "input_failed"
            
            # 点击下一步
            print(f"[验证身份] 查找下一步按钮...")
            time.sleep(1)  # 等待输入生效
            
            try:
                next_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@type='button']//span[contains(text(), 'Next') or contains(text(), '下一步')]"))
                )
                # 滚动到按钮位置
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                time.sleep(0.5)
                next_button.click()
                print(f"[验证身份] 已点击下一步")
            except:
                # 如果找不到，尝试其他方式
                try:
                    next_button = driver.find_element(By.XPATH, "//button[@jsname='LgbsSe']")
                    driver.execute_script("arguments[0].click();", next_button)
                    print(f"[验证身份] 已点击下一步（JS方式）")
                except Exception as btn_err:
                    print(f"[验证身份错误] 未找到下一步按钮: {str(btn_err)}")
                    return "next_button_not_found"
            
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


def handle_recovery_options_page(driver, account_id):
    """处理恢复选项页面（添加手机号）
    
    Args:
        driver: Selenium WebDriver
        account_id: 账号ID
    
    Returns:
        str: 处理结果 "success"/"no_phone"/"failed"
    """
    try:
        print(f"[恢复选项] 开始处理恢复选项页面...")
        
        # 1. 获取可用手机号（优先使用已绑定的）
        phone = get_available_phone(account_id)
        if not phone:
            print(f"[恢复选项错误] 没有可用的手机号")
            return "no_phone"
        
        # 等待页面加载
        time.sleep(2)
        
        # 2. 输入手机号
        try:
            print(f"[恢复选项] 查找手机号输入框...")
            # 多种方式查找输入框
            phone_input = None
            try:
                # 方式1: 通过placeholder
                phone_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Enter phone' or contains(@aria-label, 'phone')]"))
                )
                print(f"[恢复选项] 通过placeholder找到输入框")
            except:
                try:
                    # 方式2: 通过type=tel
                    phone_input = driver.find_element(By.XPATH, "//input[@type='tel']")
                    print(f"[恢复选项] 通过type=tel找到输入框")
                except:
                    # 方式3: 查找所有input，找最可能是手机号的
                    inputs = driver.find_elements(By.TAG_NAME, "input")
                    for inp in inputs:
                        if inp.is_displayed() and not inp.get_attribute('value'):
                            phone_input = inp
                            print(f"[恢复选项] 通过遍历找到输入框")
                            break
            
            if not phone_input:
                print(f"[恢复选项错误] 未找到手机号输入框")
                return "phone_input_not_found"
            
            # 滚动到输入框
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", phone_input)
            time.sleep(1)
            
            # 输入手机号（带+号）
            full_phone = f"+{phone.phone_number}"
            print(f"[恢复选项] 输入手机号: {full_phone}")
            
            try:
                # 点击激活
                phone_input.click()
                time.sleep(0.5)
                # 输入
                phone_input.clear()
                phone_input.send_keys(full_phone)
                print(f"[恢复选项] 已输入手机号（普通方式）")
            except:
                # 使用JS方式
                driver.execute_script(f"arguments[0].value = '{full_phone}';", phone_input)
                driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", phone_input)
                print(f"[恢复选项] 已输入手机号（JS方式）")
            
            time.sleep(2)
            
        except Exception as e:
            error_msg = f"输入手机号失败: {str(e)}"
            print(f"[恢复选项错误] {error_msg}")
            import traceback
            traceback.print_exc()
            return "input_phone_failed"
        
        # 3. 点击Save按钮
        try:
            print(f"[恢复选项] 查找Save按钮...")
            save_button = None
            
            try:
                # 方式1: 通过文本
                save_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Save') or contains(text(), '保存')]"))
                )
                print(f"[恢复选项] 通过文本找到Save按钮")
            except:
                # 方式2: 查找所有button，找包含save的
                buttons = driver.find_elements(By.TAG_NAME, "button")
                for btn in buttons:
                    if btn.is_displayed() and ('save' in btn.text.lower() or '保存' in btn.text):
                        save_button = btn
                        print(f"[恢复选项] 通过遍历找到Save按钮")
                        break
            
            if save_button:
                # 滚动到按钮
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_button)
                time.sleep(1)
                
                # 点击
                try:
                    save_button.click()
                    print(f"[恢复选项] 已点击Save按钮")
                except:
                    driver.execute_script("arguments[0].click();", save_button)
                    print(f"[恢复选项] 已点击Save按钮（JS方式）")
                
                # 等待页面跳转
                time.sleep(5)
                
                # 检查结果
                current_url = driver.current_url
                print(f"[恢复选项] 保存后 URL: {current_url}")
                
                if "myaccount.google.com" in current_url:
                    print(f"[恢复选项] ✅ 保存成功，已登录")
                    
                    # 更新数据库
                    try:
                        # 标记手机号为已使用
                        if not phone.status:
                            phone.status = True
                            print(f"[恢复选项] 标记手机号为已使用")
                        
                        # 绑定手机号到账号
                        account = Account.query.get(account_id)
                        if account and account.phone_id != phone.id:
                            account.phone_id = phone.id
                            print(f"[恢复选项] 已绑定手机号到账号")
                        
                        db.session.commit()
                    except Exception as e:
                        print(f"[恢复选项警告] 更新数据库失败: {str(e)}")
                    
                    return "success"
                else:
                    print(f"[恢复选项] 保存完成，继续后续流程")
                    
                    # 更新数据库
                    try:
                        # 标记手机号为已使用
                        if not phone.status:
                            phone.status = True
                            print(f"[恢复选项] 标记手机号为已使用")
                        
                        # 绑定手机号到账号
                        account = Account.query.get(account_id)
                        if account and account.phone_id != phone.id:
                            account.phone_id = phone.id
                            print(f"[恢复选项] 已绑定手机号到账号")
                        
                        db.session.commit()
                    except Exception as e:
                        print(f"[恢复选项警告] 更新数据库失败: {str(e)}")
                    
                    return "continue"
            else:
                print(f"[恢复选项错误] 未找到Save按钮")
                return "save_button_not_found"
                
        except Exception as e:
            error_msg = f"点击Save按钮失败: {str(e)}"
            print(f"[恢复选项错误] {error_msg}")
            import traceback
            traceback.print_exc()
            return "click_save_failed"
            
    except Exception as e:
        error_msg = f"处理恢复选项页面失败: {str(e)}"
        print(f"[恢复选项错误] {error_msg}")
        import traceback
        traceback.print_exc()
        return "error"


def check_password_page_security_verification(driver):
    """检查修改密码页面是否需要安全验证
    
    Args:
        driver: Selenium WebDriver
    
    Returns:
        tuple: (status, message)
            - ("success", message): 无需安全验证
            - ("success_with_verification", message): 需要安全验证
    """
    try:
        print(f"[登录] 跳转到修改密码页面检测安全验证...")
        driver.get("https://myaccount.google.com/signinoptions/password")
        time.sleep(5)  # 等待页面加载，可能会重新要求登录验证或跳转到验证失败页面
        
        # 检查当前URL
        current_url = driver.current_url
        print(f"[登录] 当前 URL: {current_url}")
        
        # 检查是否跳转到 "We couldn't verify it's you" 页面
        if "signin/rejected" in current_url:
            print(f"[登录] ⚠️ 检测到跳转到身份验证失败页面 (signin/rejected)")
            print(f"[登录] 尝试点击 'Try again' 链接...")
            
            try:
                # 尝试多种方式查找"Try again"链接
                try_again_clicked = False
                
                # 方法1: 通过aria-label属性查找a标签（最准确）
                try:
                    try_again_link = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, "//a[@aria-label='Try again']"))
                    )
                    try_again_link.click()
                    print(f"[登录] ✅ 成功点击 'Try again' 链接 (方法1: aria-label)")
                    try_again_clicked = True
                except Exception as e:
                    print(f"[登录] 方法1失败: {str(e)}")
                
                # 方法2: 通过jsname属性查找
                if not try_again_clicked:
                    try:
                        try_again_link = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, "//a[@jsname='hSRGPd']"))
                        )
                        try_again_link.click()
                        print(f"[登录] ✅ 成功点击 'Try again' 链接 (方法2: jsname)")
                        try_again_clicked = True
                    except Exception as e:
                        print(f"[登录] 方法2失败: {str(e)}")
                
                # 方法3: 通过href包含restart的a标签
                if not try_again_clicked:
                    try:
                        try_again_link = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/restart')]"))
                        )
                        try_again_link.click()
                        print(f"[登录] ✅ 成功点击 'Try again' 链接 (方法3: restart href)")
                        try_again_clicked = True
                    except Exception as e:
                        print(f"[登录] 方法3失败: {str(e)}")
                
                # 方法4: 通过class和data-navigation属性
                if not try_again_clicked:
                    try:
                        try_again_link = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, "//a[@data-navigation='server' and contains(@class, 'WpHeLc')]"))
                        )
                        try_again_link.click()
                        print(f"[登录] ✅ 成功点击 'Try again' 链接 (方法4: class+data-navigation)")
                        try_again_clicked = True
                    except Exception as e:
                        print(f"[登录] 方法4失败: {str(e)}")
                
                if try_again_clicked:
                    time.sleep(5)  # 等待页面重新加载
                    # 重新检测页面状态
                    current_url = driver.current_url
                    print(f"[登录] 点击后的 URL: {current_url}")
                    
                    # 如果仍在rejected页面，则返回需要安全验证
                    if "signin/rejected" in current_url:
                        print(f"[登录] ⚠️ 点击后仍在身份验证失败页面")
                        return "identity_verification_failed", "无法验证身份，需要使用熟悉的设备或网络"
                    else:
                        print(f"[登录] ✅ 成功跳转，继续登录流程")
                        # 继续检测后续流程
                else:
                    print(f"[登录] ⚠️ 未找到 'Try again' 链接")
                    print(f"[登录] ⚠️ 这是一个无法验证身份的页面，需要使用熟悉的设备/网络")
                    return "identity_verification_failed", "无法验证身份，需要使用熟悉的设备或网络"
                    
            except Exception as e:
                print(f"[登录] 点击 'Try again' 链接失败: {str(e)}")
                return "identity_verification_failed", "无法验证身份，需要使用熟悉的设备或网络"
        
        # 检查是否跳转到登录页面（需要重新验证）
        if "signin" in current_url and "myaccount" not in current_url:
            print(f"[登录] 检测到跳转到登录验证页面，等待自动跳转...")
            time.sleep(10)  # 等待自动跳转
            current_url = driver.current_url
            print(f"[登录] 等待后的 URL: {current_url}")
            
            # 再次检查是否是 rejected 页面
            if "signin/rejected" in current_url:
                print(f"[登录] ⚠️ 跳转后仍是身份验证失败页面")
                print(f"[登录] 尝试点击 'Try again' 链接...")
                
                try:
                    # 尝试多种方式查找"Try again"链接
                    try_again_clicked = False
                    
                    # 方法1: 通过aria-label属性查找a标签（最准确）
                    try:
                        try_again_link = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, "//a[@aria-label='Try again']"))
                        )
                        try_again_link.click()
                        print(f"[登录] ✅ 成功点击 'Try again' 链接 (方法1: aria-label)")
                        try_again_clicked = True
                    except Exception as e:
                        print(f"[登录] 方法1失败: {str(e)}")
                    
                    # 方法2: 通过jsname属性查找
                    if not try_again_clicked:
                        try:
                            try_again_link = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, "//a[@jsname='hSRGPd']"))
                            )
                            try_again_link.click()
                            print(f"[登录] ✅ 成功点击 'Try again' 链接 (方法2: jsname)")
                            try_again_clicked = True
                        except Exception as e:
                            print(f"[登录] 方法2失败: {str(e)}")
                    
                    # 方法3: 通过href包含restart的a标签
                    if not try_again_clicked:
                        try:
                            try_again_link = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/restart')]"))
                            )
                            try_again_link.click()
                            print(f"[登录] ✅ 成功点击 'Try again' 链接 (方法3: restart href)")
                            try_again_clicked = True
                        except Exception as e:
                            print(f"[登录] 方法3失败: {str(e)}")
                    
                    # 方法4: 通过class和data-navigation属性
                    if not try_again_clicked:
                        try:
                            try_again_link = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, "//a[@data-navigation='server' and contains(@class, 'WpHeLc')]"))
                            )
                            try_again_link.click()
                            print(f"[登录] ✅ 成功点击 'Try again' 链接 (方法4: class+data-navigation)")
                            try_again_clicked = True
                        except Exception as e:
                            print(f"[登录] 方法4失败: {str(e)}")
                    
                    if try_again_clicked:
                        time.sleep(5)  # 等待页面重新加载
                        current_url = driver.current_url
                        print(f"[登录] 点击后的 URL: {current_url}")
                    else:
                        print(f"[登录] ⚠️ 未找到 'Try again' 链接")
                        print(f"[登录] ⚠️ 这是一个无法验证身份的页面，需要使用熟悉的设备/网络")
                        
                except Exception as e:
                    print(f"[登录] 点击 'Try again' 链接失败: {str(e)}")
                
                return "identity_verification_failed", "无法验证身份，需要使用熟悉的设备或网络"
        
        # 重新检测状态
        verification_state = detect_login_page_state(driver)
        print(f"[登录] 修改密码页面状态: {verification_state}")
        
        if verification_state == "identity_verification_failed":
            print(f"[登录] ⚠️ 无法验证身份")
            return "identity_verification_failed", "无法验证身份，需要使用熟悉的设备或网络"
        elif verification_state == "need_security_verification":
            print(f"[登录] ⚠️ 检测到需要安全验证")
            return "success_with_verification", "登录成功，但需要安全验证"
        else:
            print(f"[登录] ✅ 无需安全验证，登录成功")
            return "success", "登录成功"
    except Exception as e:
        print(f"[登录警告] 跳转修改密码页面失败: {str(e)}，默认为登录成功")
        return "success", "登录成功"


def handle_choose_account_page(driver, account_email):
    """处理选择账号页面 - 点击对应的账号
    
    Args:
        driver: Selenium WebDriver
        account_email: 要选择的账号邮箱
    
    Returns:
        str: 处理结果 "success"/"continue"/"failed"
    """
    try:
        print(f"[选择账号] 开始处理选择账号页面...")
        print(f"[选择账号] 要选择的账号: {account_email}")
        
        # 等待页面加载
        time.sleep(2)
        
        # 查找并点击对应的账号
        try:
            print(f"[选择账号] 查找账号元素...")
            account_element = None
            
            try:
                # 方式1: 通过包含邮箱文本的元素查找
                account_element = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, f"//*[contains(text(), '{account_email}')]"))
                )
                print(f"[选择账号] 通过邮箱文本找到账号元素")
            except:
                try:
                    # 方式2: 查找所有可能的账号div
                    elements = driver.find_elements(By.XPATH, "//div[@data-email or contains(@class, 'account')]")
                    for elem in elements:
                        if account_email.lower() in elem.text.lower():
                            account_element = elem
                            print(f"[选择账号] 通过遍历找到账号元素")
                            break
                except:
                    pass
            
            if account_element:
                # 滚动到元素
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", account_element)
                time.sleep(1)
                
                # 点击
                try:
                    account_element.click()
                    print(f"[选择账号] 已点击账号")
                except:
                    driver.execute_script("arguments[0].click();", account_element)
                    print(f"[选择账号] 已点击账号（JS方式）")
                
                # 等待页面跳转
                time.sleep(5)
                
                # 检查结果
                current_url = driver.current_url
                print(f"[选择账号] 点击后 URL: {current_url}")
                
                if "myaccount.google.com" in current_url:
                    print(f"[选择账号] ✅ 选择成功，已登录")
                    return "success"
                else:
                    print(f"[选择账号] 选择完成，继续后续流程")
                    return "continue"
            else:
                print(f"[选择账号错误] 未找到对应的账号: {account_email}")
                # 如果找不到账号，可能需要点击"Use another account"
                try:
                    use_another = driver.find_element(By.XPATH, "//div[contains(text(), 'Use another account') or contains(text(), '使用其他账号')]")
                    if use_another:
                        print(f"[选择账号] 找不到对应账号，点击'Use another account'")
                        use_another.click()
                        time.sleep(3)
                        return "continue"
                except:
                    pass
                return "account_not_found"
                
        except Exception as e:
            error_msg = f"查找或点击账号失败: {str(e)}"
            print(f"[选择账号错误] {error_msg}")
            import traceback
            traceback.print_exc()
            return "click_failed"
            
    except Exception as e:
        error_msg = f"处理选择账号页面失败: {str(e)}"
        print(f"[选择账号错误] {error_msg}")
        import traceback
        traceback.print_exc()
        return "error"


def handle_home_address_page(driver):
    """处理设置住址页面 - 点击Skip跳过
    
    Args:
        driver: Selenium WebDriver
    
    Returns:
        str: 处理结果 "success"/"continue"/"failed"
    """
    try:
        print(f"[住址设置] 开始处理设置住址页面...")
        
        # 等待页面加载
        time.sleep(2)
        
        # 查找并点击Skip按钮
        try:
            print(f"[住址设置] 查找Skip按钮...")
            skip_button = None
            
            try:
                # 方式1: 通过文本查找
                skip_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Skip') or contains(text(), '跳过')]"))
                )
                print(f"[住址设置] 通过文本找到Skip按钮")
            except:
                try:
                    # 方式2: 查找所有button，找包含skip的
                    buttons = driver.find_elements(By.TAG_NAME, "button")
                    for btn in buttons:
                        if btn.is_displayed() and ('skip' in btn.text.lower() or '跳过' in btn.text):
                            skip_button = btn
                            print(f"[住址设置] 通过遍历找到Skip按钮")
                            break
                except:
                    pass
            
            if skip_button:
                # 滚动到按钮
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", skip_button)
                time.sleep(1)
                
                # 点击
                try:
                    skip_button.click()
                    print(f"[住址设置] 已点击Skip按钮")
                except:
                    driver.execute_script("arguments[0].click();", skip_button)
                    print(f"[住址设置] 已点击Skip按钮（JS方式）")
                
                # 等待页面跳转
                time.sleep(5)
                
                # 检查结果
                current_url = driver.current_url
                print(f"[住址设置] 跳过后 URL: {current_url}")
                
                if "myaccount.google.com" in current_url:
                    print(f"[住址设置] ✅ 跳过成功，已登录")
                    return "success"
                else:
                    print(f"[住址设置] 跳过完成，继续后续流程")
                    return "continue"
            else:
                print(f"[住址设置错误] 未找到Skip按钮")
                return "skip_button_not_found"
                
        except Exception as e:
            error_msg = f"查找或点击Skip按钮失败: {str(e)}"
            print(f"[住址设置错误] {error_msg}")
            import traceback
            traceback.print_exc()
            return "click_failed"
            
    except Exception as e:
        error_msg = f"处理设置住址页面失败: {str(e)}"
        print(f"[住址设置错误] {error_msg}")
        import traceback
        traceback.print_exc()
        return "error"


def get_available_phone(account_id=None):
    """获取一个可用的手机号（优先使用已绑定的，否则获取新的）
    
    Args:
        account_id: 账号ID，如果提供则优先使用该账号已绑定的手机号
    
    Returns:
        Phone: 手机号对象，失败返回 None
    """
    try:
        # 如果提供了账号ID，优先检查是否已绑定手机号
        if account_id:
            account = Account.query.get(account_id)
            if account and account.phone_id:
                bound_phone = Phone.query.get(account.phone_id)
                if bound_phone:
                    print(f"[手机号] 使用账号已绑定的手机号: {bound_phone.phone_number}")
                    # 检查手机号是否过期
                    now = datetime.now()
                    if bound_phone.expire_time and bound_phone.expire_time < now:
                        print(f"[手机号警告] 绑定的手机号已过期，将获取新的")
                    else:
                        # 如果有接码URL，优先使用绑定的
                        if bound_phone.sms_url:
                            return bound_phone
                        else:
                            print(f"[手机号警告] 绑定的手机号没有配置接码URL，将获取新的")
        
        # 如果没有绑定或绑定的不可用，查找新的可用手机号
        now = datetime.now()
        phone = Phone.query.filter(
            Phone.status == False,
            db.or_(Phone.expire_time == None, Phone.expire_time > now)
        ).first()
        
        if phone:
            print(f"[手机号] 找到新的可用手机号: {phone.phone_number}")
            return phone
        else:
            print(f"[手机号错误] 没有可用的手机号")
            return None
    except Exception as e:
        print(f"[手机号错误] 获取手机号失败: {str(e)}")
        return None


def get_sms_code(sms_url, max_retries=12, interval=10, request_time=None):
    """从接码URL获取验证码
    
    Args:
        sms_url: 接码URL
        max_retries: 最大重试次数，默认12次
        interval: 重试间隔（秒），默认10秒
        request_time: 请求验证码的时间（datetime对象），只获取此时间之后的验证码
    
    Returns:
        str: 验证码，如 "123456"，失败返回 None
    """
    from datetime import datetime
    
    try:
        print(f"[验证码] 开始从接码URL获取验证码...")
        print(f"[验证码] URL: {sms_url}")
        
        # 如果没有传入请求时间，使用当前时间减去5秒作为基准
        if request_time is None:
            request_time = datetime.now()
            print(f"[验证码] 未指定请求时间，使用当前时间: {request_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"[验证码] 只获取 {request_time.strftime('%Y-%m-%d %H:%M:%S')} 之后的验证码")
        
        for attempt in range(max_retries):
            try:
                print(f"[验证码] 第 {attempt + 1}/{max_retries} 次尝试...")
                
                # 请求接码URL
                response = requests.get(sms_url, timeout=30)
                if response.status_code == 200:
                    content = response.text
                    print(f"[验证码] 获取到内容: {content[:300] if len(content) > 300 else content}")
                    
                    # 尝试解析JSON格式的响应
                    try:
                        data = response.json()
                        if isinstance(data, dict) and 'messages' in data:
                            messages = data.get('messages', [])
                            print(f"[验证码] 检测到JSON格式，共 {len(messages)} 条消息")
                            
                            # 遍历消息，找到请求时间之后的最新验证码
                            for msg_item in messages:
                                msg_text = msg_item.get('msg', '')
                                rec_time_str = msg_item.get('rec_time', '')
                                
                                # 解析消息时间
                                try:
                                    msg_time = datetime.strptime(rec_time_str, '%Y-%m-%d %H:%M:%S')
                                except:
                                    print(f"[验证码] 无法解析消息时间: {rec_time_str}")
                                    continue
                                
                                # 检查消息时间是否在请求时间之后
                                if msg_time >= request_time:
                                    # 提取验证码
                                    match = re.search(r'G-(\d{5,6})', msg_text)
                                    if match:
                                        code = match.group(1)
                                        print(f"[验证码] ✅ 找到有效验证码: {code} (时间: {rec_time_str})")
                                        return code
                                else:
                                    print(f"[验证码] 跳过旧消息 (时间: {rec_time_str}，早于请求时间)")
                            
                            print(f"[验证码] 未找到请求时间之后的有效验证码，继续等待...")
                        else:
                            # 非标准JSON格式，使用旧的正则匹配方式
                            match = re.search(r'G-(\d{5,6})', content)
                            if match:
                                code = match.group(1)
                                print(f"[验证码] ✅ 成功获取验证码: {code}")
                                return code
                            else:
                                print(f"[验证码] 未找到验证码格式 G-XXXXXX，继续等待...")
                    except (ValueError, TypeError):
                        # 不是JSON格式，使用旧的正则匹配方式
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
        
        # 1. 获取可用手机号（优先使用已绑定的）
        phone = get_available_phone(account_id)
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
            
            # 记录点击下一步的时间（用于过滤旧验证码）
            from datetime import datetime
            sms_request_time = datetime.now()
            print(f"[手机验证] 记录请求时间: {sms_request_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
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
        sms_code = get_sms_code(phone.sms_url, max_retries=12, interval=10, request_time=sms_request_time)
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
                    if not phone.status:
                        phone.status = True
                        print(f"[手机验证] 标记手机号为已使用")
                    
                    # 绑定手机号到账号（如果还未绑定）
                    account = Account.query.get(account_id)
                    if account and account.phone_id != phone.id:
                        account.phone_id = phone.id
                        print(f"[手机验证] 已绑定手机号到账号")
                    
                    db.session.commit()
                    
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
                    # 标记手机号为已使用
                    if not phone.status:
                        phone.status = True
                        print(f"[手机验证] 标记手机号为已使用")
                    
                    # 绑定手机号到账号（如果还未绑定）
                    account = Account.query.get(account_id)
                    if account and account.phone_id != phone.id:
                        account.phone_id = phone.id
                        print(f"[手机验证] 已绑定手机号到账号")
                    
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


def handle_phone_consent_page(driver, account_id):
    """处理需要点击Send发送验证码的手机验证页面（ipp/consent页面）
    
    这个页面已经显示了手机号，只需要点击Send按钮发送验证码，然后输入验证码
    
    Args:
        driver: Selenium WebDriver
        account_id: 账号ID
    
    Returns:
        str: 处理结果 "success"/"no_phone"/"failed"
    """
    try:
        print(f"[手机验证-Send] 开始处理需要点击Send的手机验证页面...")
        
        # 1. 获取可用手机号（用于获取验证码）
        phone = get_available_phone(account_id)
        if not phone:
            print(f"[手机验证-Send错误] 没有可用的手机号")
            return "no_phone"
        
        if not phone.sms_url:
            print(f"[手机验证-Send错误] 手机号 {phone.phone_number} 没有配置接码URL")
            return "no_sms_url"
        
        # 2. 查找并点击Send按钮
        try:
            print(f"[手机验证-Send] 查找Send按钮...")
            
            # 尝试多种方式查找Send按钮
            send_button = None
            button_selectors = [
                "//button[contains(., 'Send')]",
                "//button[.//span[contains(text(), 'Send')]]",
                "//span[contains(text(), 'Send')]/ancestor::button",
                "//div[@role='button' and contains(., 'Send')]",
                "//button[@jsname='LgbsSe']",
                "//button[contains(@class, 'send')]",
            ]
            
            for selector in button_selectors:
                try:
                    send_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    if send_button:
                        print(f"[手机验证-Send] 找到Send按钮，使用选择器: {selector}")
                        break
                except:
                    continue
            
            if not send_button:
                print(f"[手机验证-Send错误] 未找到Send按钮")
                return "send_button_not_found"
            
            # 记录点击Send的时间（用于过滤旧验证码）
            from datetime import datetime
            sms_request_time = datetime.now()
            print(f"[手机验证-Send] 记录请求时间: {sms_request_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 点击Send按钮
            try:
                send_button.click()
                print(f"[手机验证-Send] 已点击Send按钮")
            except:
                driver.execute_script("arguments[0].click();", send_button)
                print(f"[手机验证-Send] 已点击Send按钮（JS方式）")
            
            # 等待验证码发送
            time.sleep(5)
            
        except Exception as e:
            error_msg = f"点击Send按钮失败: {str(e)}"
            print(f"[手机验证-Send错误] {error_msg}")
            import traceback
            traceback.print_exc()
            return "click_send_failed"
        
        # 3. 获取验证码
        print(f"[手机验证-Send] 开始获取验证码...")
        sms_code = get_sms_code(phone.sms_url, max_retries=12, interval=10, request_time=sms_request_time)
        if not sms_code:
            print(f"[手机验证-Send错误] 获取验证码失败")
            return "sms_code_failed"
        
        # 4. 查找并输入验证码
        try:
            print(f"[手机验证-Send] 查找验证码输入框...")
            
            # 尝试多种方式查找验证码输入框
            code_input = None
            input_selectors = [
                "//input[@type='tel']",
                "//input[@id='code']",
                "//input[contains(@name, 'code')]",
                "//input[contains(@name, 'pin')]",
                "//input[@type='text' and contains(@aria-label, 'code')]",
                "//input[@autocomplete='one-time-code']",
            ]
            
            for selector in input_selectors:
                try:
                    code_input = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    if code_input:
                        print(f"[手机验证-Send] 找到验证码输入框，使用选择器: {selector}")
                        break
                except:
                    continue
            
            if not code_input:
                print(f"[手机验证-Send错误] 未找到验证码输入框")
                return "code_input_not_found"
            
            print(f"[手机验证-Send] 输入验证码: {sms_code}")
            code_input.clear()
            code_input.send_keys(sms_code)
            time.sleep(2)
            
            # 点击"下一步"或"验证"按钮
            print(f"[手机验证-Send] 查找并点击验证按钮...")
            try:
                verify_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, 
                        "//button[@type='button']//span[contains(text(), 'Next') or contains(text(), '下一步') or contains(text(), 'Verify') or contains(text(), '验证')]"
                    ))
                )
                verify_button.click()
                print(f"[手机验证-Send] 已点击验证按钮")
            except:
                # 有些页面可能自动提交
                print(f"[手机验证-Send] 未找到验证按钮，可能自动提交")
            
            # 等待页面跳转
            time.sleep(5)
            
            # 5. 检查结果
            current_url = driver.current_url
            print(f"[手机验证-Send] 验证后 URL: {current_url}")
            
            if "myaccount.google.com" in current_url:
                print(f"[手机验证-Send] ✅ 验证成功，已登录")
                
                # 更新数据库
                try:
                    if not phone.status:
                        phone.status = True
                        print(f"[手机验证-Send] 标记手机号为已使用")
                    
                    account = Account.query.get(account_id)
                    if account and account.phone_id != phone.id:
                        account.phone_id = phone.id
                        print(f"[手机验证-Send] 已绑定手机号到账号")
                    
                    db.session.commit()
                except Exception as e:
                    print(f"[手机验证-Send警告] 更新数据库失败: {str(e)}")
                
                return "success"
            else:
                # 检查是否还在验证页面（可能验证码错误）
                try:
                    error_element = driver.find_element(By.XPATH, "//span[contains(text(), 'wrong') or contains(text(), 'incorrect') or contains(text(), '错误')]")
                    if error_element:
                        print(f"[手机验证-Send错误] 验证码错误")
                        return "code_error"
                except:
                    pass
                
                print(f"[手机验证-Send] 验证完成，继续后续流程")
                
                # 更新数据库
                try:
                    if not phone.status:
                        phone.status = True
                        print(f"[手机验证-Send] 标记手机号为已使用")
                    
                    account = Account.query.get(account_id)
                    if account and account.phone_id != phone.id:
                        account.phone_id = phone.id
                        print(f"[手机验证-Send] 已绑定手机号到账号")
                    
                    db.session.commit()
                except Exception as e:
                    print(f"[手机验证-Send警告] 更新数据库失败: {str(e)}")
                
                return "continue"
                
        except Exception as e:
            error_msg = f"输入验证码失败: {str(e)}"
            print(f"[手机验证-Send错误] {error_msg}")
            import traceback
            traceback.print_exc()
            return "input_code_failed"
            
    except Exception as e:
        error_msg = f"处理手机验证（Send页面）失败: {str(e)}"
        print(f"[手机验证-Send错误] {error_msg}")
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
        elif "ipp/consent" in current_url:
            print(f"[密码页面] 检测到需要点击Send发送验证码的手机验证页面")
            return "need_phone_consent"
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
        # === 步骤1: 等待浏览器完全启动 ===
        print(f"[登录-步骤1] 等待浏览器完全启动...")
        if account_id:
            add_login_log(account_id, None, 'login', 'info', '步骤1: 等待浏览器完全启动')
        time.sleep(2)
        
        # === 步骤2: 导航到Google账号页面 ===
        print(f"[登录-步骤2] 正在访问 Google 账号页面...")
        if account_id:
            add_login_log(account_id, None, 'login', 'info', '步骤2: 访问 Google 账号页面')
        try:
            current_url_before = driver.current_url
            print(f"[登录-步骤2] 导航前URL: {current_url_before}")
            
            driver.get('https://accounts.google.com/')
            print(f"[登录-步骤2] 已发送导航请求，等待页面加载...")
            
            # 等待页面加载
            time.sleep(5)
            
            current_url_after = driver.current_url
            print(f"[登录-步骤2] 导航后URL: {current_url_after}")
            
            # 如果仍然是空白页，可能是代理或网络问题
            if current_url_after == "about:blank" or current_url_after == "data:,":
                print(f"[登录-步骤2-警告] 页面仍然是空白，可能是网络或代理问题")
                print(f"[登录-步骤2] 再次尝试导航...")
                if account_id:
                    add_login_log(account_id, None, 'login', 'warning', '步骤2: 页面空白，重试导航')
                driver.get('https://accounts.google.com/')
                time.sleep(5)
                current_url_retry = driver.current_url
                print(f"[登录-步骤2] 重试后URL: {current_url_retry}")
                
                if current_url_retry == "about:blank" or current_url_retry == "data:,":
                    error_msg = "步骤2失败: 无法访问Google登录页面，请检查网络连接和代理设置"
                    print(f"[登录-步骤2-错误] {error_msg}")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'failed', error_msg)
                    return "failed", error_msg
            
            if account_id:
                add_login_log(account_id, None, 'login', 'success', '步骤2完成: 成功访问Google登录页面')
            
        except Exception as e:
            error_msg = f"步骤2失败: 访问页面失败，浏览器可能已关闭: {str(e)}"
            print(f"[登录-步骤2-错误] {error_msg}")
            import traceback
            traceback.print_exc()
            if account_id:
                add_login_log(account_id, None, 'login', 'failed', error_msg)
            return "failed", error_msg
        
        # === 步骤3: 循环处理登录流程（状态机模式） ===
        print(f"[登录-步骤3] 开始登录状态机流程...")
        if account_id:
            add_login_log(account_id, None, 'login', 'info', '步骤3: 开始登录状态机流程')
        
        max_attempts = 8
        for attempt in range(max_attempts):
            # 检查是否超时
            elapsed_time = time_module.time() - start_time
            if elapsed_time > max_total_time:
                error_msg = f"步骤3失败: 登录流程超过 {max_total_time} 秒"
                print(f"[登录-步骤3-超时] {error_msg}")
                if account_id:
                    add_login_log(account_id, None, 'login', 'failed', error_msg)
                return "failed", error_msg
            
            print(f"\n[登录-步骤3.{attempt + 1}] ===== 第 {attempt + 1} 次状态检测 =====")
            if account_id:
                add_login_log(account_id, None, 'login', 'info', f'步骤3.{attempt + 1}: 进行第{attempt + 1}次状态检测')
            
            try:
                # 先输出当前URL
                try:
                    current_url = driver.current_url
                    print(f"[登录-步骤3.{attempt + 1}] 当前 URL: {current_url}")
                except:
                    pass
                
                current_state = detect_login_page_state(driver)
                print(f"[登录-步骤3.{attempt + 1}] 检测到状态: {current_state}")
                if account_id:
                    add_login_log(account_id, None, 'login', 'info', f'步骤3.{attempt + 1}: 检测到状态 [{current_state}]')
            except Exception as e:
                error_msg = f"步骤3.{attempt + 1}失败: 检测页面状态失败，浏览器可能已关闭: {str(e)}"
                print(f"[登录-步骤3.{attempt + 1}-错误] {error_msg}")
                if account_id:
                    add_login_log(account_id, None, 'login', 'failed', error_msg)
                return "failed", error_msg
            
            if current_state == "logged_in":
                # 登录成功后，检测安全验证
                print(f"[登录-步骤3.{attempt + 1}] ✅ 检测到已登录状态")
                if account_id:
                    add_login_log(account_id, None, 'login', 'success', f'步骤3.{attempt + 1}: 检测到已登录状态，验证安全检查')
                return check_password_page_security_verification(driver)
            
            elif current_state == "identity_verification_failed":
                # 无法验证身份
                error_msg = f"步骤3.{attempt + 1}失败: 无法验证身份，需要使用熟悉的设备或网络环境"
                print(f"[登录-步骤3.{attempt + 1}] ⚠️ {error_msg}")
                if account_id:
                    add_login_log(account_id, None, 'login', 'failed', error_msg)
                return "identity_verification_failed", "无法验证身份，需要使用熟悉的设备或网络"
            
            elif current_state == "need_security_verification":
                # 登录成功但需要安全验证
                msg = f"步骤3.{attempt + 1}: 登录成功，但需要安全验证（可能需要原设备或其他验证方式）"
                print(f"[登录-步骤3.{attempt + 1}] ⚠️ {msg}")
                if account_id:
                    add_login_log(account_id, None, 'login', 'success', msg)
                return "success_with_verification", "登录成功，但需要安全验证"
            
            elif current_state == "choose_account":
                # 处理选择账号页面
                print(f"[登录-步骤3.{attempt + 1}] 开始处理选择账号页面...")
                if account_id:
                    add_login_log(account_id, None, 'login', 'info', f'步骤3.{attempt + 1}: 处理选择账号页面')
                status = handle_choose_account_page(driver, account)
                
                if status == "success":
                    # 选择账号成功后，检测安全验证
                    print(f"[登录-步骤3.{attempt + 1}] ✅ 选择账号成功")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'success', f'步骤3.{attempt + 1}: 选择账号成功')
                    return check_password_page_security_verification(driver)
                elif status == "continue":
                    # 继续下一轮检测
                    print(f"[登录-步骤3.{attempt + 1}] 选择账号完成，继续检测后续状态...")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'info', f'步骤3.{attempt + 1}: 选择账号完成，继续')
                    time.sleep(2)
                    continue
                elif status == "account_not_found":
                    # 如果找不到账号，继续流程（可能会到输入邮箱页面）
                    print(f"[登录-步骤3.{attempt + 1}] 未找到对应账号，继续正常登录流程...")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'info', f'步骤3.{attempt + 1}: 未找到对应账号，继续')
                    time.sleep(2)
                    continue
                else:
                    error_msg = f"步骤3.{attempt + 1}失败: 选择账号失败: {status}"
                    print(f"[登录-步骤3.{attempt + 1}-错误] {error_msg}")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'failed', error_msg)
                    return "failed", error_msg
            
            elif current_state == "need_email":
                # 处理邮箱输入页面
                print(f"[登录-步骤3.{attempt + 1}] 开始处理邮箱输入...")
                if account_id:
                    add_login_log(account_id, None, 'login', 'info', f'步骤3.{attempt + 1}: 处理邮箱输入页面')
                try:
                    # 双重检查：确保不是"Verify it's you"页面
                    try:
                        verify_title = driver.find_element(By.XPATH, "//h1[contains(text(), \"Verify it's you\") or contains(text(), '验证您的身份')]")
                        if verify_title and verify_title.is_displayed():
                            print(f"[登录-步骤3.{attempt + 1}-警告] 误检测为need_email，实际是Verify it's you页面，重新检测...")
                            if account_id:
                                add_login_log(account_id, None, 'login', 'warning', f'步骤3.{attempt + 1}: 页面误检测，重新检测')
                            time.sleep(2)
                            continue
                    except:
                        pass
                    
                    print(f"[登录-步骤3.{attempt + 1}] 输入邮箱: {account}")
                    email_input = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "identifierId"))
                    )
                    
                    # 检查输入框是否可编辑
                    if email_input.get_attribute("readonly") or email_input.get_attribute("disabled"):
                        print(f"[登录-步骤3.{attempt + 1}-警告] 邮箱输入框不可编辑，重新检测状态...")
                        if account_id:
                            add_login_log(account_id, None, 'login', 'warning', f'步骤3.{attempt + 1}: 邮箱输入框不可编辑')
                        time.sleep(2)
                        continue
                    
                    email_input.clear()
                    email_input.send_keys(account)
                    print(f"[登录-步骤3.{attempt + 1}] 已输入邮箱")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'info', f'步骤3.{attempt + 1}: 已输入邮箱')
                    
                    # 点击下一步
                    print(f"[登录-步骤3.{attempt + 1}] 点击邮箱下一步按钮")
                    next_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.ID, "identifierNext"))
                    )
                    next_button.click()
                    if account_id:
                        add_login_log(account_id, None, 'login', 'info', f'步骤3.{attempt + 1}: 已点击下一步，等待页面跳转')
                    
                    # 等待页面跳转
                    print(f"[登录-步骤3.{attempt + 1}] 等待页面跳转...")
                    time.sleep(5)
                    
                    # 继续下一次循环检测
                    continue
                    
                except Exception as e:
                    error_msg = f"步骤3.{attempt + 1}警告: 输入邮箱失败: {str(e)}"
                    print(f"[登录-步骤3.{attempt + 1}-错误] {error_msg}")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'warning', error_msg)
                    # 如果输入失败，尝试重新检测状态而不是直接返回失败
                    print(f"[登录-步骤3.{attempt + 1}] 尝试重新检测页面状态...")
                    time.sleep(2)
                    continue
            
            elif current_state == "need_password":
                # 处理密码页面
                print(f"[登录-步骤3.{attempt + 1}] 开始处理密码输入...")
                if account_id:
                    add_login_log(account_id, None, 'login', 'info', f'步骤3.{attempt + 1}: 处理密码输入页面')
                status = handle_password_page(driver, password)
                
                if status == "success":
                    print(f"[登录-步骤3.{attempt + 1}] ✅ 密码输入成功")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'success', f'步骤3.{attempt + 1}: 密码输入成功')
                    return check_password_page_security_verification(driver)
                elif status == "need_phone":
                    # 不直接返回，而是继续循环让下一轮处理手机验证
                    print(f"[登录-步骤3.{attempt + 1}] 密码处理后需要手机验证，继续下一轮循环处理...")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'info', f'步骤3.{attempt + 1}: 需要手机验证，继续')
                    time.sleep(2)
                    continue
                elif status == "need_2fa":
                    msg = f"步骤3.{attempt + 1}: 需要2FA验证"
                    print(f"[登录-步骤3.{attempt + 1}] {msg}")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'info', msg)
                    return "need_2fa", "需要2FA验证"
                elif status == "disabled":
                    error_msg = f"步骤3.{attempt + 1}失败: 账号被禁用"
                    print(f"[登录-步骤3.{attempt + 1}] {error_msg}")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'failed', error_msg)
                    return "disabled", "账号被禁用"
                elif status == "password_error":
                    error_msg = f"步骤3.{attempt + 1}失败: 密码错误"
                    print(f"[登录-步骤3.{attempt + 1}] {error_msg}")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'failed', error_msg)
                    return "password_error", "密码错误"
                elif status == "error":
                    error_msg = f"步骤3.{attempt + 1}失败: 密码处理错误"
                    print(f"[登录-步骤3.{attempt + 1}] {error_msg}")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'failed', error_msg)
                    return "failed", "密码处理错误"
                else:
                    # 未知状态，继续循环检测
                    print(f"[登录-步骤3.{attempt + 1}] 密码处理后返回未知状态: {status}，继续检测...")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'warning', f'步骤3.{attempt + 1}: 密码处理返回未知状态 [{status}]')
                    time.sleep(2)
                    continue
            
            elif current_state == "verify_identity":
                # 处理 "Verify it's you" 验证身份页面
                print(f"[登录-步骤3.{attempt + 1}] 开始处理验证身份页面...")
                if account_id:
                    add_login_log(account_id, None, 'login', 'info', f'步骤3.{attempt + 1}: 处理验证身份页面')
                status = handle_verify_identity_page(driver, backup_email)
                
                if status == "success":
                    print(f"[登录-步骤3.{attempt + 1}] ✅ 验证身份成功")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'success', f'步骤3.{attempt + 1}: 验证身份成功')
                    return check_password_page_security_verification(driver)
                elif status == "continue":
                    # 继续下一轮检测
                    print(f"[登录-步骤3.{attempt + 1}] 验证身份完成，继续检测后续状态...")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'info', f'步骤3.{attempt + 1}: 验证身份完成，继续')
                    time.sleep(2)
                    continue
                elif status == "no_backup_email":
                    error_msg = f"步骤3.{attempt + 1}失败: 需要辅助邮箱验证，但账号未设置辅助邮箱"
                    print(f"[登录-步骤3.{attempt + 1}] {error_msg}")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'failed', error_msg)
                    return "failed", "需要辅助邮箱验证，但账号未设置辅助邮箱"
                else:
                    error_msg = f"步骤3.{attempt + 1}失败: 验证身份失败: {status}"
                    print(f"[登录-步骤3.{attempt + 1}] {error_msg}")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'failed', error_msg)
                    return "failed", error_msg
            
            elif current_state == "passkey_enrollment":
                # 处理 Passkey 注册页面
                print(f"[登录-步骤3.{attempt + 1}] 开始处理Passkey注册页面...")
                if account_id:
                    add_login_log(account_id, None, 'login', 'info', f'步骤3.{attempt + 1}: 处理Passkey注册页面')
                status = handle_passkey_enrollment_page(driver)
                
                if status == "success":
                    print(f"[登录-步骤3.{attempt + 1}] ✅ Passkey处理成功")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'success', f'步骤3.{attempt + 1}: Passkey处理成功')
                    return check_password_page_security_verification(driver)
                elif status == "continue":
                    # 继续下一轮检测
                    print(f"[登录-步骤3.{attempt + 1}] Passkey 跳过完成，继续检测后续状态...")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'info', f'步骤3.{attempt + 1}: Passkey跳过，继续')
                    time.sleep(2)
                    continue
                else:
                    error_msg = f"步骤3.{attempt + 1}失败: Passkey 页面处理失败: {status}"
                    print(f"[登录-步骤3.{attempt + 1}] {error_msg}")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'failed', error_msg)
                    return "failed", error_msg
            
            elif current_state == "verify_click_next":
                # 处理需要点击Next的 "Verify it's you" 页面
                status = handle_verify_click_next_page(driver)
                
                if status == "success":
                    return check_password_page_security_verification(driver)
                elif status == "need_captcha":
                    # 进入人机验证流程
                    print(f"[登录] 检测到人机验证，开始处理...")
                    captcha_status = handle_captcha_page(driver)
                    
                    if captcha_status == "success":
                        return check_password_page_security_verification(driver)
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
                    return check_password_page_security_verification(driver)
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
            
            elif current_state == "recovery_options":
                # 处理恢复选项页面（添加手机号）
                print(f"[登录] 开始处理恢复选项页面...")
                status = handle_recovery_options_page(driver, account_id)
                
                if status == "success":
                    return check_password_page_security_verification(driver)
                elif status == "continue":
                    # 继续下一轮检测
                    print(f"[登录] 恢复选项设置完成，继续检测后续状态...")
                    time.sleep(2)
                    continue
                elif status == "no_phone":
                    return "failed", "需要设置恢复手机号，但没有可用的手机号"
                else:
                    return "failed", f"恢复选项设置失败: {status}"
            
            elif current_state == "home_address":
                # 处理设置住址页面
                print(f"[登录] 开始处理设置住址页面...")
                status = handle_home_address_page(driver)
                
                if status == "success":
                    # 住址设置成功后，检测安全验证
                    return check_password_page_security_verification(driver)
                elif status == "continue":
                    # 继续下一轮检测
                    print(f"[登录] 设置住址跳过完成，继续检测后续状态...")
                    time.sleep(2)
                    continue
                else:
                    return "failed", f"设置住址页面处理失败: {status}"
            
            elif current_state == "need_phone":
                # 处理手机号验证
                print(f"[登录-步骤3.{attempt + 1}] 开始处理手机号验证...")
                if account_id:
                    add_login_log(account_id, None, 'login', 'info', f'步骤3.{attempt + 1}: 处理手机号验证')
                status = handle_phone_verification(driver, account_id)
                
                if status == "success":
                    print(f"[登录-步骤3.{attempt + 1}] ✅ 手机号验证成功")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'success', f'步骤3.{attempt + 1}: 手机号验证成功')
                    return check_password_page_security_verification(driver)
                elif status == "continue":
                    # 继续下一轮检测
                    print(f"[登录-步骤3.{attempt + 1}] 手机号验证完成，继续检测后续状态...")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'info', f'步骤3.{attempt + 1}: 手机号验证完成，继续')
                    time.sleep(2)
                    continue
                elif status == "no_phone":
                    error_msg = f"步骤3.{attempt + 1}失败: 需要手机号验证，但没有可用的手机号"
                    print(f"[登录-步骤3.{attempt + 1}] {error_msg}")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'failed', error_msg)
                    return "failed", "需要手机号验证，但没有可用的手机号"
                elif status == "no_sms_url":
                    error_msg = f"步骤3.{attempt + 1}失败: 手机号没有配置接码URL"
                    print(f"[登录-步骤3.{attempt + 1}] {error_msg}")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'failed', error_msg)
                    return "failed", "手机号没有配置接码URL"
                elif status == "sms_code_failed":
                    error_msg = f"步骤3.{attempt + 1}失败: 获取验证码失败（超过12次重试）"
                    print(f"[登录-步骤3.{attempt + 1}] {error_msg}")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'failed', error_msg)
                    return "failed", "获取验证码失败（超过12次重试）"
                else:
                    error_msg = f"步骤3.{attempt + 1}失败: 手机号验证失败: {status}"
                    print(f"[登录-步骤3.{attempt + 1}] {error_msg}")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'failed', error_msg)
                    return "failed", error_msg
            
            elif current_state == "need_phone_consent":
                # 处理需要点击Send发送验证码的手机验证页面（ipp/consent）
                print(f"[登录] 开始处理需要点击Send的手机验证页面...")
                status = handle_phone_consent_page(driver, account_id)
                
                if status == "success":
                    return check_password_page_security_verification(driver)
                elif status == "continue":
                    # 继续下一轮检测
                    print(f"[登录] 手机验证（Send页面）完成，继续检测后续状态...")
                    time.sleep(2)
                    continue
                elif status == "no_phone":
                    return "failed", "需要手机号验证，但没有可用的手机号"
                elif status == "no_sms_url":
                    return "failed", "手机号没有配置接码URL"
                elif status == "sms_code_failed":
                    return "failed", "获取验证码失败（超过12次重试）"
                elif status == "send_button_not_found":
                    return "failed", "未找到Send按钮"
                else:
                    return "failed", f"手机验证（Send页面）失败: {status}"
            
            elif current_state == "need_appeal":
                # 处理申诉流程
                print(f"[登录-步骤3.{attempt + 1}] 检测到需要申诉，开始处理申诉流程...")
                if account_id:
                    add_login_log(account_id, None, 'login', 'info', f'步骤3.{attempt + 1}: 检测到需要申诉，开始处理')
                status = handle_appeal_flow(driver, backup_email)
                
                if status == "success":
                    print(f"[登录-步骤3.{attempt + 1}] ✅ 申诉提交成功")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'success', f'步骤3.{attempt + 1}: 申诉提交成功')
                    return "appeal_success", "申诉提交成功，请等待审核"
                elif status == "no_backup_email":
                    error_msg = f"步骤3.{attempt + 1}失败: 需要申诉但账号未设置辅助邮箱"
                    print(f"[登录-步骤3.{attempt + 1}] {error_msg}")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'failed', error_msg)
                    return "appeal_failed", "需要申诉但账号未设置辅助邮箱"
                elif status == "no_appeal_text":
                    error_msg = f"步骤3.{attempt + 1}失败: 无法获取申诉文案，请检查配置"
                    print(f"[登录-步骤3.{attempt + 1}] {error_msg}")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'failed', error_msg)
                    return "appeal_failed", "无法获取申诉文案，请检查配置"
                else:
                    error_msg = f"步骤3.{attempt + 1}失败: 申诉流程失败: {status}"
                    print(f"[登录-步骤3.{attempt + 1}] {error_msg}")
                    if account_id:
                        add_login_log(account_id, None, 'login', 'failed', error_msg)
                    return "appeal_failed", error_msg
            
            elif current_state == "need_2fa":
                msg = f"步骤3.{attempt + 1}: 需要2FA验证"
                print(f"[登录-步骤3.{attempt + 1}] {msg}")
                if account_id:
                    add_login_log(account_id, None, 'login', 'info', msg)
                return "need_2fa", "需要2FA验证"
            
            elif current_state == "disabled":
                error_msg = f"步骤3.{attempt + 1}失败: 账号被禁用（无法申诉）"
                print(f"[登录-步骤3.{attempt + 1}] {error_msg}")
                if account_id:
                    add_login_log(account_id, None, 'login', 'failed', error_msg)
                return "disabled", "账号被禁用（无法申诉）"
            
            elif current_state == "password_error":
                error_msg = f"步骤3.{attempt + 1}失败: 密码错误"
                print(f"[登录-步骤3.{attempt + 1}] {error_msg}")
                if account_id:
                    add_login_log(account_id, None, 'login', 'failed', error_msg)
                return "password_error", "密码错误"
            
            else:
                # 未知状态，等待后继续
                print(f"[登录-步骤3.{attempt + 1}] 未知状态: {current_state}，等待后重新检测...")
                if account_id:
                    add_login_log(account_id, None, 'login', 'warning', f'步骤3.{attempt + 1}: 未知状态 [{current_state}]，继续检测')
                time.sleep(3)
                continue
        
        # 超过最大尝试次数
        final_url = driver.current_url
        error_msg = f"步骤3失败: 登录流程超过最大尝试次数({max_attempts}次)，最终 URL: {final_url}"
        print(f"[登录-步骤3-错误] {error_msg}")
        if account_id:
            add_login_log(account_id, None, 'login', 'failed', error_msg)
        return "failed", f"登录流程超过最大尝试次数，最终 URL: {final_url}"
        
    except Exception as e:
        error_msg = f"登录过程发生未预期的异常: {str(e)}"
        print(f"[登录-异常] {error_msg}")
        import traceback
        traceback.print_exc()
        if account_id:
            add_login_log(account_id, None, 'login', 'failed', f'登录异常: {str(e)}')
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
            
            print(f"[自动登录] 浏览器已打开，检查浏览器状态...")
            add_login_log(account_id, browser_env.container_code, 'auto_login', 'info', '浏览器已打开，开始登录')
            
            # 检查浏览器是否真的准备好了
            try:
                initial_url = driver.current_url
                print(f"[自动登录] 浏览器初始URL: {initial_url}")
            except Exception as e:
                error_msg = f'无法获取浏览器URL，浏览器可能未正常启动: {str(e)}'
                print(f"[自动登录错误] {error_msg}")
                account.login_status = 'failed'
                db.session.commit()
                add_login_log(account_id, browser_env.container_code, 'auto_login', 'failed', error_msg)
                return
            
            # 执行登录（传递账号ID和辅助邮箱）
            status, message = perform_login(driver, account.account, account.password, account_id=account_id, backup_email=account.backup_email)
            print(f"[自动登录] 登录结果 - 状态: {status}, 消息: {message}")
            
            # 更新账号状态
            account.login_status = status
            # success 和 success_with_verification 都算成功
            account.status = (status in ['success', 'success_with_verification'])
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


# 批量任务停止标志
stop_batch_tasks = False


def batch_login_task(app, account_ids):
    """批量登录任务（速率控制：最多3个并发，间隔1-2秒）"""
    import random
    import threading
    from queue import Queue
    
    global stop_batch_tasks
    stop_batch_tasks = False
    
    with app.app_context():
        print(f"\n========== 开始批量登录 {len(account_ids)} 个账号 ==========")
        
        # 创建任务队列
        task_queue = Queue()
        for account_id in account_ids:
            task_queue.put(account_id)
        
        # 工作线程函数
        def worker():
            # auto_login_task内部已经有app_context，这里不需要再加
            while not task_queue.empty() and not stop_batch_tasks:
                try:
                    account_id = task_queue.get(timeout=1)
                    print(f"[批量登录] 开始登录账号 ID: {account_id}")
                    
                    # 执行登录
                    auto_login_task(app, account_id)
                    
                    # 任务完成后等待1-2秒
                    if not task_queue.empty():
                        wait_time = random.uniform(1, 2)
                        print(f"[批量登录] 等待 {wait_time:.1f} 秒后继续下一个...")
                        time.sleep(wait_time)
                    
                    task_queue.task_done()
                except Exception as e:
                    print(f"[批量登录错误] {str(e)}")
                    import traceback
                    traceback.print_exc()
        
        # 创建3个工作线程
        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker)
            thread.daemon = True
            thread.start()
            threads.append(thread)
            # 启动线程时也间隔一下
            if i < 2:
                time.sleep(0.5)
        
        # 等待所有任务完成
        for thread in threads:
            thread.join()
        
        if stop_batch_tasks:
            print(f"========== 批量登录已被用户停止 ==========\n")
        else:
            print(f"========== 批量登录完成 ==========\n")

