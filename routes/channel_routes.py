# -*- coding: utf-8 -*-
"""
频道管理路由
"""
from flask import request, jsonify
from routes import channel_bp
from models import db, Account, LoginLog
from services import hubstudio_service
from services.channel_service import check_avatar_availability, create_youtube_channel, detect_monetization_requirement
from services.login_service import perform_login
import threading
import time


@channel_bp.route('/check-avatar-availability', methods=['GET'])
def check_avatar():
    """检查头像文件夹可用性"""
    try:
        is_available, count, error_msg = check_avatar_availability()
        
        if is_available:
            return jsonify({
                'code': 0,
                'message': f'头像文件夹可用，共有 {count} 张头像',
                'data': {'available': True, 'count': count}
            })
        else:
            return jsonify({
                'code': 1,
                'message': error_msg,
                'data': {'available': False, 'count': 0}
            }), 400
    except Exception as e:
        return jsonify({
            'code': 1,
            'message': f'检查失败: {str(e)}',
            'data': {'available': False, 'count': 0}
        }), 500


@channel_bp.route('/<int:account_id>/create-channel', methods=['POST'])
def create_channel(account_id):
    """为指定账号创建YouTube频道"""
    try:
        # 获取账号信息
        account = Account.query.get(account_id)
        if not account:
            return jsonify({'code': 1, 'message': '账号不存在'}), 404
        
        # 检查账号是否已登录
        if not account.login_status or account.login_status not in ['success', 'success_with_verification']:
            return jsonify({'code': 1, 'message': '账号未登录，请先完成登录'}), 400
        
        # 检查是否有浏览器环境
        if not account.browser_env_id:
            return jsonify({'code': 1, 'message': '账号未绑定浏览器环境'}), 400
        
        # 只有在频道未创建时才检查头像可用性
        if account.channel_status != 'created' or not account.channel_url:
            # 检查头像可用性
            is_available, count, error_msg = check_avatar_availability()
            if not is_available:
                return jsonify({'code': 1, 'message': error_msg}), 400
        
        # 启动后台任务创建频道
        def create_channel_task():
            from main import app
            with app.app_context():
                driver = None
                browser_env_id = None
                
                try:
                    # 在后台线程中重新查询账号信息（避免数据库会话问题）
                    acc = Account.query.get(account_id)
                    if not acc:
                        print(f"[创建频道错误] 账号不存在")
                        return
                    
                    browser_env_id = acc.browser_env_id
                    
                    # 添加日志：开始创建频道
                    log = LoginLog(
                        account_id=account_id,
                        browser_env_id=browser_env_id,
                        action='create_channel',
                        status='start',
                        message='开始创建YouTube频道'
                    )
                    db.session.add(log)
                    db.session.commit()
                    
                    # 打开浏览器
                    print(f"[创建频道] 正在打开浏览器环境: {browser_env_id}")
                    driver = hubstudio_service.open_browser(browser_env_id)
                    
                    if not driver:
                        error_msg = '无法打开浏览器'
                        print(f"[创建频道错误] {error_msg}")
                        log = LoginLog(
                            account_id=account_id,
                            browser_env_id=browser_env_id,
                            action='create_channel',
                            status='failed',
                            message=error_msg
                        )
                        db.session.add(log)
                        db.session.commit()
                        return
                    
                    print(f"[创建频道] 浏览器已打开")
                    
                    # 添加日志：浏览器已打开
                    log = LoginLog(
                        account_id=account_id,
                        browser_env_id=browser_env_id,
                        action='create_channel',
                        status='info',
                        message='浏览器已打开，检查登录状态'
                    )
                    db.session.add(log)
                    db.session.commit()
                    
                    # 检查是否需要登录
                    try:
                        current_url = driver.current_url
                        print(f"[创建频道] 当前URL: {current_url}")
                        
                        # 如果是空白页或不在Google域名，先进行登录
                        if current_url == "about:blank" or current_url == "data:," or "google.com" not in current_url:
                            print(f"[创建频道] 检测到未登录，开始自动登录...")
                            
                            # 添加日志：开始登录
                            log = LoginLog(
                                account_id=account_id,
                                browser_env_id=browser_env_id,
                                action='create_channel',
                                status='info',
                                message='检测到未登录，开始自动登录Google账号'
                            )
                            db.session.add(log)
                            db.session.commit()
                            
                            # 执行登录
                            login_status, login_message = perform_login(
                                driver, 
                                acc.account, 
                                acc.password, 
                                account_id=account_id, 
                                backup_email=acc.backup_email
                            )
                            
                            print(f"[创建频道] 登录结果 - 状态: {login_status}, 消息: {login_message}")
                            
                            if login_status not in ['success', 'success_with_verification']:
                                error_msg = f'自动登录失败: {login_message}'
                                print(f"[创建频道错误] {error_msg}")
                                
                                # 更新账号登录状态（根据登录结果设置）
                                if login_status == 'disabled':
                                    acc.login_status = 'disabled'
                                elif login_status == 'need_2fa':
                                    acc.login_status = 'need_2fa'
                                elif login_status == 'password_error':
                                    acc.login_status = 'password_error'
                                else:
                                    acc.login_status = 'failed'
                                db.session.commit()
                                
                                log = LoginLog(
                                    account_id=account_id,
                                    browser_env_id=browser_env_id,
                                    action='create_channel',
                                    status='failed',
                                    message=error_msg
                                )
                                db.session.add(log)
                                db.session.commit()
                                return
                            
                            # 更新账号登录状态
                            acc.login_status = login_status
                            acc.status = True
                            db.session.commit()
                            
                            # 添加日志：登录成功
                            log = LoginLog(
                                account_id=account_id,
                                browser_env_id=browser_env_id,
                                action='create_channel',
                                status='success',
                                message=f'自动登录成功，{login_message}'
                            )
                            db.session.add(log)
                            db.session.commit()
                            
                            # 等待登录完全完成
                            time.sleep(3)
                    except Exception as check_error:
                        print(f"[创建频道警告] 检查登录状态失败: {str(check_error)}")
                        # 继续尝试创建频道
                        pass
                    
                    # 检查频道是否已存在
                    acc_check = Account.query.get(account_id)
                    if acc_check and acc_check.channel_status == 'created' and acc_check.channel_url:
                        print(f"[创建频道] 检测到频道已存在，跳转到检测创收要求流程...")
                        
                        # 添加日志：检测到频道已存在
                        log = LoginLog(
                            account_id=account_id,
                            browser_env_id=browser_env_id,
                            action='create_channel',
                            status='info',
                            message='检测到频道已存在，开始检测创收要求'
                        )
                        db.session.add(log)
                        db.session.commit()
                        
                        # 直接调用检测创收要求函数
                        monetization_req = detect_monetization_requirement(
                            driver, 
                            acc_check.channel_url, 
                            account_id=account_id, 
                            browser_env_id=browser_env_id
                        )
                        
                        # 更新数据库
                        if monetization_req:
                            acc_check.monetization_requirement = monetization_req
                            db.session.commit()
                            
                            status = 'success'
                            message = f'创收要求检测完成：{monetization_req}'
                        else:
                            status = 'warning'
                            message = '创收要求检测失败'
                    else:
                        print(f"[创建频道] 开始创建YouTube频道...")
                        
                        # 添加日志：开始创建频道
                        log = LoginLog(
                            account_id=account_id,
                            browser_env_id=browser_env_id,
                            action='create_channel',
                            status='info',
                            message='开始创建YouTube频道'
                        )
                        db.session.add(log)
                        db.session.commit()
                        
                        # 执行创建频道操作
                        status, message = create_youtube_channel(driver, account_id=account_id, browser_env_id=browser_env_id)
                    
                    print(f"[创建频道] 创建结果 - 状态: {status}, 消息: {message}")
                    
                    # 添加日志：创建结果
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
                    error_msg = f'创建频道过程发生异常: {str(e)}'
                    print(f"[创建频道异常] {error_msg}")
                    import traceback
                    traceback.print_exc()
                    
                    # 添加异常日志
                    try:
                        log = LoginLog(
                            account_id=account_id,
                            browser_env_id=browser_env_id,
                            action='create_channel',
                            status='failed',
                            message=error_msg
                        )
                        db.session.add(log)
                        db.session.commit()
                    except:
                        pass
                
                finally:
                    # 关闭浏览器
                    if driver:
                        try:
                            driver.quit()
                        except:
                            pass
                        if browser_env_id:
                            hubstudio_service.close_browser(browser_env_id)
        
        # 在后台线程中执行
        thread = threading.Thread(target=create_channel_task)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'code': 0,
            'message': '频道创建任务已启动，请稍后查看结果'
        })
        
    except Exception as e:
        return jsonify({'code': 1, 'message': f'操作失败: {str(e)}'}), 500

