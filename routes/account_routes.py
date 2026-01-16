# -*- coding: utf-8 -*-
"""
账号管理路由
"""
from flask import request, jsonify, send_file
from models import db, Account
from routes import account_bp
import pandas as pd
from io import BytesIO
from datetime import datetime


@account_bp.route('', methods=['GET'])
def get_accounts():
    """获取账号列表（支持分页和筛选）"""
    # 获取分页参数
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    
    # 获取筛选参数
    account_search = request.args.get('account', '').strip()
    phone_search = request.args.get('phone', '').strip()
    env_id_search = request.args.get('env_id', '').strip()
    login_status_filter = request.args.getlist('login_status')  # 多选
    channel_status_filter = request.args.getlist('channel_status')  # 多选
    monetization_filter = request.args.getlist('monetization')  # 多选
    
    # 构建查询
    query = Account.query
    
    # 账号搜索
    if account_search:
        query = query.filter(Account.account.like(f'%{account_search}%'))
    
    # 手机号搜索（需要处理 None 值）
    if phone_search:
        query = query.filter(
            db.and_(
                Account.phone_number.isnot(None),
                Account.phone_number.like(f'%{phone_search}%')
            )
        )
    
    # 环境ID搜索（需要处理 None 值）
    if env_id_search:
        query = query.filter(
            db.and_(
                Account.browser_env_id.isnot(None),
                Account.browser_env_id.like(f'%{env_id_search}%')
            )
        )
    
    # 登录状态筛选（多选）
    if login_status_filter:
        # 处理 not_logged 包括 None 的情况
        if 'not_logged' in login_status_filter:
            # 将 not_logged 和 None 都包含进来
            other_statuses = [s for s in login_status_filter if s != 'not_logged']
            if other_statuses:
                query = query.filter(
                    db.or_(
                        Account.login_status.in_(other_statuses),
                        Account.login_status == 'not_logged',
                        Account.login_status.is_(None)
                    )
                )
            else:
                query = query.filter(
                    db.or_(
                        Account.login_status == 'not_logged',
                        Account.login_status.is_(None)
                    )
                )
        else:
            query = query.filter(Account.login_status.in_(login_status_filter))
    
    # 频道状态筛选（多选）
    if channel_status_filter:
        # 处理 not_created 包括 None 的情况
        if 'not_created' in channel_status_filter:
            # 将 not_created 和 None 都包含进来
            other_statuses = [s for s in channel_status_filter if s != 'not_created']
            if other_statuses:
                query = query.filter(
                    db.or_(
                        Account.channel_status.in_(other_statuses),
                        Account.channel_status == 'not_created',
                        Account.channel_status.is_(None)
                    )
                )
            else:
                query = query.filter(
                    db.or_(
                        Account.channel_status == 'not_created',
                        Account.channel_status.is_(None)
                    )
                )
        else:
            query = query.filter(Account.channel_status.in_(channel_status_filter))
    
    # 创收要求筛选（多选）
    if monetization_filter:
        query = query.filter(Account.monetization_requirement.in_(monetization_filter))
    
    # 查询总数
    total = query.count()
    
    # 分页查询
    pagination = query.order_by(Account.id.desc()).paginate(
        page=page, per_page=page_size, error_out=False
    )
    
    return jsonify({
        'code': 0, 
        'data': [a.to_dict() for a in pagination.items],
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': pagination.pages
    })


@account_bp.route('', methods=['POST'])
def add_account():
    """添加账号"""
    data = request.json
    account = Account(
        account=data.get('account', ''),
        password=data.get('password', ''),
        backup_email=data.get('backup_email', ''),
        status=data.get('status', False)
    )
    db.session.add(account)
    db.session.commit()
    return jsonify({'code': 0, 'message': '添加成功', 'data': account.to_dict()})


@account_bp.route('/<int:id>', methods=['GET'])
def get_account(id):
    """获取单个账号"""
    account = Account.query.get_or_404(id)
    return jsonify({'code': 0, 'data': account.to_dict()})


@account_bp.route('/<int:id>', methods=['PUT'])
def update_account(id):
    """更新账号"""
    account = Account.query.get_or_404(id)
    data = request.json
    account.account = data.get('account', account.account)
    account.password = data.get('password', account.password)
    account.backup_email = data.get('backup_email', account.backup_email)
    account.status = data.get('status', account.status)
    # 支持修改环境ID
    if 'browser_env_id' in data:
        account.browser_env_id = data.get('browser_env_id') or None
    # 支持修改登录状态
    if 'login_status' in data:
        account.login_status = data.get('login_status') or None
    # 支持修改频道状态
    if 'channel_status' in data:
        account.channel_status = data.get('channel_status') or None
    db.session.commit()
    return jsonify({'code': 0, 'message': '更新成功', 'data': account.to_dict()})


@account_bp.route('/<int:id>', methods=['DELETE'])
def delete_account(id):
    """删除账号"""
    account = Account.query.get_or_404(id)
    db.session.delete(account)
    db.session.commit()
    return jsonify({'code': 0, 'message': '删除成功'})


