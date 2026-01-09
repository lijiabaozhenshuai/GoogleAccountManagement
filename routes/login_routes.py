# -*- coding: utf-8 -*-
"""
自动登录路由
"""
import threading
from flask import request, jsonify, current_app
from models import db, Account, LoginLog, BrowserEnv
from routes import login_bp
from services import login_service


@login_bp.route('/accounts/<int:id>/auto-login', methods=['POST'])
def auto_login_account(id):
    """自动登录账号"""
    account = Account.query.get_or_404(id)
    
    # 检查是否正在登录中
    if account.login_status == 'logging':
        return jsonify({'code': 1, 'message': '账号正在登录中，请稍候'})
    
    # 在后台线程中执行登录任务
    app = current_app._get_current_object()
    thread = threading.Thread(target=login_service.auto_login_task, args=(app, id))
    thread.daemon = True
    thread.start()
    
    return jsonify({'code': 0, 'message': '已开始自动登录，请刷新查看状态'})


@login_bp.route('/accounts/<int:id>/logs', methods=['GET'])
def get_account_logs(id):
    """获取账号的登录日志"""
    account = Account.query.get_or_404(id)
    logs = LoginLog.query.filter_by(account_id=id).order_by(LoginLog.created_at.desc()).all()
    return jsonify({
        'code': 0,
        'data': [log.to_dict() for log in logs],
        'account': account.account
    })


@login_bp.route('/accounts/<int:id>/reset-status', methods=['POST'])
def reset_account_status(id):
    """重置账号登录状态"""
    account = Account.query.get_or_404(id)
    
    # 如果有关联的浏览器环境，释放它
    if account.browser_env_id:
        browser_env = BrowserEnv.query.filter_by(container_code=account.browser_env_id).first()
        if browser_env:
            browser_env.status = False
            browser_env.account_id = None
    
    account.login_status = 'not_logged'
    account.browser_env_id = None
    db.session.commit()
    
    login_service.add_login_log(id, None, 'reset', 'info', '登录状态已重置')
    
    return jsonify({'code': 0, 'message': '状态已重置'})


@login_bp.route('/browser-envs/sync', methods=['POST'])
def sync_browser_envs():
    """同步HubStudio浏览器环境到本地"""
    try:
        synced_count, total = login_service.sync_browser_envs()
        return jsonify({
            'code': 0,
            'message': f'同步完成，新增 {synced_count} 个环境',
            'total': total
        })
    except Exception as e:
        return jsonify({'code': 1, 'message': f'同步失败: {str(e)}'})


@login_bp.route('/browser-envs', methods=['GET'])
def get_browser_envs():
    """获取本地浏览器环境列表"""
    envs = BrowserEnv.query.order_by(BrowserEnv.id.desc()).all()
    return jsonify({'code': 0, 'data': [env.to_dict() for env in envs]})


@login_bp.route('/browser-envs/available-count', methods=['GET'])
def get_available_browser_envs_count():
    """获取可用浏览器环境数量"""
    count = BrowserEnv.query.filter_by(status=False).count()
    return jsonify({'code': 0, 'count': count})


@login_bp.route('/test-hubstudio', methods=['POST'])
def test_hubstudio_connection():
    """测试 HubStudio API 连接"""
    from services import hubstudio_service
    
    try:
        # 测试 API 状态
        print("\n========== 测试 HubStudio 连接 ==========")
        api_ok = hubstudio_service.check_api_status()
        print(f"API 状态检查: {'✓ 成功' if api_ok else '✗ 失败'}")
        
        if not api_ok:
            return jsonify({
                'code': 1, 
                'message': 'HubStudio API 连接失败，请检查: 1) HubStudio 是否运行 2) API 配置是否正确'
            })
        
        # 获取浏览器列表
        result = hubstudio_service.get_browsers(page=1, page_size=10)
        browsers = result.get('browsers', [])
        total = result.get('total', 0)
        
        print(f"浏览器列表获取: ✓ 成功，共 {total} 个环境")
        
        if total > 0:
            print(f"前 {len(browsers)} 个环境:")
            for browser in browsers[:5]:
                print(f"  - {browser.get('containerCode')}: {browser.get('containerName')}")
        
        # 尝试启动第一个浏览器（仅测试 API，不实际连接）
        if browsers:
            test_container = browsers[0].get('containerCode')
            print(f"\n测试启动浏览器环境: {test_container}")
            driver = hubstudio_service.open_browser(test_container)
            
            if driver:
                print(f"✓ 浏览器启动成功！")
                # 关闭测试浏览器
                driver.quit()
                hubstudio_service.close_browser(test_container)
                print(f"✓ 浏览器已关闭")
                print("========================================\n")
                
                return jsonify({
                    'code': 0,
                    'message': f'HubStudio 连接测试成功！共 {total} 个浏览器环境',
                    'data': {
                        'api_status': 'ok',
                        'total_browsers': total,
                        'test_result': 'success'
                    }
                })
            else:
                print(f"✗ 浏览器启动失败")
                print("========================================\n")
                return jsonify({
                    'code': 1,
                    'message': '浏览器启动失败，请检查控制台日志查看详细错误'
                })
        else:
            print("⚠ 没有可用的浏览器环境")
            print("========================================\n")
            return jsonify({
                'code': 1,
                'message': 'HubStudio 连接正常，但没有可用的浏览器环境'
            })
            
    except Exception as e:
        print(f"✗ 测试过程出错: {str(e)}")
        print("========================================\n")
        import traceback
        traceback.print_exc()
        return jsonify({
            'code': 1,
            'message': f'测试失败: {str(e)}'
        })
