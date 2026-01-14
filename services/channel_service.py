# -*- coding: utf-8 -*-
"""
YouTube频道创建服务
"""
import time
import os
import random
import string
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from config import CHANNEL_AVATAR_PATH
from models import db, LoginLog


def get_random_name(length=10):
    """生成随机名字"""
    # 生成随机字符串，包含字母和数字
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def get_available_avatar():
    """从头像文件夹中获取一个可用的头像
    
    Returns:
        str: 头像文件的完整路径，如果没有可用头像则返回 None
    """
    try:
        if not CHANNEL_AVATAR_PATH or not os.path.exists(CHANNEL_AVATAR_PATH):
            print(f"[频道创建错误] 头像文件夹路径不存在: {CHANNEL_AVATAR_PATH}")
            return None
        
        # 获取文件夹中所有图片文件
        supported_formats = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
        avatar_files = []
        
        for file in os.listdir(CHANNEL_AVATAR_PATH):
            file_lower = file.lower()
            if any(file_lower.endswith(fmt) for fmt in supported_formats):
                avatar_files.append(os.path.join(CHANNEL_AVATAR_PATH, file))
        
        if not avatar_files:
            print(f"[频道创建错误] 头像文件夹中没有可用的图片文件")
            return None
        
        # 随机选择一个头像
        avatar_path = random.choice(avatar_files)
        print(f"[频道创建] 选择头像: {avatar_path}")
        return avatar_path
        
    except Exception as e:
        print(f"[频道创建错误] 获取头像失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def handle_system_upload_dialog(file_path):
    """处理操作系统文件上传弹窗
    使用 pyautogui 模拟键盘操作
    """
    try:
        import pyautogui
        import pyperclip
        
        abs_path = os.path.abspath(file_path)
        print(f"[系统交互] 开始处理文件上传弹窗: {abs_path}")
        
        # 禁用 pyautogui 的安全暂停（加快速度）
        pyautogui.PAUSE = 0.3
        
        # 等待系统弹窗完全加载
        print(f"[系统交互] 等待系统弹窗加载...")
        time.sleep(5)  # 等待5秒确保弹窗完全加载
        
        # 方法1：使用 Alt+N 聚焦到文件名输入框（Windows "打开"对话框中的快捷键）
        print(f"[系统交互] 尝试聚焦到文件名输入框 (Alt+N)...")
        pyautogui.hotkey('alt', 'n')
        time.sleep(0.5)
        
        # 清空当前输入框内容
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.3)
        
        # 复制路径到剪贴板（支持中文路径）
        print(f"[系统交互] 复制路径到剪贴板...")
        pyperclip.copy(abs_path)
        time.sleep(0.3)
        
        # 验证剪贴板内容
        clipboard_content = pyperclip.paste()
        if clipboard_content == abs_path:
            print(f"[系统交互] ✅ 剪贴板验证成功")
        else:
            print(f"[系统交互警告] 剪贴板内容不匹配！")
            print(f"[系统交互调试] 期望: {abs_path}")
            print(f"[系统交互调试] 实际: {clipboard_content}")
        
        # 粘贴路径
        print(f"[系统交互] 粘贴路径 (Ctrl+V)...")
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(2)  # 等待粘贴完成
        
        # 按回车确认（打开文件）
        print(f"[系统交互] 按回车确认...")
        pyautogui.press('enter')
        
        # 重要：等待系统弹窗完全关闭，避免后续按键被浏览器捕获
        print(f"[系统交互] 等待系统弹窗关闭...")
        time.sleep(3)
        
        print(f"[系统交互] ✅ 文件选择操作完成")
        
        # 立即返回，不要在这里长时间等待，让浏览器自然上传
        return True
        
    except ImportError:
        print(f"[系统交互错误] 缺少 pyautogui 或 pyperclip 库，无法处理系统弹窗")
        return False
    except Exception as e:
        print(f"[系统交互错误] 处理弹窗失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def check_avatar_availability():
    """检查头像文件夹中的头像数量
    
    Returns:
        tuple: (是否可用, 可用数量, 错误信息)
    """
    try:
        if not CHANNEL_AVATAR_PATH:
            return False, 0, "未配置头像文件夹路径"
        
        if not os.path.exists(CHANNEL_AVATAR_PATH):
            return False, 0, f"头像文件夹不存在: {CHANNEL_AVATAR_PATH}"
        
        # 获取文件夹中所有图片文件
        supported_formats = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
        avatar_files = []
        
        for file in os.listdir(CHANNEL_AVATAR_PATH):
            file_lower = file.lower()
            if any(file_lower.endswith(fmt) for fmt in supported_formats):
                avatar_files.append(file)
        
        count = len(avatar_files)
        if count == 0:
            return False, 0, "头像文件夹中没有可用的图片文件"
        
        return True, count, ""
        
    except Exception as e:
        return False, 0, f"检查头像文件夹失败: {str(e)}"


def add_channel_log(account_id, browser_env_id, status, message):
    """添加频道创建日志"""
    try:
        log = LoginLog(
            account_id=account_id,
            browser_env_id=browser_env_id,
            action='create_channel',
            status=status,
            message=message
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"[日志错误] 添加日志失败: {str(e)}")


def detect_monetization_requirement(driver, channel_url, account_id=None, browser_env_id=None):
    """检测YouTube创收要求（3m还是10m）
    
    Args:
        driver: Selenium WebDriver
        channel_url: 频道URL
        account_id: 账号ID（用于日志记录）
        browser_env_id: 浏览器环境ID（用于日志记录）
    
    Returns:
        str: "3m" 或 "10m" 或 None（检测失败）
    """
    try:
        print(f"[创收检测] 开始检测创收要求...")
        add_channel_log(account_id, browser_env_id, 'info', '开始检测创收要求')
        
        # 从频道URL提取频道ID
        channel_id = None
        if "channel/" in channel_url:
            channel_id = channel_url.split("channel/")[1].split("/")[0].split("?")[0]
        elif "studio.youtube.com" in channel_url and "UC" in channel_url:
            # 从studio URL中提取
            parts = channel_url.split("/")
            for part in parts:
                if part.startswith("UC"):
                    channel_id = part
                    break
        
        if not channel_id:
            print(f"[创收检测] 无法从URL中提取频道ID: {channel_url}")
            add_channel_log(account_id, browser_env_id, 'warning', f'无法从URL中提取频道ID')
            return None
        
        # 构建创收页面URL
        monetization_url = f"https://studio.youtube.com/channel/{channel_id}/monetization/overview"
        print(f"[创收检测] 导航到创收页面: {monetization_url}")
        add_channel_log(account_id, browser_env_id, 'info', f'导航到创收页面')
        
        driver.get(monetization_url)
        time.sleep(8)  # 等待页面加载
        
        # 处理"Welcome to YouTube Studio"弹窗
        try:
            print(f"[创收检测] 检查是否有欢迎弹窗...")
            # 查找Continue按钮
            continue_button = None
            try:
                # 方式1：通过按钮文本查找
                continue_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Continue') or contains(text(), '继续')]")
            except:
                # 方式2：通过aria-label查找
                try:
                    continue_button = driver.find_element(By.XPATH, "//button[@aria-label='Continue' or @aria-label='继续']")
                except:
                    pass
            
            if continue_button and continue_button.is_displayed():
                print(f"[创收检测] 检测到欢迎弹窗，点击Continue按钮...")
                continue_button.click()
                time.sleep(2)
                print(f"[创收检测] ✅ 已点击Continue按钮")
            else:
                print(f"[创收检测] 未检测到欢迎弹窗，继续...")
        except Exception as popup_err:
            print(f"[创收检测] 处理弹窗时出错（可忽略）: {str(popup_err)}")
        
        # 向下滚动页面，确保创收要求区域可见
        print(f"[创收检测] 向下滚动页面...")
        try:
            # 滚动到页面中部
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
            time.sleep(2)
            # 再滚动一点，确保Shorts区域可见
            driver.execute_script("window.scrollBy(0, 300);")
            time.sleep(1)
            print(f"[创收检测] ✅ 页面滚动完成")
        except Exception as scroll_err:
            print(f"[创收检测] 滚动页面时出错: {str(scroll_err)}")
        
        # 获取所有threshold元素
        threshold_value = None
        all_thresholds = []
        
        try:
            print(f"[创收检测] 开始获取所有threshold元素...")
            all_thresholds = driver.find_elements(By.XPATH, "//span[contains(@class, 'threshold')]")
            print(f"[创收检测] 页面上共有 {len(all_thresholds)} 个threshold元素")
            
            # 打印所有threshold的值（调试用）
            for idx, th in enumerate(all_thresholds):
                try:
                    th_text = th.text.strip()
                    print(f"[创收检测调试] threshold {idx+1}: {th_text}")
                except:
                    pass
            
            # 标准的YouTube创收页面有3个threshold：
            # 1. subscribers (1,000)
            # 2. watch hours (4,000)
            # 3. shorts views (3M 或 10M) ← 这是我们需要的
            if len(all_thresholds) >= 3:
                threshold_value = all_thresholds[2].text.strip()  # 取第3个（索引2）
                print(f"[创收检测] ✅ 成功获取第3个threshold（Shorts）值: {threshold_value}")
            else:
                print(f"[创收检测] ⚠️ threshold元素数量不足: {len(all_thresholds)}")
                
        except Exception as e:
            print(f"[创收检测] 获取threshold元素失败: {str(e)}")
        
        # 备用方法1：精确定位 shorts-progress 区域的 threshold 元素
        if not threshold_value:
            try:
                print(f"[创收检测] 尝试备用方法1: 定位shorts-progress中的threshold元素...")
                shorts_threshold = driver.find_element(
                    By.XPATH, 
                    "//div[contains(@class, 'shorts-progress')]//span[contains(@class, 'threshold')]"
                )
                threshold_value = shorts_threshold.text.strip()
                print(f"[创收检测] ✅ 备用方法1成功 - Shorts threshold值: {threshold_value}")
            except Exception as e:
                print(f"[创收检测] 备用方法1失败: {str(e)}")
        
        # 备用方法2：通过ID定位
        if not threshold_value:
            try:
                print(f"[创收检测] 尝试备用方法2: 通过shorts-count ID定位...")
                shorts_count_elem = driver.find_element(By.ID, "shorts-count")
                # 找到父容器，然后找threshold
                parent_div = shorts_count_elem.find_element(By.XPATH, "./ancestor::div[contains(@class, 'shorts-progress')]")
                shorts_threshold = parent_div.find_element(By.XPATH, ".//span[contains(@class, 'threshold')]")
                threshold_value = shorts_threshold.text.strip()
                print(f"[创收检测] ✅ 备用方法2成功 - Shorts threshold值: {threshold_value}")
            except Exception as e:
                print(f"[创收检测] 备用方法2失败: {str(e)}")
        
        # 判断结果
        if not threshold_value:
            print(f"[创收检测] ⚠️ 无法获取threshold值")
            add_channel_log(account_id, browser_env_id, 'warning', '无法获取Shorts threshold值')
            return None
        
        # 清理和标准化threshold值
        threshold_clean = threshold_value.upper().replace(',', '').replace('.', '').replace(' ', '')
        print(f"[创收检测] 标准化后的threshold值: {threshold_clean}")
        
        # 判断是3m还是10m
        import re
        result = None
        
        # 检测3M相关
        # 匹配: 3M, 3000000, 300万, 3 million, 3 triệu 等
        if re.search(r'3M|3000000|300万|3MILLION|3TRIỆU', threshold_clean):
            result = "3m"
            print(f"[创收检测] ✅ 检测结果: 3m (300万) - threshold值: {threshold_value}")
            add_channel_log(account_id, browser_env_id, 'success', f'检测到创收要求: 3m (300万) - 显示值: {threshold_value}')
        # 检测10M相关
        # 匹配: 10M, 10000000, 1000万, 10 million, 10 triệu 等
        elif re.search(r'10M|10000000|1000万|10MILLION|10TRIỆU', threshold_clean):
            result = "10m"
            print(f"[创收检测] ✅ 检测结果: 10m (1000万) - threshold值: {threshold_value}")
            add_channel_log(account_id, browser_env_id, 'success', f'检测到创收要求: 10m (1000万) - 显示值: {threshold_value}')
        else:
            print(f"[创收检测] ⚠️ 无法识别threshold值: {threshold_value}")
            add_channel_log(account_id, browser_env_id, 'warning', f'无法识别threshold值: {threshold_value}')
        
        return result
        
    except Exception as e:
        error_msg = f"检测创收要求失败: {str(e)}"
        print(f"[创收检测错误] {error_msg}")
        import traceback
        traceback.print_exc()
        add_channel_log(account_id, browser_env_id, 'failed', error_msg)
        return None


def create_youtube_channel(driver, account_id=None, browser_env_id=None):
    """创建YouTube频道
    
    Args:
        driver: Selenium WebDriver
        account_id: 账号ID（用于日志记录）
        browser_env_id: 浏览器环境ID（用于日志记录）
    
    Returns:
        tuple: (status, message)
            - status: "success" 成功, "failed" 失败
            - message: 详细信息
    """
    avatar_path = None
    channel_name = ""
    channel_url = ""  # 频道链接
    
    try:
        print(f"[频道创建-开始] ===== 开始创建YouTube频道 =====")
        add_channel_log(account_id, browser_env_id, 'info', '开始创建YouTube频道')
        driver.maximize_window()
        
        # === 步骤1: 检查是否已登录Google账号 ===
        print(f"[频道创建-步骤1] 检查浏览器登录状态...")
        add_channel_log(account_id, browser_env_id, 'info', '步骤1: 检查浏览器登录状态')
        try:
            current_url = driver.current_url
            print(f"[频道创建-步骤1] 当前URL: {current_url}")
            
            # 如果是空白页，先导航到YouTube检查登录状态
            if current_url == "about:blank" or ("google.com" not in current_url and "youtube.com" not in current_url):
                print(f"[频道创建-步骤1] 当前不在Google/YouTube页面，先导航到YouTube检查登录状态...")
                driver.get("https://www.youtube.com/")
                time.sleep(5)
                current_url = driver.current_url
                print(f"[频道创建-步骤1] 导航后URL: {current_url}")
            
            print(f"[频道创建-步骤1] ✅ 浏览器状态正常")
            add_channel_log(account_id, browser_env_id, 'success', '步骤1完成: 浏览器状态检查通过')
            
        except Exception as e:
            error_msg = f"步骤1失败: 无法获取当前URL: {str(e)}"
            print(f"[频道创建-步骤1-错误] {error_msg}")
            add_channel_log(account_id, browser_env_id, 'failed', error_msg)
            return "failed", "浏览器连接失败"
        
        # === 步骤2: 检查频道是否已经创建 ===
        print(f"[频道创建-步骤2] 检查频道是否已经创建...")
        add_channel_log(account_id, browser_env_id, 'info', '步骤2: 检查频道是否已存在')
        try:
            from models import Account
            account = Account.query.get(account_id)
            if account and account.channel_status == 'created' and account.channel_url:
                print(f"[频道创建-步骤2] ⚠️ 检测到频道已存在: {account.channel_url}")
                add_channel_log(account_id, browser_env_id, 'info', '步骤2: 检测到频道已存在，跳转到验证流程')
                
                # 跳转到YouTube工作室验证频道
                print(f"[频道创建-步骤2.1] 跳转到YouTube工作室验证频道...")
                driver.get("https://studio.youtube.com")
                time.sleep(5)
                
                # 验证频道链接是否正常
                current_url = driver.current_url
                print(f"[频道创建-步骤2.1] 当前URL: {current_url}")
                
                if "studio.youtube.com" in current_url:
                    print(f"[频道创建-步骤2.1] ✅ 频道状态正常，可以访问YouTube工作室")
                    add_channel_log(account_id, browser_env_id, 'success', '步骤2.1完成: 频道状态正常')
                    
                    # 检测创收要求
                    print(f"[频道创建-步骤2.2] 开始检测创收要求...")
                    add_channel_log(account_id, browser_env_id, 'info', '步骤2.2: 检测创收要求')
                    monetization_req = detect_monetization_requirement(driver, account.channel_url, account_id, browser_env_id)
                    
                    if monetization_req:
                        print(f"[频道创建-步骤2.2] ✅ 创收要求检测成功: {monetization_req}")
                        account.monetization_requirement = monetization_req
                        db.session.commit()
                        add_channel_log(account_id, browser_env_id, 'success', f'步骤2.2完成: 创收要求为 {monetization_req}')
                        
                        success_msg = f"✅ 频道已存在且状态正常！链接: {account.channel_url}, 创收要求: {monetization_req}"
                        return "success", success_msg
                    else:
                        print(f"[频道创建-步骤2.2] ⚠️ 无法检测创收要求")
                        add_channel_log(account_id, browser_env_id, 'warning', '步骤2.2: 无法检测创收要求')
                        
                        success_msg = f"✅ 频道已存在且状态正常！链接: {account.channel_url}, 创收要求: 未检测到"
                        return "success", success_msg
                else:
                    print(f"[频道创建-步骤2.1] ⚠️ 无法访问YouTube工作室，频道可能有问题")
                    add_channel_log(account_id, browser_env_id, 'warning', '步骤2.1: 无法访问YouTube工作室')
                    # 继续创建新频道流程
            
            print(f"[频道创建-步骤2] ✅ 频道未创建，继续创建流程")
        except Exception as e:
            print(f"[频道创建-步骤2-警告] 检查频道状态失败: {str(e)}")
            # 继续创建流程
        
        # === 步骤3: 获取可用头像 ===
        print(f"[频道创建-步骤3] 获取可用头像...")
        add_channel_log(account_id, browser_env_id, 'info', '步骤3: 获取可用头像')
        avatar_path = get_available_avatar()
        if not avatar_path:
            error_msg = "步骤3失败: 没有可用的头像文件"
            print(f"[频道创建-步骤3-错误] {error_msg}")
            add_channel_log(account_id, browser_env_id, 'failed', error_msg)
            return "failed", "没有可用的头像文件，请在设置中配置头像文件夹路径"
        
        print(f"[频道创建-步骤3] ✅ 已选择头像: {os.path.basename(avatar_path)}")
        add_channel_log(account_id, browser_env_id, 'success', f'步骤3完成: 已选择头像 [{os.path.basename(avatar_path)}]')
        
        # === 步骤4: 跳转到YouTube首页 ===
        print(f"[频道创建-步骤4] 跳转到YouTube首页...")
        add_channel_log(account_id, browser_env_id, 'info', '步骤4: 跳转到YouTube首页')
        driver.get("https://www.youtube.com/")
        time.sleep(5)
        
        current_url = driver.current_url
        print(f"[频道创建-步骤4] 当前URL: {current_url}")
        
        # === 步骤4.1: 检查是否遇到 Google 登录被拒绝页面 ===
        if "signin/rejected" in current_url or "Couldn't sign you in" in driver.page_source:
            print(f"[频道创建-步骤4.1] ⚠️ 检测到Google登录被拒绝页面")
            add_channel_log(account_id, browser_env_id, 'warning', '步骤4.1: 检测到登录被拒绝，尝试点击Try again')
            
            try:
                # 查找并点击 "Try again" 按钮
                try_again_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Try again') or contains(., '重试')]"))
                )
                try_again_btn.click()
                print(f"[频道创建-步骤4.1] ✅ 已点击 'Try again' 按钮")
                add_channel_log(account_id, browser_env_id, 'success', '步骤4.1完成: 已点击Try again按钮，等待重新登录')
                time.sleep(5)
                
                # 更新URL
                current_url = driver.current_url
                print(f"[频道创建-步骤4.1] 点击Try again后URL: {current_url}")
                
            except Exception as e:
                error_msg = f"步骤4.1失败: 点击Try again按钮失败: {str(e)}"
                print(f"[频道创建-步骤4.1-错误] {error_msg}")
                add_channel_log(account_id, browser_env_id, 'failed', error_msg)
                return "failed", "登录被拒绝且无法点击Try again按钮"
        else:
            print(f"[频道创建-步骤4] ✅ 成功跳转到YouTube")
            add_channel_log(account_id, browser_env_id, 'success', '步骤4完成: 成功跳转到YouTube首页')
        
        # === 步骤5: 检查是否需要处理额外的验证步骤 ===
        if "accounts.google.com" in current_url:
            if "uplevelingstep" in current_url or "selection" in current_url:
                print(f"[频道创建-步骤5] 检测到Google额外验证步骤（Verify your info to continue）")
                add_channel_log(account_id, browser_env_id, 'info', '步骤5: 检测到需要验证身份')
                
                # 导入手机验证相关函数
                from services.login_service import get_available_phone, get_sms_code
                
                # 检查是否需要手机号验证
                try:
                    # 查找"Verify your phone number"选项
                    phone_verify_option = None
                    try:
                        phone_verify_option = driver.find_element(By.XPATH, "//*[contains(text(), 'Verify your phone number') or contains(text(), '验证您的手机号码')]")
                        print(f"[频道创建] 找到手机号验证选项")
                    except:
                        # 查找所有包含"phone"的可点击元素
                        elements = driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'PHONE', 'phone'), 'phone')]")
                        for elem in elements:
                            if elem.is_displayed() and ("verify" in elem.text.lower() or "验证" in elem.text):
                                phone_verify_option = elem
                                print(f"[频道创建] 通过遍历找到手机号验证选项")
                                break
                    
                    if phone_verify_option:
                        print(f"[频道创建-步骤4.1] 需要手机号验证，开始处理...")
                        add_channel_log(account_id, browser_env_id, 'info', '步骤4.1: 需要手机号验证')
                        
                        # 获取可用手机号
                        from models import Account
                        acc = Account.query.get(account_id)
                        phone = get_available_phone(account_id)
                        
                        if not phone:
                            error_msg = "步骤4.1失败: 需要手机号验证，但没有可用的手机号"
                            print(f"[频道创建-步骤4.1-错误] {error_msg}")
                            add_channel_log(account_id, browser_env_id, 'failed', error_msg)
                            return "failed", error_msg
                        
                        if not phone.sms_url:
                            error_msg = f"步骤4.1失败: 手机号 {phone.phone_number} 没有配置接码URL"
                            print(f"[频道创建-步骤4.1-错误] {error_msg}")
                            add_channel_log(account_id, browser_env_id, 'failed', error_msg)
                            return "failed", error_msg
                        
                        print(f"[频道创建-步骤4.1] 已获取手机号: {phone.phone_number}")
                        add_channel_log(account_id, browser_env_id, 'info', f'步骤4.1: 已获取手机号 [+{phone.phone_number}]')
                        
                        # === 步骤4.2: 点击手机号验证选项 ===
                        print(f"[频道创建-步骤4.2] 点击手机号验证选项...")
                        add_channel_log(account_id, browser_env_id, 'info', '步骤4.2: 点击手机号验证选项')
                        try:
                            phone_verify_option.click()
                            print(f"[频道创建-步骤4.2] ✅ 已点击手机号验证选项")
                        except:
                            driver.execute_script("arguments[0].click();", phone_verify_option)
                            print(f"[频道创建-步骤4.2] ✅ 已点击手机号验证选项（JS方式）")
                        
                        add_channel_log(account_id, browser_env_id, 'success', '步骤4.2完成: 已选择手机号验证方式')
                        time.sleep(3)
                        
                        # === 步骤4.3: 检查是否需要输入手机号 ===
                        print(f"[频道创建-步骤4.3] 检查是否需要输入手机号...")
                        try:
                            phone_input = driver.find_element(By.XPATH, "//input[@type='tel' or @id='phoneNumberId']")
                            print(f"[频道创建-步骤4.3] 需要输入手机号")
                            add_channel_log(account_id, browser_env_id, 'info', '步骤4.3: 输入手机号')
                            
                            full_phone = f"+{phone.phone_number}"
                            phone_input.clear()
                            phone_input.send_keys(full_phone)
                            print(f"[频道创建-步骤4.3] 已输入手机号: {full_phone}")
                            add_channel_log(account_id, browser_env_id, 'info', f'步骤4.3: 已输入手机号 [{full_phone}]')
                            
                            # 点击下一步
                            next_btn = driver.find_element(By.XPATH, "//button[@type='button']//span[contains(text(), 'Next') or contains(text(), '下一步')]")
                            next_btn.click()
                            print(f"[频道创建-步骤4.3] ✅ 已点击下一步")
                            add_channel_log(account_id, browser_env_id, 'success', '步骤4.3完成: 已点击下一步，等待验证码')
                            
                            # 记录点击下一步的时间（用于过滤旧验证码）
                            from datetime import datetime
                            sms_request_time = datetime.now()
                            print(f"[频道创建-步骤4.3] 记录请求时间: {sms_request_time.strftime('%Y-%m-%d %H:%M:%S')}")
                            
                            time.sleep(3)
                        except:
                            print(f"[频道创建-步骤4.3] 不需要输入手机号（可能已保存）")
                            add_channel_log(account_id, browser_env_id, 'info', '步骤4.3: 手机号已保存，无需输入')
                            from datetime import datetime
                            sms_request_time = datetime.now()
                        
                        # === 步骤4.4: 获取验证码 ===
                        print(f"[频道创建-步骤4.4] 开始获取验证码...")
                        add_channel_log(account_id, browser_env_id, 'info', '步骤4.4: 开始获取验证码')
                        sms_code = get_sms_code(phone.sms_url, max_retries=12, interval=10, request_time=sms_request_time)
                        
                        if not sms_code:
                            error_msg = "步骤4.4失败: 获取验证码失败（超过12次重试）"
                            print(f"[频道创建-步骤4.4-错误] {error_msg}")
                            add_channel_log(account_id, browser_env_id, 'failed', error_msg)
                            return "failed", error_msg
                        
                        print(f"[频道创建-步骤4.4] ✅ 已获取验证码: {sms_code}")
                        add_channel_log(account_id, browser_env_id, 'success', f'步骤4.4完成: 已获取验证码')
                        
                        # === 步骤4.5: 输入验证码 ===
                        print(f"[频道创建-步骤4.5] 查找验证码输入框...")
                        add_channel_log(account_id, browser_env_id, 'info', '步骤4.5: 输入验证码')
                        try:
                            code_input = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.XPATH, "//input[@type='tel' or @id='code' or contains(@name, 'code') or contains(@aria-label, 'code')]"))
                            )
                            print(f"[频道创建-步骤4.5] 找到验证码输入框")
                            
                            code_input.clear()
                            code_input.send_keys(sms_code)
                            print(f"[频道创建-步骤4.5] 已输入验证码: {sms_code}")
                            add_channel_log(account_id, browser_env_id, 'info', f'步骤4.5: 已输入验证码')
                            
                            time.sleep(2)
                            
                            # 点击下一步/验证按钮
                            try:
                                verify_btn = driver.find_element(By.XPATH, "//button[@type='button']//span[contains(text(), 'Next') or contains(text(), '下一步') or contains(text(), 'Verify') or contains(text(), '验证')]")
                                verify_btn.click()
                                print(f"[频道创建-步骤4.5] 已点击验证按钮")
                                add_channel_log(account_id, browser_env_id, 'info', '步骤4.5: 已提交验证码')
                            except:
                                print(f"[频道创建-步骤4.5] 未找到验证按钮，可能自动提交")
                            
                            # 等待验证完成
                            time.sleep(5)
                            
                            # 更新数据库
                            try:
                                if not phone.status:
                                    phone.status = True
                                if acc.phone_id != phone.id:
                                    acc.phone_id = phone.id
                                db.session.commit()
                                print(f"[频道创建-步骤4.5] 已绑定手机号到账号")
                            except:
                                pass
                            
                            # 检查是否成功
                            current_url = driver.current_url
                            print(f"[频道创建-步骤4.5] 验证后URL: {current_url}")
                            
                            if "youtube.com" in current_url:
                                print(f"[频道创建-步骤4.5] ✅ 手机验证成功，已到达YouTube")
                                add_channel_log(account_id, browser_env_id, 'success', '步骤4.5完成: 手机验证成功')
                            else:
                                print(f"[频道创建-步骤4.5] 验证后仍未到达YouTube，等待跳转...")
                                add_channel_log(account_id, browser_env_id, 'info', '步骤4.5: 等待页面跳转到YouTube')
                                time.sleep(10)
                                current_url = driver.current_url
                                print(f"[频道创建-步骤4.5] 等待后URL: {current_url}")
                            
                        except Exception as code_error:
                            error_msg = f"步骤4.5失败: 输入验证码失败: {str(code_error)}"
                            print(f"[频道创建-步骤4.5-错误] {error_msg}")
                            add_channel_log(account_id, browser_env_id, 'failed', error_msg)
                            return "failed", "手机验证失败"
                    
                    else:
                        # 没有手机验证选项，可能有其他选项
                        print(f"[频道创建] 未找到手机验证选项，查找其他验证方式...")
                        
                        # 尝试查找任何Continue/Next按钮
                        buttons = driver.find_elements(By.TAG_NAME, "button")
                        continue_btn = None
                        for btn in buttons:
                            if btn.is_displayed():
                                btn_text = btn.text.lower()
                                if "continue" in btn_text or "next" in btn_text or "skip" in btn_text:
                                    continue_btn = btn
                                    break
                        
                        if continue_btn:
                            continue_btn.click()
                            print(f"[频道创建] 已点击继续按钮")
                            time.sleep(5)
                        else:
                            print(f"[频道创建] 未找到继续按钮，等待自动跳转...")
                            time.sleep(10)
                        
                        current_url = driver.current_url
                        print(f"[频道创建] 处理后URL: {current_url}")
                    
                except Exception as verify_error:
                    error_msg = f"处理验证步骤失败: {str(verify_error)}"
                    print(f"[频道创建错误] {error_msg}")
                    import traceback
                    traceback.print_exc()
                    # 继续尝试
                    time.sleep(10)
                    current_url = driver.current_url
                    print(f"[频道创建] 异常后URL: {current_url}")
                
                # 最终检查是否到达YouTube
                if "youtube.com" not in current_url:
                    error_msg = "步骤4失败: 无法通过验证跳转到YouTube"
                    print(f"[频道创建-步骤4-错误] {error_msg}")
                    add_channel_log(account_id, browser_env_id, 'failed', error_msg)
                    return "failed", "无法通过验证，请手动检查"
                else:
                    print(f"[频道创建-步骤4] ✅ 成功到达YouTube")
                    add_channel_log(account_id, browser_env_id, 'success', '步骤4完成: 成功到达YouTube首页')
            else:
                # 其他情况，真的需要登录
                error_msg = "步骤4失败: 需要登录Google账号"
                print(f"[频道创建-步骤4-错误] {error_msg}")
                add_channel_log(account_id, browser_env_id, 'failed', error_msg)
                return "failed", "账号未登录，请先完成登录"
        
        # === 步骤5: 检查登录状态 ===
        print(f"[频道创建-步骤5] 检查YouTube登录状态...")
        add_channel_log(account_id, browser_env_id, 'info', '步骤5: 检查YouTube登录状态')
        try:
            # 查找是否有 "Sign in" 或 "Login" 按钮
            login_buttons = driver.find_elements(By.XPATH, 
                "//a[contains(text(), 'Sign in') or contains(text(), 'Login') or contains(text(), '登录')] | " +
                "//button[contains(text(), 'Sign in') or contains(text(), 'Login') or contains(text(), '登录')]"
            )
            
            has_login_button = False
            for btn in login_buttons:
                try:
                    if btn.is_displayed():
                        has_login_button = True
                        print(f"[频道创建-步骤5] ⚠️ 检测到登录按钮，说明未登录")
                        break
                except:
                    pass
            
            if has_login_button:
                error_msg = "步骤5失败: 检测到页面有登录按钮，账号未登录，需要先完成登录"
                print(f"[频道创建-步骤5-错误] {error_msg}")
                add_channel_log(account_id, browser_env_id, 'failed', error_msg)
                return "failed", error_msg
            else:
                print(f"[频道创建-步骤5] ✅ 未检测到登录按钮，账号已登录")
                add_channel_log(account_id, browser_env_id, 'success', '步骤5完成: 账号已登录，继续创建频道')
                
        except Exception as e:
            print(f"[频道创建-步骤5-警告] 检查登录状态时出错: {str(e)}，继续执行")
            add_channel_log(account_id, browser_env_id, 'warning', f'步骤5警告: 检查登录状态出错，继续')
        
        # === 步骤6: 点击创建按钮 ===
        print(f"[频道创建-步骤6] 查找并点击Create按钮...")
        add_channel_log(account_id, browser_env_id, 'info', '步骤6: 查找Create按钮')
        try:
            # 多种方式尝试定位Create按钮
            create_button = None
            
            try:
                # 方式1: 通过aria-label查找
                create_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Create' or @aria-label='创建']"))
                )
                print(f"[频道创建] 通过aria-label找到Create按钮")
            except:
                try:
                    # 方式2: 通过title查找
                    create_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[@title='Create' or @title='创建']"))
                    )
                    print(f"[频道创建] 通过title找到Create按钮")
                except:
                    try:
                        # 方式3: 通过yt-icon-button查找包含create的
                        create_button = driver.find_element(By.XPATH, "//ytd-topbar-menu-button-renderer[contains(@class, 'style-scope')]//button[contains(@aria-label, 'reate')]")
                        print(f"[频道创建] 通过class找到Create按钮")
                    except:
                        # 方式4: 查找所有可见的按钮，找包含create相关图标的
                        buttons = driver.find_elements(By.TAG_NAME, "button")
                        for btn in buttons:
                            aria_label = btn.get_attribute("aria-label") or ""
                            title = btn.get_attribute("title") or ""
                            if "create" in aria_label.lower() or "create" in title.lower() or "创建" in aria_label or "创建" in title:
                                if btn.is_displayed():
                                    create_button = btn
                                    print(f"[频道创建] 通过遍历找到Create按钮")
                                    break
            
            if not create_button:
                error_msg = "步骤6失败: 未找到Create按钮"
                print(f"[频道创建-步骤6-错误] {error_msg}")
                add_channel_log(account_id, browser_env_id, 'failed', error_msg)
                return "failed", "未找到Create按钮，可能页面结构已改变"
            
            # 滚动到按钮可见
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", create_button)
            time.sleep(1)
            
            # 点击按钮
            try:
                create_button.click()
                print(f"[频道创建-步骤6] ✅ 已点击Create按钮")
                add_channel_log(account_id, browser_env_id, 'success', '步骤6完成: 已点击Create按钮，等待菜单弹出')
            except:
                driver.execute_script("arguments[0].click();", create_button)
                print(f"[频道创建-步骤6] ✅ 已点击Create按钮（JS方式）")
                add_channel_log(account_id, browser_env_id, 'success', '步骤6完成: 已点击Create按钮（JS方式）')
            
            # 等待菜单弹出
            time.sleep(3)
            
        except Exception as e:
            error_msg = f"步骤6失败: 点击Create按钮失败: {str(e)}"
            print(f"[频道创建-步骤6-错误] {error_msg}")
            import traceback
            traceback.print_exc()
            add_channel_log(account_id, browser_env_id, 'failed', error_msg)
            return "failed", error_msg
        
        # === 步骤7: 在弹出菜单中找到并点击"Upload video"选项 ===
        print(f"[频道创建-步骤7] 查找并点击'Upload video'选项...")
        add_channel_log(account_id, browser_env_id, 'info', '步骤7: 查找Upload video选项')
        try:
            # 查找菜单项
            upload_video_option = None
            
            try:
                # 方式1: 通过文本查找
                upload_video_option = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Upload video') or contains(text(), '上传视频')]"))
                )
                print(f"[频道创建] 通过文本找到'Upload video'选项")
            except:
                try:
                    # 方式2: 通过图标和文本组合查找
                    elements = driver.find_elements(By.XPATH, "//ytd-menu-service-item-renderer//yt-formatted-string | //tp-yt-paper-item//yt-formatted-string")
                    for elem in elements:
                        text = elem.text.lower()
                        if "upload" in text and "video" in text or "上传视频" in elem.text:
                            upload_video_option = elem
                            print(f"[频道创建] 通过遍历找到'Upload video'选项")
                            break
                except:
                    pass
            
            if not upload_video_option:
                error_msg = "步骤7失败: 未找到'Upload video'选项"
                print(f"[频道创建-步骤7-错误] {error_msg}")
                add_channel_log(account_id, browser_env_id, 'failed', error_msg)
                return "failed", "未找到Upload video选项，菜单结构可能已改变"
            
            # 滚动到选项可见
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", upload_video_option)
            time.sleep(1)
            
            # 点击选项
            try:
                upload_video_option.click()
                print(f"[频道创建-步骤7] ✅ 已点击'Upload video'选项")
                add_channel_log(account_id, browser_env_id, 'success', '步骤7完成: 已点击Upload video选项，等待响应')
            except:
                driver.execute_script("arguments[0].click();", upload_video_option)
                print(f"[频道创建-步骤7] ✅ 已点击'Upload video'选项（JS方式）")
                add_channel_log(account_id, browser_env_id, 'success', '步骤7完成: 已点击Upload video选项（JS方式）')
            
            # 等待页面响应（可能会弹出创建频道提示）
            time.sleep(5)
            
            # === 步骤8: 检查是否出现创建频道的提示或弹窗 ===
            current_url = driver.current_url
            print(f"[频道创建-步骤8] 点击Upload video后URL: {current_url}")
            add_channel_log(account_id, browser_env_id, 'info', '步骤8: 检查是否需要创建频道')
            
            # 如果没有频道，YouTube会显示创建频道的弹窗
            # 如果已有频道，会直接进入上传页面
            if "upload" in current_url.lower():
                # 已经有频道了，直接进入了上传页面
                print(f"[频道创建-步骤8] 检测到已有频道（直接进入上传页面）")
                add_channel_log(account_id, browser_env_id, 'info', '步骤8: 检测到账号已有频道，开始提取频道信息')
                
                # 从URL提取频道ID
                import re
                channel_id_match = re.search(r'/channel/([^/]+)', current_url)
                if channel_id_match:
                    channel_id = channel_id_match.group(1)
                    channel_url = f"https://www.youtube.com/channel/{channel_id}"
                    print(f"[频道创建-步骤8] ✅ 已提取频道ID: {channel_id}")
                    print(f"[频道创建-步骤8] 频道链接: {channel_url}")
                    add_channel_log(account_id, browser_env_id, 'success', f'步骤8完成: 已提取频道链接 [{channel_url}]')
                    
                    # 检测创收要求
                    monetization_req = None
                    try:
                        print(f"[频道创建-步骤8.1] 开始检测创收要求...")
                        add_channel_log(account_id, browser_env_id, 'info', '步骤8.1: 检测创收要求')
                        monetization_req = detect_monetization_requirement(driver, channel_url, account_id, browser_env_id)
                        if monetization_req:
                            print(f"[频道创建-步骤8.1] ✅ 创收要求检测成功: {monetization_req}")
                            add_channel_log(account_id, browser_env_id, 'success', f'步骤8.1完成: 创收要求为 {monetization_req}')
                        else:
                            print(f"[频道创建-步骤8.1] ⚠️ 创收要求检测失败")
                            add_channel_log(account_id, browser_env_id, 'warning', '步骤8.1: 无法检测创收要求')
                    except Exception as detect_error:
                        print(f"[频道创建-步骤8.1-警告] 检测创收要求失败: {str(detect_error)}")
                        add_channel_log(account_id, browser_env_id, 'warning', f'步骤8.1: 检测创收要求失败 - {str(detect_error)}')
                    
                    # 更新数据库
                    try:
                        from models import Account
                        account = Account.query.get(account_id)
                        if account:
                            account.channel_status = 'created'
                            account.channel_url = channel_url
                            if monetization_req:
                                account.monetization_requirement = monetization_req
                            db.session.commit()
                            print(f"[频道创建-步骤8.2] ✅ 已更新数据库（创收要求: {monetization_req or '未检测到'}）")
                            add_channel_log(account_id, browser_env_id, 'success', f'步骤8.2完成: 已保存频道信息到数据库')
                    except Exception as db_error:
                        print(f"[频道创建-步骤8.2-错误] 更新数据库失败: {str(db_error)}")
                        add_channel_log(account_id, browser_env_id, 'failed', f'步骤8.2失败: 更新数据库失败 - {str(db_error)}')
                    
                    success_msg = f"✅ 账号已有频道！链接: {channel_url}, 创收要求: {monetization_req or '未检测到'}"
                    print(f"[频道创建-步骤8] {success_msg}")
                    return "success", success_msg
                else:
                    error_msg = "无法从URL提取频道ID"
                    print(f"[频道创建-步骤8-错误] {error_msg}")
                    add_channel_log(account_id, browser_env_id, 'failed', error_msg)
                    return "failed", f"检测到已有频道但{error_msg}"
            
            # 检查是否出现创建频道弹窗
            print(f"[频道创建-步骤8] 检查是否出现创建频道弹窗...")
            try:
                # 查找创建频道弹窗的标题 "How you'll appear"
                channel_dialog = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(text(), \"How you'll appear\") or contains(text(), '您的显示方式')]"))
                )
                print(f"[频道创建-步骤8] ✅ 检测到创建频道弹窗")
                add_channel_log(account_id, browser_env_id, 'success', '步骤8完成: 检测到创建频道弹窗')
            except:
                print(f"[频道创建-步骤8] 未检测到创建频道弹窗，检查账号是否已有频道...")
                add_channel_log(account_id, browser_env_id, 'warning', '步骤8: 未检测到创建频道弹窗，检查是否已有频道')
                
                # 尝试检测是否已有频道
                try:
                    # 如果URL已经变成频道页面，说明账号已有频道
                    current_url = driver.current_url
                    if "channel" in current_url.lower() or "studio" in current_url.lower():
                        print(f"[频道创建] ✅ 检测到账号已有频道: {current_url}")
                        
                        # 保存频道信息到数据库
                        try:
                            from models import Account
                            account = Account.query.get(account_id)
                            if account:
                                account.channel_status = 'created'
                                account.channel_url = current_url
                                db.session.commit()
                                print(f"[频道创建] ✅ 已保存已有频道信息到数据库")
                        except Exception as db_error:
                            print(f"[频道创建警告] 保存频道信息失败: {str(db_error)}")
                        
                        add_channel_log(account_id, browser_env_id, 'success', f'账号已有频道: {current_url}')
                        return "success", f"账号已有频道: {current_url}"
                    
                    # 尝试直接访问频道页面来获取频道链接
                    print(f"[频道创建] 尝试访问YouTube Studio获取频道信息...")
                    driver.get("https://studio.youtube.com")
                    time.sleep(5)
                    
                    studio_url = driver.current_url
                    if "studio.youtube.com/channel" in studio_url:
                        # 从URL中提取频道ID
                        import re
                        channel_match = re.search(r'channel/([^/]+)', studio_url)
                        if channel_match:
                            channel_id = channel_match.group(1)
                            channel_url = f"https://www.youtube.com/channel/{channel_id}"
                            print(f"[频道创建] ✅ 从Studio获取到频道链接: {channel_url}")
                            
                            # 保存频道信息到数据库
                            try:
                                from models import Account
                                account = Account.query.get(account_id)
                                if account:
                                    account.channel_status = 'created'
                                    account.channel_url = channel_url
                                    db.session.commit()
                                    print(f"[频道创建] ✅ 已保存频道信息到数据库")
                            except Exception as db_error:
                                print(f"[频道创建警告] 保存频道信息失败: {str(db_error)}")
                            
                            add_channel_log(account_id, browser_env_id, 'success', f'账号已有频道: {channel_url}')
                            return "success", f"账号已有频道: {channel_url}"
                except Exception as check_error:
                    print(f"[频道创建-步骤8-调试] 检查已有频道失败: {str(check_error)}")
                
                error_msg = "步骤8失败: 未检测到创建频道弹窗"
                print(f"[频道创建-步骤8-错误] {error_msg}")
                add_channel_log(account_id, browser_env_id, 'failed', error_msg)
                return "failed", "未检测到创建频道弹窗，请手动检查账号状态"
                
        except Exception as e:
            error_msg = f"步骤7-8失败: 点击Upload video或检测创建频道弹窗失败: {str(e)}"
            print(f"[频道创建-步骤7-8-错误] {error_msg}")
            import traceback
            traceback.print_exc()
            add_channel_log(account_id, browser_env_id, 'failed', error_msg)
            return "failed", error_msg
        
        # === 步骤9: 在频道创建弹窗中上传头像 ===
        print(f"[频道创建-步骤9] 开始上传头像...")
        add_channel_log(account_id, browser_env_id, 'info', '步骤9: 开始上传头像')
        
        # === 步骤9.1: 点击"Select picture"按钮 ===
        print(f"[频道创建-步骤9.1] 点击'Select picture'按钮...")
        add_channel_log(account_id, browser_env_id, 'info', '步骤9.1: 点击Select picture按钮')
        try:
            select_picture_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Select picture' or contains(., 'Select picture')]"))
            )
            print(f"[频道创建-步骤9.1] 找到'Select picture'按钮")
            
            select_picture_btn.click()
            print(f"[频道创建-步骤9.1] ✅ 已点击'Select picture'按钮")
            add_channel_log(account_id, browser_env_id, 'success', '步骤9.1完成: 已点击Select picture按钮')
            
            # 等待弹窗出现
            print(f"[频道创建-步骤9.1] 等待'Choose your picture'弹窗出现...")
            time.sleep(3)  # 先等待弹窗加载
            
        except Exception as e:
            error_msg = f"步骤9.1失败: 点击Select picture按钮失败: {str(e)}"
            print(f"[频道创建-步骤9.1-错误] {error_msg}")
            add_channel_log(account_id, browser_env_id, 'failed', error_msg)
            return "failed", "无法点击Select picture按钮"
        
        # === 步骤9.2: 检查是否需要切换到iframe ===
        print(f"[频道创建-步骤9.2] 检查是否有iframe...")
        add_channel_log(account_id, browser_env_id, 'info', '步骤9.2: 检查iframe')
        switched_to_iframe = False
        original_window = None
        
        try:
            # 查找页面上所有的iframe
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            print(f"[频道创建调试] 页面上找到 {len(iframes)} 个iframe")
            
            # 遍历iframe，查找包含目标内容的
            for i, iframe in enumerate(iframes):
                try:
                    # 检查iframe是否可见
                    if not iframe.is_displayed():
                        continue
                    
                    # 获取iframe的src属性
                    iframe_src = iframe.get_attribute("src") or ""
                    print(f"[频道创建调试] iframe{i+1}: src='{iframe_src[:100]}...' visible={iframe.is_displayed()}")
                    
                    # 如果是Google的profile相关iframe，尝试切换
                    if "profile" in iframe_src.lower() or "accounts.google" in iframe_src.lower() or iframe.is_displayed():
                        print(f"[频道创建] 尝试切换到iframe{i+1}...")
                        driver.switch_to.frame(iframe)
                        
                        # 检查这个iframe中是否有我们需要的元素
                        time.sleep(1)
                        test_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'From computer') or contains(text(), 'Illustrations')]")
                        
                        if test_elements:
                            print(f"[频道创建] ✅ 在iframe{i+1}中找到目标元素！")
                            switched_to_iframe = True
                            break
                        else:
                            # 没找到，切回主文档继续查找
                            print(f"[频道创建调试] iframe{i+1}中未找到目标元素，切回主文档")
                            driver.switch_to.default_content()
                            
                except Exception as iframe_error:
                    print(f"[频道创建调试] 处理iframe{i+1}时出错: {str(iframe_error)}")
                    try:
                        driver.switch_to.default_content()
                    except:
                        pass
            
            # 如果没有找到合适的iframe，尝试直接在主文档查找
            if not switched_to_iframe:
                print(f"[频道创建] 未在iframe中找到元素，尝试在主文档中查找...")
                driver.switch_to.default_content()
                
                # 再次检查主文档
                test_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'From computer')]")
                if test_elements:
                    print(f"[频道创建] ✅ 在主文档中找到'From computer'元素")
                else:
                    # 尝试查找所有窗口句柄
                    print(f"[频道创建调试] 检查是否有新窗口...")
                    all_windows = driver.window_handles
                    print(f"[频道创建调试] 当前有 {len(all_windows)} 个窗口")
                    
        except Exception as e:
            print(f"[频道创建警告] 检查iframe时出错: {str(e)}")
            try:
                driver.switch_to.default_content()
            except:
                pass
        
        # 步骤3: 使用JavaScript在所有frame中查找元素
        print(f"[频道创建] 使用JavaScript全局查找...")
        try:
            # 使用JavaScript查找所有frame中的元素
            js_find_result = driver.execute_script("""
                function findInAllFrames(selector) {
                    // 先在主文档查找
                    var element = document.querySelector(selector);
                    if (element) return {found: true, frameIndex: -1};
                    
                    // 在所有iframe中查找
                    var frames = document.querySelectorAll('iframe');
                    for (var i = 0; i < frames.length; i++) {
                        try {
                            var frameDoc = frames[i].contentDocument || frames[i].contentWindow.document;
                            element = frameDoc.querySelector(selector);
                            if (element) return {found: true, frameIndex: i};
                        } catch(e) {
                            // 跨域iframe，无法访问
                        }
                    }
                    return {found: false, frameIndex: -1};
                }
                
                // 尝试多种选择器
                var selectors = [
                    'button[role="tab"]',
                    '*[class*="rtaOSd"]',
                    'h1[class*="i2Djkc"]'
                ];
                
                for (var s of selectors) {
                    var result = findInAllFrames(s);
                    if (result.found) {
                        return {found: true, frameIndex: result.frameIndex, selector: s};
                    }
                }
                
                return {found: false, frameIndex: -1, selector: null};
            """)
            
            print(f"[频道创建调试] JavaScript查找结果: {js_find_result}")
            
            if js_find_result and js_find_result.get('found'):
                frame_index = js_find_result.get('frameIndex', -1)
                if frame_index >= 0:
                    print(f"[频道创建] ✅ JavaScript在iframe{frame_index}中找到元素")
                    # 切换到该iframe
                    driver.switch_to.default_content()
                    iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    if frame_index < len(iframes):
                        driver.switch_to.frame(iframes[frame_index])
                        switched_to_iframe = True
                        print(f"[频道创建] ✅ 已切换到iframe{frame_index}")
                else:
                    print(f"[频道创建] ✅ JavaScript在主文档中找到元素")
                    
        except Exception as js_error:
            print(f"[频道创建调试] JavaScript查找出错: {str(js_error)}")
        
        # 等待页面稳定，避免操作过快
        print(f"[频道创建] 等待页面完全加载...")
        time.sleep(3)
        
        # 步骤3: 点击"From computer"选项卡
        print(f"[频道创建] 查找'From computer'选项卡...")
        dialog_container = None  # 定义在外层作用域
        
        # 首先尝试在主文档层面使用ActionChains点击（最可靠的方法）
        print(f"[频道创建] 尝试在主文档层面使用ActionChains点击...")
        content_switched_early = False
        try:
            # 确保在主文档
            driver.switch_to.default_content()
            time.sleep(0.5)
            
            # 找到iframe元素
            target_iframe = None
            all_iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in all_iframes:
                try:
                    src = iframe.get_attribute("src") or ""
                    if "profilewidgets.youtube.com" in src and iframe.is_displayed():
                        target_iframe = iframe
                        break
                except:
                    pass
            
            if target_iframe:
                from selenium.webdriver.common.action_chains import ActionChains
                
                # 获取iframe的位置和大小
                iframe_location = target_iframe.location
                iframe_size = target_iframe.size
                
                print(f"[频道创建调试] iframe位置: {iframe_location}, 大小: {iframe_size}")
                
                # "From computer" tab大约在iframe的右上角区域
                # 根据观察，两个tab平分宽度，From computer在右边
                # 估算位置：iframe宽度的75%处，高度约60px（标题下方）
                offset_x = int(iframe_size['width'] * 0.75)
                offset_y = 60  # tab大约在顶部60px处
                
                print(f"[频道创建] 尝试ActionChains点击iframe内偏移位置: ({offset_x}, {offset_y})")
                
                # 移动到iframe，然后偏移到tab位置并点击
                actions = ActionChains(driver)
                actions.move_to_element_with_offset(target_iframe, offset_x, offset_y).click().perform()
                
                print(f"[频道创建] ✅ ActionChains点击完成")
                time.sleep(2)
                
                # 切换到iframe检查结果
                driver.switch_to.frame(target_iframe)
                
                # 检查是否成功
                upload_check = driver.find_elements(By.XPATH, "//*[contains(text(), 'Upload from computer') or contains(text(), 'Drag')]")
                for elem in upload_check:
                    try:
                        if elem.is_displayed():
                            content_switched_early = True
                            print(f"[频道创建] ✅ ActionChains点击成功，检测到上传界面！")
                            break
                    except:
                        pass
                
                if not content_switched_early:
                    # 也检查一下tab状态
                    tab_state = driver.execute_script("""
                        var tabs = document.querySelectorAll('button[role="tab"]');
                        var result = [];
                        for (var t of tabs) {
                            result.push({
                                text: t.innerText,
                                selected: t.getAttribute('aria-selected')
                            });
                        }
                        return result;
                    """)
                    print(f"[频道创建调试] Tab状态: {tab_state}")
                    
                    # 检查From computer是否被选中
                    for tab in tab_state:
                        if 'From computer' in tab.get('text', '') and tab.get('selected') == 'true':
                            content_switched_early = True
                            print(f"[频道创建] ✅ From computer tab已选中")
                            break
                            
                # 切回主文档，准备后续操作
                driver.switch_to.default_content()
                
        except Exception as ac_err:
            print(f"[频道创建调试] ActionChains点击失败: {str(ac_err)}")
            try:
                driver.switch_to.default_content()
            except:
                pass
        
        # 如果早期点击成功了，跳过后续的点击尝试
        if content_switched_early:
            print(f"[频道创建] 早期ActionChains点击成功，跳过其他方法")
            # 切换到iframe继续后续操作
            try:
                target_iframe = driver.find_element(By.CSS_SELECTOR, 'iframe[src*="profilewidgets.youtube.com"]')
                driver.switch_to.frame(target_iframe)
            except:
                pass
        
        # 确保切换到正确的iframe（profilewidgets.youtube.com）
        print(f"[频道创建] 确保在正确的iframe中...")
        try:
            # 先切回主文档
            driver.switch_to.default_content()
            time.sleep(0.5)
            
            # 查找包含profilewidgets的iframe
            all_iframes = driver.find_elements(By.TAG_NAME, "iframe")
            print(f"[频道创建调试] 主文档中发现 {len(all_iframes)} 个iframe")
            
            target_iframe = None
            for idx, iframe in enumerate(all_iframes):
                try:
                    src = iframe.get_attribute("src") or ""
                    if "profilewidgets.youtube.com" in src and iframe.is_displayed():
                        target_iframe = iframe
                        print(f"[频道创建] 找到目标iframe: {src[:80]}...")
                        break
                except:
                    pass
            
            if target_iframe:
                # 切换到目标iframe
                driver.switch_to.frame(target_iframe)
                print(f"[频道创建] ✅ 已切换到profilewidgets iframe")
                time.sleep(1)
            else:
                print(f"[频道创建调试] 未找到profilewidgets iframe，尝试在主文档中操作")
                
        except Exception as iframe_err:
            print(f"[频道创建调试] 切换iframe出错: {str(iframe_err)}")
        
        try:
            # 查找"From computer"选项卡
            # 关键修改：不假设ID是正确的，而是遍历所有包含文本的元素，找到可见的那个
            print(f"[频道创建] 查找可见的'From computer'选项卡...")
            content_switched = False
            
            click_result = driver.execute_script("""
                function isVisible(elem) {
                    if (!elem) return false;
                    var rect = elem.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                }
                
                function clickElement(elem) {
                    // 模拟完整的用户交互事件序列
                    var rect = elem.getBoundingClientRect();
                    var centerX = rect.left + rect.width / 2;
                    var centerY = rect.top + rect.height / 2;
                    
                    var events = [
                        new FocusEvent('focus', {bubbles: true, cancelable: true}),
                        new PointerEvent('pointerenter', {bubbles: true, cancelable: true, clientX: centerX, clientY: centerY}),
                        new PointerEvent('pointerdown', {bubbles: true, cancelable: true, clientX: centerX, clientY: centerY, button: 0, buttons: 1}),
                        new MouseEvent('mousedown', {bubbles: true, cancelable: true, clientX: centerX, clientY: centerY, button: 0, buttons: 1}),
                        new PointerEvent('pointerup', {bubbles: true, cancelable: true, clientX: centerX, clientY: centerY, button: 0, buttons: 0}),
                        new MouseEvent('mouseup', {bubbles: true, cancelable: true, clientX: centerX, clientY: centerY, button: 0, buttons: 0}),
                        new MouseEvent('click', {bubbles: true, cancelable: true, clientX: centerX, clientY: centerY, button: 0})
                    ];
                    
                    for (var evt of events) {
                        elem.dispatchEvent(evt);
                    }
                    elem.click();
                    return true;
                }

                // 1. 尝试通过ID查找
                var tab = document.getElementById('nTuXNc');
                if (isVisible(tab)) {
                    return {success: clickElement(tab), method: 'id', id: tab.id};
                }
                
                // 2. 尝试通过jsname查找
                tab = document.querySelector('button[jsname="zf3vf"]');
                if (isVisible(tab)) {
                    return {success: clickElement(tab), method: 'jsname', id: tab.id};
                }
                
                // 3. 遍历所有 button[role="tab"]
                var tabs = document.querySelectorAll('button[role="tab"]');
                for (var t of tabs) {
                    if (t.innerText.includes('From computer') && isVisible(t)) {
                        return {success: clickElement(t), method: 'role_tab', id: t.id};
                    }
                }
                
                // 4. 遍历所有包含文本的 span
                var spans = document.querySelectorAll('span');
                for (var s of spans) {
                    if (s.innerText.includes('From computer') && isVisible(s)) {
                        // 尝试点击span本身
                        clickElement(s);
                        // 尝试点击最近的button祖先
                        var p = s.closest('button');
                        if (p) clickElement(p);
                        return {success: true, method: 'span_text', tag: s.tagName};
                    }
                }
                
                // 调试信息：输出找到的所有相关元素及其可见性
                var debugInfo = [];
                var allTabs = document.querySelectorAll('button[role="tab"]');
                for (var t of allTabs) {
                    var r = t.getBoundingClientRect();
                    debugInfo.push({tag: t.tagName, text: t.innerText.substring(0, 20), w: r.width, h: r.height, id: t.id});
                }
                
                return {success: false, error: 'No visible element found', debug: debugInfo};
            """)
            
            print(f"[频道创建调试] JavaScript查找点击结果: {click_result}")
            
            if click_result and click_result.get('success'):
                print(f"[频道创建] ✅ 已通过JavaScript找到并点击元素 (Method: {click_result.get('method')})")
                time.sleep(2)
                
                # 验证
                upload_check = driver.find_elements(By.XPATH, "//*[contains(text(), 'Upload from computer') or contains(text(), 'Drag')]")
                for elem in upload_check:
                    try:
                        if elem.is_displayed():
                            content_switched = True
                            print(f"[频道创建] ✅ 检测到上传界面！")
                            break
                    except:
                        pass
            
            # 如果上面失败了，尝试CDP坐标点击（分步获取坐标）
            if not content_switched:
                print(f"[频道创建] 尝试CDP坐标点击（分步获取坐标）...")
                try:
                    # 步骤1: 在iframe中获取元素的相对坐标（当前应该已经在iframe中）
                    tab_rect = driver.execute_script("""
                        var tab = document.getElementById('nTuXNc') || 
                                  document.querySelector('button[jsname="zf3vf"]');
                        
                        if (!tab) {
                            var tabs = document.querySelectorAll('button[role="tab"]');
                            for (var t of tabs) {
                                if (t.innerText.includes('From computer')) {
                                    tab = t;
                                    break;
                                }
                            }
                        }
                        
                        if (!tab) {
                            return null;
                        }
                        
                        var rect = tab.getBoundingClientRect();
                        return {
                            x: rect.left + rect.width / 2,
                            y: rect.top + rect.height / 2,
                            width: rect.width,
                            height: rect.height,
                            left: rect.left,
                            top: rect.top
                        };
                    """)
                    
                    print(f"[频道创建调试] iframe内元素坐标: {tab_rect}")
                    
                    if tab_rect and tab_rect.get('width', 0) > 0:
                        # 步骤2: 切回主文档获取iframe的位置
                        driver.switch_to.default_content()
                        
                        iframe_rect = driver.execute_script("""
                            var iframe = document.querySelector('iframe[src*="profilewidgets.youtube.com"]');
                            if (!iframe) {
                                return null;
                            }
                            var rect = iframe.getBoundingClientRect();
                            return {
                                x: rect.left,
                                y: rect.top,
                                width: rect.width,
                                height: rect.height
                            };
                        """)
                        
                        print(f"[频道创建调试] iframe坐标: {iframe_rect}")
                        
                        if iframe_rect:
                            # 步骤3: 计算绝对坐标
                            abs_x = iframe_rect['x'] + tab_rect['x']
                            abs_y = iframe_rect['y'] + tab_rect['y']
                            
                            print(f"[频道创建] 执行CDP点击: iframe({iframe_rect['x']}, {iframe_rect['y']}) + tab({tab_rect['x']}, {tab_rect['y']}) = ({abs_x}, {abs_y})")
                            
                            # 步骤4: 使用CDP执行真实点击
                            driver.execute_cdp_cmd('Input.dispatchMouseEvent', {
                                'type': 'mousePressed',
                                'x': abs_x,
                                'y': abs_y,
                                'button': 'left',
                                'clickCount': 1
                            })
                            time.sleep(0.1)
                            driver.execute_cdp_cmd('Input.dispatchMouseEvent', {
                                'type': 'mouseReleased',
                                'x': abs_x,
                                'y': abs_y,
                                'button': 'left',
                                'clickCount': 1
                            })
                            
                            print(f"[频道创建] ✅ CDP坐标点击完成")
                            time.sleep(2)
                            
                            # 切回iframe检查结果
                            target_iframe = driver.find_element(By.CSS_SELECTOR, 'iframe[src*="profilewidgets.youtube.com"]')
                            driver.switch_to.frame(target_iframe)
                            
                            # 检查是否成功
                            upload_check = driver.find_elements(By.XPATH, "//*[contains(text(), 'Upload from computer') or contains(text(), 'Drag')]")
                            for elem in upload_check:
                                try:
                                    if elem.is_displayed():
                                        content_switched = True
                                        print(f"[频道创建] ✅ CDP点击成功，检测到上传界面")
                                        break
                                except:
                                    pass
                        else:
                            print(f"[频道创建调试] 无法获取iframe坐标")
                            # 切回iframe
                            target_iframe = driver.find_element(By.CSS_SELECTOR, 'iframe[src*="profilewidgets.youtube.com"]')
                            driver.switch_to.frame(target_iframe)
                    else:
                        print(f"[频道创建调试] 无法获取元素坐标: {tab_rect}")
                        
                except Exception as cdp_err:
                    print(f"[频道创建调试] CDP坐标点击失败: {str(cdp_err)}")
                    # 确保切回iframe
                    try:
                        driver.switch_to.default_content()
                        target_iframe = driver.find_element(By.CSS_SELECTOR, 'iframe[src*="profilewidgets.youtube.com"]')
                        driver.switch_to.frame(target_iframe)
                    except:
                        pass
            
            # 备用方法5：直接在iframe中使用pyautogui风格的点击
            if not content_switched:
                print(f"[频道创建] 尝试最后的点击方法...")
                try:
                    # 确保在iframe中
                    # 尝试使用Selenium的execute_script直接调用元素的click
                    result = driver.execute_script("""
                        // 找到From computer tab
                        var tab = document.getElementById('nTuXNc') || 
                                  document.querySelector('button[jsname="zf3vf"]');
                        
                        if (!tab) {
                            var tabs = document.querySelectorAll('button[role="tab"]');
                            for (var t of tabs) {
                                if (t.innerText.includes('From computer')) {
                                    tab = t;
                                    break;
                                }
                            }
                        }
                        
                        if (!tab) {
                            return {success: false, error: 'tab not found'};
                        }
                        
                        // 获取Illustrations tab
                        var illustrationsTab = null;
                        var tabs = document.querySelectorAll('button[role="tab"]');
                        for (var t of tabs) {
                            if (t.innerText.includes('Illustrations')) {
                                illustrationsTab = t;
                                break;
                            }
                        }
                        
                        // 模拟真实的tab切换：先取消选中Illustrations，再选中From computer
                        if (illustrationsTab) {
                            illustrationsTab.setAttribute('aria-selected', 'false');
                            illustrationsTab.setAttribute('tabindex', '-1');
                        }
                        
                        tab.setAttribute('aria-selected', 'true');
                        tab.setAttribute('tabindex', '0');
                        
                        // 触发所有可能的事件
                        tab.focus();
                        
                        // 创建并分发各种事件
                        ['mouseenter', 'mouseover', 'mousedown', 'mouseup', 'click'].forEach(function(eventType) {
                            var event = new MouseEvent(eventType, {
                                view: window,
                                bubbles: true,
                                cancelable: true,
                                composed: true
                            });
                            tab.dispatchEvent(event);
                        });
                        
                        // 触发change事件（某些框架需要）
                        tab.dispatchEvent(new Event('change', {bubbles: true}));
                        
                        // 触发input事件
                        tab.dispatchEvent(new Event('input', {bubbles: true}));
                        
                        // 触发自定义事件（Google可能使用）
                        tab.dispatchEvent(new CustomEvent('action', {bubbles: true, detail: {type: 'click'}}));
                        
                        return {
                            success: true, 
                            ariaSelected: tab.getAttribute('aria-selected'),
                            method: 'comprehensive_events'
                        };
                    """)
                    
                    print(f"[频道创建调试] 综合事件触发结果: {result}")
                    time.sleep(2)
                    
                    # 检查是否成功
                    upload_check = driver.find_elements(By.XPATH, "//*[contains(text(), 'Upload from computer') or contains(text(), 'Drag')]")
                    for elem in upload_check:
                        try:
                            if elem.is_displayed():
                                content_switched = True
                                print(f"[频道创建] ✅ 综合事件触发成功，检测到上传界面")
                                break
                        except:
                            pass
                            
                except Exception as final_err:
                    print(f"[频道创建调试] 最后的点击方法失败: {str(final_err)}")
            
            # 标记为已处理
            from_computer_tab = "processed"
            add_channel_log(account_id, browser_env_id, 'info', '已尝试切换到From computer选项卡')
                
        except Exception as e:
            error_msg = f"处理'From computer'选项卡时出错: {str(e)}"
            print(f"[频道创建错误] {error_msg}")
            import traceback
            traceback.print_exc()
            add_channel_log(account_id, browser_env_id, 'failed', error_msg)
            return "failed", "无法切换到From computer选项卡"
        
        # 确保切换完成后再查找弹窗容器
        try:
            possible_dialogs = driver.find_elements(By.XPATH, "//dialog | //*[@role='dialog']")
            for dialog in possible_dialogs:
                if dialog.is_displayed():
                    dialog_container = dialog
                    break
        except:
            pass
        
        # 步骤4: 查找并点击"Upload from computer"按钮
        print(f"[频道创建] 查找'Upload from computer'按钮...")
        upload_btn = None
        
        try:
            # 等待一下确保内容加载
            time.sleep(2)
            
            # 方式1: 直接查找包含特定文本的按钮（最直接）
            try:
                # 查找所有可见的按钮
                all_buttons = driver.find_elements(By.XPATH, "//button")
                print(f"[频道创建调试] 页面上共有 {len(all_buttons)} 个按钮")
                
                visible_buttons = []
                for btn in all_buttons:
                    try:
                        if btn.is_displayed():
                            btn_text = btn.text
                            # 检查是否包含"Upload from computer"
                            if "Upload from computer" in btn_text or "upload from computer" in btn_text.lower():
                                upload_btn = btn
                                print(f"[频道创建] ✅ 找到'Upload from computer'按钮（文本匹配）")
                                break
                            
                            # 记录所有可见按钮用于调试
                            if btn_text:
                                visible_buttons.append({
                                    'text': btn_text,
                                    'aria-label': btn.get_attribute("aria-label") or "",
                                    'class': (btn.get_attribute("class") or "")[:50]
                                })
                    except:
                        pass
                
                if not upload_btn:
                    print(f"[频道创建调试] 未找到'Upload from computer'按钮，输出所有可见按钮:")
                    for i, btn_info in enumerate(visible_buttons[:20]):
                        print(f"[频道创建调试] 按钮{i+1}: text='{btn_info['text']}', aria='{btn_info['aria-label']}'")
                        
            except Exception as e:
                print(f"[频道创建] 方式1查找失败: {str(e)}")
            
            # 方式2: 通过包含"Upload"和"computer"关键词的按钮
            if not upload_btn:
                try:
                    all_buttons = driver.find_elements(By.TAG_NAME, "button")
                    for btn in all_buttons:
                        if btn.is_displayed():
                            btn_text = btn.text.lower()
                            if "upload" in btn_text and "computer" in btn_text:
                                upload_btn = btn
                                print(f"[频道创建] ✅ 找到包含upload和computer的按钮: '{btn.text}'")
                                break
                except Exception as e:
                    print(f"[频道创建] 方式2查找失败: {str(e)}")
            
            # 方式3: 查找特定class的按钮（从源码分析可能的class模式）
            if not upload_btn:
                try:
                    # 尝试查找AeBiU开头的按钮class（Google Material Design按钮）
                    buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'AeBiU') or contains(@class, 'VfPpkd')]")
                    for btn in buttons:
                        if btn.is_displayed():
                            btn_text = btn.text.lower()
                            if "upload" in btn_text:
                                upload_btn = btn
                                print(f"[频道创建] ✅ 通过class找到上传按钮: '{btn.text}'")
                                break
                except:
                    pass
        
        except Exception as e:
            print(f"[频道创建错误] 查找按钮过程出错: {str(e)}")
            import traceback
            traceback.print_exc()
        
        if not upload_btn:
            error_msg = "找不到'Upload from computer'按钮，可能需要先切换到From computer选项卡"
            print(f"[频道创建错误] {error_msg}")
            add_channel_log(account_id, browser_env_id, 'failed', error_msg)
            return "failed", error_msg
        
        # 点击Upload from computer按钮
        print(f"[频道创建] 准备点击'Upload from computer'按钮...")
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", upload_btn)
            time.sleep(1)
            upload_btn.click()
            print(f"[频道创建] 已点击'Upload from computer'按钮")
            add_channel_log(account_id, browser_env_id, 'info', '已点击Upload from computer按钮')
        except:
            try:
                driver.execute_script("arguments[0].click();", upload_btn)
                print(f"[频道创建] 已点击'Upload from computer'按钮（JS方式）")
                add_channel_log(account_id, browser_env_id, 'info', '已点击Upload from computer按钮（JS方式）')
            except Exception as click_error:
                error_msg = f"点击Upload from computer按钮失败: {str(click_error)}"
                print(f"[频道创建错误] {error_msg}")
                add_channel_log(account_id, browser_env_id, 'failed', error_msg)
                return "failed", error_msg
        
        time.sleep(2)
        
        # 步骤8: 在文件选择器中输入图片路径
        print(f"[频道创建] 查找文件上传input...")
        try:
            # 使用强大的JavaScript递归查找input[type='file']，支持Shadow DOM和iframe
            file_input_info = driver.execute_script("""
                function findFileInput(root, depth = 0) {
                    if (depth > 20) return null; // 防止死循环
                    
                    // 1. 检查当前root下的input
                    var inputs = root.querySelectorAll('input[type="file"]');
                    if (inputs.length > 0) {
                        return {found: true, type: 'direct', element: inputs[0]};
                    }
                    
                    // 2. 检查Shadow DOM
                    var walker = document.createTreeWalker(
                        root, 
                        NodeFilter.SHOW_ELEMENT, 
                        null, 
                        false
                    );
                    
                    while(walker.nextNode()) {
                        var node = walker.currentNode;
                        if (node.shadowRoot) {
                            var result = findFileInput(node.shadowRoot, depth + 1);
                            if (result) return result;
                        }
                    }
                    
                    return null;
                }
                
                // 在主文档查找
                var result = findFileInput(document.body);
                if (result) return result;
                
                // 遍历所有iframe
                var iframes = document.querySelectorAll('iframe');
                for (var i = 0; i < iframes.length; i++) {
                    try {
                        var iframeDoc = iframes[i].contentDocument || iframes[i].contentWindow.document;
                        if (iframeDoc) {
                            var iframeResult = findFileInput(iframeDoc.body);
                            if (iframeResult) {
                                return {found: true, type: 'iframe', index: i, element: iframeResult.element};
                            }
                        }
                    } catch(e) {
                        // 跨域访问限制，忽略
                    }
                }
                
                return null;
            """)
            
            print(f"[频道创建调试] input file查找结果: {file_input_info}")
            
            file_input = None
            if file_input_info and file_input_info.get('found'):
                if file_input_info.get('type') == 'iframe':
                    # 如果在iframe中，需要切换过去
                    iframe_index = file_input_info.get('index')
                    print(f"[频道创建] input在iframe {iframe_index} 中，切换上下文...")
                    driver.switch_to.default_content()
                    all_iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    if len(all_iframes) > iframe_index:
                        driver.switch_to.frame(all_iframes[iframe_index])
                        # 再次查找（因为切换了上下文，element引用可能失效）
                        file_input = driver.find_element(By.XPATH, "//input[@type='file']")
                else:
                    # 在当前文档或Shadow DOM中
                    # 注意：如果是在Shadow DOM中，Selenium直接find_element可能找不到
                    # 这里简化处理，如果是direct找到的（execute_script返回的element），直接使用
                    file_input = file_input_info.get('element')
            
            # 如果JS查找失败，尝试回退到暴力遍历iframe查找
            if not file_input:
                print(f"[频道创建] JS查找失败，尝试遍历iframe查找...")
                all_iframes = driver.find_elements(By.TAG_NAME, "iframe")
                
                # 先检查当前位置
                try:
                    inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
                    if inputs:
                        file_input = inputs[0]
                        print(f"[频道创建] 在当前上下文中找到input")
                except:
                    pass
                
                if not file_input:
                    for i, iframe in enumerate(all_iframes):
                        try:
                            driver.switch_to.default_content()
                            driver.switch_to.frame(iframe)
                            inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
                            if inputs:
                                file_input = inputs[0]
                                print(f"[频道创建] ✅ 在iframe {i} 中找到文件上传input")
                                break
                        except:
                            pass

            # 如果最终找到了input
            if file_input:
                # 确保input没有被disabled，并尝试显示它（以便调试）
                driver.execute_script("""
                    arguments[0].removeAttribute('disabled');
                    arguments[0].style.display = 'block';
                    arguments[0].style.visibility = 'visible';
                    arguments[0].style.opacity = '1';
                    arguments[0].style.width = '1px';
                    arguments[0].style.height = '1px';
                """, file_input)
                
                # 直接设置文件路径
                file_input.send_keys(avatar_path)
                print(f"[频道创建] 已设置头像文件路径: {avatar_path}")
                add_channel_log(account_id, browser_env_id, 'info', f'已选择头像文件: {os.path.basename(avatar_path)}')
                
                # 恢复到profilewidgets iframe（为了点击Done按钮）
                try:
                    time.sleep(1)
                    driver.switch_to.default_content()

                    # 重新查找目标iframe
                    target_iframe = None
                    all_iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    for iframe in all_iframes:
                        if "profilewidgets.youtube.com" in (iframe.get_attribute("src") or ""):
                            target_iframe = iframe
                            break

                    if target_iframe:
                        driver.switch_to.frame(target_iframe)
                    else:
                        print(f"[频道创建警告] 未找到profilewidgets iframe，Done按钮点击可能失败")
                except Exception as e:
                    print(f"[频道创建警告] 恢复iframe上下文失败: {str(e)}")
            else:
                print(f"[频道创建警告] 在任何位置都未找到input[type='file']，尝试处理系统弹窗...")
                
                # 尝试使用 pyautogui 处理系统弹窗
                if handle_system_upload_dialog(avatar_path):
                    print(f"[频道创建] 系统弹窗处理完成，直接等待裁剪界面...")
                    add_channel_log(account_id, browser_env_id, 'info', '已通过系统弹窗上传头像')
                    # 不做任何等待，直接跳到等待裁剪界面的步骤
                else:
                    return "failed", "无法定位文件上传控件且系统交互失败"
            
            # 步骤9: 等待裁剪界面 - 使用纯等待，不轮询DOM以避免干扰
            print(f"[频道创建] 等待裁剪界面加载（纯等待模式，不干扰浏览器）...")
            print(f"[频道创建] 等待15秒让裁剪界面完全加载...")
            
            # 关键：使用纯 time.sleep，不做任何 Selenium 操作
            # 这样可以避免干扰正在进行的上传和界面渲染
            for i in range(15):
                time.sleep(1)
                if i % 5 == 4:  # 每5秒打印一次进度
                    print(f"[频道创建] 已等待 {i+1} 秒...")
            
            print(f"[频道创建] 等待完成，开始查找裁剪界面Done按钮...")
            
            # 步骤10: 查找裁剪界面的Done按钮 (jsname="yTKzd")
            done_button = None
            
            # 使用温和的方式查找，每次尝试间隔较长
            for attempt in range(6):  # 尝试6次，每次间隔3秒
                try:
                    done_button = driver.find_element(By.CSS_SELECTOR, 'button[jsname="yTKzd"]')
                    if done_button and done_button.is_displayed():
                        print(f"[频道创建] ✅ 通过jsname找到裁剪界面Done按钮")
                        break
                except:
                    pass
                
                # 备用：通过文本查找
                if not done_button:
                    try:
                        buttons = driver.find_elements(By.TAG_NAME, "button")
                        for btn in buttons:
                            try:
                                if btn.is_displayed() and "Done" in btn.text:
                                    # 确保是裁剪界面的Done按钮，不是确认弹窗的
                                    parent_html = btn.get_attribute("outerHTML")
                                    if 'jsname="yTKzd"' in parent_html or 'jslog="89765"' in parent_html:
                                        done_button = btn
                                        print(f"[频道创建] ✅ 通过文本找到裁剪界面Done按钮")
                                        break
                            except:
                                pass
                    except:
                        pass
                
                if done_button:
                    break
                    
                if attempt < 5:
                    print(f"[频道创建] 第{attempt+1}次未找到Done按钮，等待3秒后重试...")
                    time.sleep(3)
            
            if done_button:
                print(f"[频道创建] 找到裁剪界面Done按钮，准备点击...")
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", done_button)
                    time.sleep(0.5)
                    done_button.click()
                    print(f"[频道创建] 已点击裁剪界面Done按钮")
                except:
                    try:
                        driver.execute_script("arguments[0].click();", done_button)
                        print(f"[频道创建] 已点击裁剪界面Done按钮（JS方式）")
                    except Exception as e:
                        print(f"[频道创建警告] 点击Done按钮失败: {str(e)}")
                
                time.sleep(2)
                
                # 步骤11: 处理确认对话框 - 点击 "Save as profile picture" 按钮
                print(f"[频道创建] 查找'Save as profile picture'按钮...")
                save_button = None
                
                try:
                    # 通过jsname查找 (jsname="WCwAu")
                    save_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[jsname="WCwAu"]'))
                    )
                    print(f"[频道创建] 通过jsname找到Save按钮")
                except:
                    pass
                
                # 方法2: 通过文本查找
                if not save_button:
                    try:
                        buttons = driver.find_elements(By.TAG_NAME, "button")
                        for btn in buttons:
                            try:
                                btn_text = btn.text.lower()
                                if btn.is_displayed() and ("save as profile" in btn_text or "save" in btn_text):
                                    save_button = btn
                                    print(f"[频道创建] 通过文本找到Save按钮: {btn.text}")
                                    break
                            except:
                                pass
                    except:
                        pass
                
                if save_button:
                    print(f"[频道创建] 找到Save按钮，准备点击...")
                    try:
                        save_button.click()
                        print(f"[频道创建] 已点击'Save as profile picture'按钮")
                    except:
                        try:
                            driver.execute_script("arguments[0].click();", save_button)
                            print(f"[频道创建] 已点击'Save as profile picture'按钮（JS方式）")
                        except Exception as e:
                            print(f"[频道创建警告] 点击Save按钮失败: {str(e)}")
                    
                    add_channel_log(account_id, browser_env_id, 'success', '头像上传成功')
                else:
                    print(f"[频道创建警告] 未找到Save按钮，可能已自动保存")
            else:
                print(f"[频道创建警告] 未找到裁剪界面Done按钮")
                # 输出当前页面所有可见按钮用于调试
                try:
                    buttons = driver.find_elements(By.TAG_NAME, "button")
                    visible_btns = []
                    for btn in buttons[:30]:
                        try:
                            if btn.is_displayed() and btn.text.strip():
                                visible_btns.append(btn.text.strip()[:30])
                        except:
                            pass
                    print(f"[频道创建调试] 当前可见按钮: {visible_btns}")
                except:
                    pass
            
            # 切回主文档
            try:
                driver.switch_to.default_content()
            except:
                pass
            
            # 等待保存完成
            time.sleep(3)
            print(f"[频道创建] ✅ 头像上传流程完成")
            
        except Exception as e:
            error_msg = f"上传头像文件失败: {str(e)}"
            print(f"[频道创建错误] {error_msg}")
            add_channel_log(account_id, browser_env_id, 'failed', error_msg)
            import traceback
            traceback.print_exc()
            return "failed", "头像上传失败"
        
        # === 步骤12: 填写频道名称 ===
        print(f"[频道创建-步骤12] 填写频道名称...")
        add_channel_log(account_id, browser_env_id, 'info', '步骤12: 填写频道名称')
        try:
            # 生成随机名称
            channel_name = get_random_name(10)
            print(f"[频道创建-步骤12] 生成的频道名称: {channel_name}")
            add_channel_log(account_id, browser_env_id, 'info', f'步骤12: 生成频道名称 [{channel_name}]')
            
            # 查找Name输入框（第一个有maxlength="50"的输入框）
            print(f"[频道创建-步骤12] 查找Name输入框...")
            try:
                name_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@maxlength='50' and @required]"))
                )
                print(f"[频道创建-步骤12] 找到Name输入框")
            except:
                # 备用方式：通过aria-labelledby查找
                try:
                    name_input = driver.find_element(By.XPATH, "//input[@aria-labelledby='paper-input-label-1']")
                    print(f"[频道创建-步骤12] 通过aria-labelledby找到Name输入框")
                except:
                    # 最后尝试：找所有required的input，取第一个
                    inputs = driver.find_elements(By.XPATH, "//input[@required and contains(@class, 'tp-yt-paper-input')]")
                    if inputs:
                        name_input = inputs[0]
                        print(f"[频道创建-步骤12] 通过required属性找到Name输入框")
                    else:
                        error_msg = "步骤12失败: 未找到Name输入框"
                        print(f"[频道创建-步骤12-错误] {error_msg}")
                        add_channel_log(account_id, browser_env_id, 'failed', error_msg)
                        return "failed", "未找到频道名称输入框"
            
            # 滚动到输入框
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", name_input)
            time.sleep(1)
            
            # 输入名称
            print(f"[频道创建-步骤12] 输入频道名称...")
            try:
                name_input.click()
                time.sleep(0.5)
                name_input.clear()
                name_input.send_keys(channel_name)
                print(f"[频道创建-步骤12] ✅ 已输入频道名称: {channel_name}")
                add_channel_log(account_id, browser_env_id, 'success', f'步骤12完成: 已输入频道名称 [{channel_name}]')
            except:
                # 使用JS方式
                driver.execute_script(f"arguments[0].value = '{channel_name}';", name_input)
                driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", name_input)
                driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", name_input)
                print(f"[频道创建-步骤12] ✅ 已输入频道名称（JS方式）: {channel_name}")
                add_channel_log(account_id, browser_env_id, 'success', f'步骤12完成: 已输入频道名称（JS方式）[{channel_name}]')
            
            time.sleep(2)
            # Handle会根据频道名称自动生成，不需要手动填写
            
        except Exception as e:
            error_msg = f"填写频道名称失败: {str(e)}"
            print(f"[频道创建错误] {error_msg}")
            import traceback
            traceback.print_exc()
            return "failed", error_msg
        
        # 13. 点击"Create channel"按钮
        print(f"[频道创建] 查找并点击'Create channel'按钮...")
        add_channel_log(account_id, browser_env_id, 'info', '查找Create channel按钮')
        try:
            create_channel_button = None
            
            try:
                # 方式1: 通过aria-label查找（最准确）
                create_channel_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Create channel' or @aria-label='创建频道']"))
                )
                print(f"[频道创建] 通过aria-label找到'Create channel'按钮")
            except:
                try:
                    # 方式2: 通过包含特定class和文本的按钮
                    create_channel_button = driver.find_element(By.XPATH, "//button[contains(@class, 'yt-spec-button-shape-next--call-to-action')]//span[contains(text(), 'Create channel')]/..")
                    print(f"[频道创建] 通过class和文本找到'Create channel'按钮")
                except:
                    try:
                        # 方式3: 查找id为create-channel-button的元素下的button
                        create_channel_button = driver.find_element(By.XPATH, "//ytd-button-renderer[@id='create-channel-button']//button")
                        print(f"[频道创建] 通过id找到'Create channel'按钮")
                    except:
                        # 方式4: 查找所有button，找包含create channel的
                        buttons = driver.find_elements(By.TAG_NAME, "button")
                        for btn in buttons:
                            aria_label = btn.get_attribute("aria-label") or ""
                            btn_text = btn.text or ""
                            if btn.is_displayed() and (
                                "create channel" in aria_label.lower() or 
                                "create channel" in btn_text.lower() or 
                                "创建频道" in aria_label or 
                                "创建频道" in btn_text
                            ):
                                create_channel_button = btn
                                print(f"[频道创建] 通过遍历找到'Create channel'按钮")
                                break
            
            if not create_channel_button:
                error_msg = "步骤13失败: 未找到'Create channel'按钮"
                print(f"[频道创建-步骤13-错误] {error_msg}")
                add_channel_log(account_id, browser_env_id, 'failed', error_msg)
                return "failed", "未找到创建频道按钮"
            
            # 滚动到按钮
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", create_channel_button)
            time.sleep(1)
            
            # === 步骤13: 点击Create channel按钮 ===
            print(f"[频道创建-步骤13] 点击'Create channel'按钮...")
            add_channel_log(account_id, browser_env_id, 'info', '步骤13: 点击Create channel按钮')
            try:
                create_channel_button.click()
                print(f"[频道创建-步骤13] ✅ 已点击'Create channel'按钮")
                add_channel_log(account_id, browser_env_id, 'success', '步骤13完成: 已点击Create channel按钮，等待创建完成')
            except:
                driver.execute_script("arguments[0].click();", create_channel_button)
                print(f"[频道创建-步骤13] ✅ 已点击'Create channel'按钮（JS方式）")
                add_channel_log(account_id, browser_env_id, 'success', '步骤13完成: 已点击Create channel按钮（JS方式）')
            
            # 等待频道创建完成
            print(f"[频道创建-步骤13] 等待频道创建完成...")
            time.sleep(10)
            
        except Exception as e:
            error_msg = f"步骤13失败: 点击'Create channel'按钮失败: {str(e)}"
            print(f"[频道创建-步骤13-错误] {error_msg}")
            import traceback
            traceback.print_exc()
            add_channel_log(account_id, browser_env_id, 'failed', error_msg)
            return "failed", error_msg
        
        # === 步骤14: 检查频道是否创建成功 ===
        print(f"[频道创建-步骤14] 检查频道是否创建成功...")
        add_channel_log(account_id, browser_env_id, 'info', '步骤14: 检查频道创建结果')
        try:
            current_url = driver.current_url
            print(f"[频道创建-步骤14] 创建后URL: {current_url}")
            
            # 检查URL或页面元素判断是否成功
            # 成功的话通常会跳转到频道页面或Studio页面
            if "channel" in current_url.lower() or "studio" in current_url.lower():
                print(f"[频道创建-步骤14] ✅ 频道创建成功")
                add_channel_log(account_id, browser_env_id, 'success', '步骤14: 检测到频道创建成功')
                channel_url = current_url
                print(f"[频道创建] 频道链接: {channel_url}")
                
                # 15. 检测创收要求（3m或10m）
                monetization_req = None
                try:
                    print(f"[频道创建] 开始检测创收要求...")
                    monetization_req = detect_monetization_requirement(driver, channel_url, account_id, browser_env_id)
                    if monetization_req:
                        print(f"[频道创建] ✅ 创收要求检测成功: {monetization_req}")
                    else:
                        print(f"[频道创建] ⚠️ 创收要求检测失败，将保存为空")
                except Exception as detect_error:
                    print(f"[频道创建警告] 检测创收要求失败: {str(detect_error)}")
                    import traceback
                    traceback.print_exc()
                
                # 16. 保存频道信息到数据库（包括创收要求）
                try:
                    from models import Account
                    account = Account.query.get(account_id)
                    if account:
                        account.channel_status = 'created'
                        account.channel_url = channel_url
                        account.monetization_requirement = monetization_req
                        db.session.commit()
                        print(f"[频道创建] ✅ 已保存频道信息到数据库（创收要求: {monetization_req or '未检测到'}）")
                except Exception as db_error:
                    print(f"[频道创建警告] 保存频道信息失败: {str(db_error)}")
                
                # 17. 删除使用的头像
                try:
                    if avatar_path and os.path.exists(avatar_path):
                        os.remove(avatar_path)
                        print(f"[频道创建] 已删除使用的头像: {avatar_path}")
                        add_channel_log(account_id, browser_env_id, 'info', f'已删除使用的头像: {os.path.basename(avatar_path)}')
                except Exception as del_error:
                    print(f"[频道创建警告] 删除头像失败: {str(del_error)}")
                
                success_msg = f"✅ 频道创建成功！名称: {channel_name}, 链接: {channel_url}, 创收要求: {monetization_req or '未检测到'}"
                print(f"[频道创建-步骤14] {success_msg}")
                add_channel_log(account_id, browser_env_id, 'success', f'步骤14完成: {success_msg}')
                return "success", success_msg
            else:
                # 检查是否有错误提示
                try:
                    error_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'error') or contains(text(), 'Error') or contains(text(), '错误')]")
                    if error_elements:
                        error_text = " ".join([elem.text for elem in error_elements if elem.text])
                        error_msg = f"步骤14失败: 检测到错误: {error_text}"
                        print(f"[频道创建-步骤14-错误] {error_msg}")
                        # 更新数据库状态为失败
                        try:
                            from models import Account
                            account = Account.query.get(account_id)
                            if account:
                                account.channel_status = 'failed'
                                db.session.commit()
                        except:
                            pass
                        add_channel_log(account_id, browser_env_id, 'failed', error_msg)
                        return "failed", f"频道创建失败: {error_text}"
                except:
                    pass
                
                error_msg = f"步骤14失败: 未明确确认频道创建成功，当前URL: {current_url}"
                print(f"[频道创建-步骤14-错误] {error_msg}")
                add_channel_log(account_id, browser_env_id, 'failed', error_msg)
                return "failed", "频道创建状态不明确，请手动检查"
            
        except Exception as e:
            error_msg = f"步骤14失败: 检查创建结果失败: {str(e)}"
            print(f"[频道创建-步骤14-错误] {error_msg}")
            add_channel_log(account_id, browser_env_id, 'failed', error_msg)
            return "failed", error_msg
        
    except Exception as e:
        error_msg = f"创建频道过程发生未预期的异常: {str(e)}"
        print(f"[频道创建-异常] {error_msg}")
        import traceback
        traceback.print_exc()
        add_channel_log(account_id, browser_env_id, 'failed', f'频道创建异常: {str(e)}')
        
        # 如果出错且头像已获取，尝试删除（可选）
        # 如果不确定是否使用了头像，可以选择不删除
        
        return "failed", error_msg