@account_bp.route('/batch-delete', methods=['POST'])
def batch_delete_accounts():
    """批量删除账号"""
    ids = request.json.get('ids', [])
    Account.query.filter(Account.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'code': 0, 'message': f'成功删除 {len(ids)} 条记录'})


@account_bp.route('/batch-status', methods=['POST'])
def batch_update_accounts_status():
    """批量更新账号状态"""
    data = request.json
    ids = data.get('ids', [])
    status = data.get('status', False)
    Account.query.filter(Account.id.in_(ids)).update({'status': status}, synchronize_session=False)
    db.session.commit()
    return jsonify({'code': 0, 'message': f'成功更新 {len(ids)} 条记录'})


@account_bp.route('/export', methods=['GET'])
def export_accounts():
    """导出账号"""
    accounts = Account.query.all()
    data = [{
        '账号': a.account,
        '密码': a.password,
        '辅助邮箱': a.backup_email,
        '状态': '已使用' if a.status else '未使用'
    } for a in accounts]
    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=f'accounts_{datetime.now().strftime("%Y%m%d%H%M%S")}.xlsx')


@account_bp.route('/import', methods=['POST'])
def import_accounts():
    """导入账号"""
    file = request.files.get('file')
    if not file:
        return jsonify({'code': 1, 'message': '请选择文件'})
    
    df = pd.read_excel(file)
    count = 0
    for _, row in df.iterrows():
        account = Account(
            account=str(row.get('账号', '')),
            password=str(row.get('密码', '')),
            backup_email=str(row.get('辅助邮箱', '')),
            status=row.get('状态', '') == '已使用'
        )
        db.session.add(account)
        count += 1
    db.session.commit()
    return jsonify({'code': 0, 'message': f'成功导入 {count} 条记录'})


@account_bp.route('/template', methods=['GET'])
def download_accounts_template():
    """下载账号导入模板"""
    data = [{
        '账号': 'example@gmail.com',
        '密码': 'password123',
        '辅助邮箱': 'backup@example.com',
        '状态': '未使用'
    }]
    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='账号导入模板.xlsx')


@account_bp.route('/<int:id>/reset-login-status', methods=['POST'])
def reset_login_status(id):
    """重置账号登录状态"""
    account = Account.query.get_or_404(id)
    
    # 重置登录状态为空
    account.login_status = None
    db.session.commit()
    
    return jsonify({'code': 0, 'message': '登录状态已重置', 'data': account.to_dict()})


@account_bp.route('/batch-reset-login-status', methods=['POST'])
def batch_reset_login_status():
    """批量重置账号登录状态"""
    ids = request.json.get('ids', [])
    Account.query.filter(Account.id.in_(ids)).update({'login_status': None}, synchronize_session=False)
    db.session.commit()
    return jsonify({'code': 0, 'message': f'成功重置 {len(ids)} 个账号的登录状态'})


@account_bp.route('/batch-login', methods=['POST'])
def batch_login():
    """批量登录账号"""
    import threading
    from flask import current_app
    from services import login_service
    
    ids = request.json.get('ids', [])
    if not ids:
        return jsonify({'code': 1, 'message': '请选择要登录的账号'})
    
    # 检查是否有账号正在登录中
    logging_accounts = Account.query.filter(
        Account.id.in_(ids),
        Account.login_status == 'logging'
    ).count()
    
    if logging_accounts > 0:
        return jsonify({'code': 1, 'message': f'有 {logging_accounts} 个账号正在登录中，请等待完成'})
    
    # 在后台线程中执行批量登录任务
    app = current_app._get_current_object()
    thread = threading.Thread(target=login_service.batch_login_task, args=(app, ids))
    thread.daemon = True
    thread.start()
    
    return jsonify({'code': 0, 'message': f'已开始批量登录 {len(ids)} 个账号'})


@account_bp.route('/batch-create-channel', methods=['POST'])
def batch_create_channel():
    """批量创建频道"""
    import threading
    from flask import current_app
    from services import channel_service
    
    ids = request.json.get('ids', [])
    if not ids:
        return jsonify({'code': 1, 'message': '请选择要创建频道的账号'})
    
    # 检查账号是否已登录
    not_logged_accounts = Account.query.filter(
        Account.id.in_(ids),
        ~Account.login_status.in_(['success', 'success_with_verification'])
    ).count()
    
    if not_logged_accounts > 0:
        return jsonify({'code': 1, 'message': f'有 {not_logged_accounts} 个账号未登录，无法创建频道'})
    
    # 在后台线程中执行批量创建频道任务
    app = current_app._get_current_object()
    thread = threading.Thread(target=channel_service.batch_create_channel_task, args=(app, ids))
    thread.daemon = True
    thread.start()
    
    return jsonify({'code': 0, 'message': f'已开始批量创建频道 {len(ids)} 个账号'})


@account_bp.route('/stop-all-tasks', methods=['POST'])
def stop_all_tasks():
    """停止所有批量任务"""
    from services import login_service, channel_service
    
    # 设置停止标志
    login_service.stop_batch_tasks = True
    channel_service.stop_batch_tasks = True
    
    return jsonify({'code': 0, 'message': '已发送停止信号，任务将在当前操作完成后停止'})