# 批量任务停止标志
stop_batch_tasks = False


def batch_create_channel_task(app, account_ids):
    """批量创建频道任务（速率控制：最多3个并发，间隔1-2秒）"""
    import random
    import threading
    from queue import Queue
    from models import Account
    from services import hubstudio_service
    
    global stop_batch_tasks
    stop_batch_tasks = False
    
    with app.app_context():
        print(f"\n========== 开始批量创建频道 {len(account_ids)} 个账号 ==========")
        
        # 创建任务队列
        task_queue = Queue()
        for account_id in account_ids:
            task_queue.put(account_id)
        
        # 工作线程函数
        def worker():
            with app.app_context():
                while not task_queue.empty() and not stop_batch_tasks:
                    driver = None
                    account_id = None
                    browser_env_id = None
                    
                    try:
                        account_id = task_queue.get(timeout=1)
                        print(f"[批量创建频道] 开始处理账号 ID: {account_id}")
                        
                        # 获取账号信息
                        account = Account.query.get(account_id)
                        if not account:
                            print(f"[批量创建频道错误] 账号不存在: ID {account_id}")
                            task_queue.task_done()
                            continue
                        
                        # 检查是否已登录
                        if account.login_status not in ['success', 'success_with_verification']:
                            add_channel_log(account_id, None, 'failed', '账号未登录，无法创建频道')
                            print(f"[批量创建频道] 账号 {account.account} 未登录")
                            task_queue.task_done()
                            continue
                        
                        # 检查是否有绑定的浏览器环境
                        if not account.browser_env_id:
                            add_channel_log(account_id, None, 'failed', '账号未绑定浏览器环境')
                            print(f"[批量创建频道] 账号 {account.account} 未绑定浏览器环境")
                            task_queue.task_done()
                            continue
                        
                        browser_env_id = account.browser_env_id
                        
                        # 判断是创建频道还是检测创收要求
                        is_channel_created = account.channel_status == 'created' and account.channel_url
                        
                        if is_channel_created:
                            # 已创建频道，执行检测操作
                            print(f"[批量创建频道] 账号 {account.account} 已有频道，开始检测创收要求...")
                            add_channel_log(account_id, browser_env_id, 'info', '开始检测创收要求')
                            
                            # 打开浏览器
                            driver = hubstudio_service.open_browser(browser_env_id)
                            if not driver:
                                add_channel_log(account_id, browser_env_id, 'failed', '浏览器启动失败')
                                print(f"[批量创建频道错误] 浏览器启动失败")
                                task_queue.task_done()
                                continue
                            
                            # 检测创收要求
                            result = detect_monetization_requirement(driver, account.channel_url, account_id, browser_env_id)
                            
                            if result:
                                account.monetization_requirement = result
                                db.session.commit()
                                add_channel_log(account_id, browser_env_id, 'success', f'检测成功，创收要求: {result}')
                                print(f"[批量创建频道] 检测成功: {result}")
                            else:
                                add_channel_log(account_id, browser_env_id, 'failed', '无法检测创收要求')
                                print(f"[批量创建频道] 检测失败")
                        else:
                            # 未创建频道，执行创建操作
                            print(f"[批量创建频道] 账号 {account.account} 开始创建频道...")
                            
                            # 检查头像可用性 (返回元组: 是否可用, 可用数量, 错误信息)
                            is_available, avatar_count, error_msg = check_avatar_availability()
                            if not is_available:
                                add_channel_log(account_id, browser_env_id, 'failed', error_msg)
                                print(f"[批量创建频道错误] {error_msg}")
                                task_queue.task_done()
                                continue
                            
                            # 打开浏览器
                            driver = hubstudio_service.open_browser(browser_env_id)
                            if not driver:
                                add_channel_log(account_id, browser_env_id, 'failed', '浏览器启动失败')
                                print(f"[批量创建频道错误] 浏览器启动失败")
                                task_queue.task_done()
                                continue
                            
                            # 创建频道
                            channel_status, result_msg = create_youtube_channel(driver, account_id, browser_env_id)
                            
                            # 更新账号状态
                            if channel_status == "success":
                                # 从result_msg中提取频道URL（但create_youtube_channel已经保存到数据库了，这里可能是冗余的）
                                # 注意：create_youtube_channel函数内部已经更新了数据库，这里实际上不需要再次更新
                                # 但为了保持一致性，我们刷新账号对象
                                db.session.refresh(account)
                                print(f"[批量创建频道] 频道创建成功: {account.channel_url}")
                            else:
                                account.channel_status = 'failed'
                                db.session.commit()
                                print(f"[批量创建频道] 频道创建失败: {result_msg}")
                        
                        # 任务完成后等待1-2秒
                        if not task_queue.empty():
                            wait_time = random.uniform(1, 2)
                            print(f"[批量创建频道] 等待 {wait_time:.1f} 秒后继续下一个...")
                            time.sleep(wait_time)
                    
                        task_queue.task_done()
                    except Exception as e:
                        print(f"[批量创建频道错误] {str(e)}")
                        if account_id:
                            add_channel_log(account_id, browser_env_id, 'failed', f'创建失败: {str(e)}')
                        task_queue.task_done()
                    finally:
                        # 关闭浏览器
                        if driver:
                            try:
                                driver.quit()
                            except:
                                pass
                        if browser_env_id:
                            try:
                                hubstudio_service.close_browser(browser_env_id)
                            except:
                                pass
        
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
            print(f"========== 批量创建频道已被用户停止 ==========\n")
        else:
            print(f"========== 批量创建频道完成 ==========\n")

