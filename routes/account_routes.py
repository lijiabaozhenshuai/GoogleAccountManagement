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
    """获取账号列表"""
    accounts = Account.query.order_by(Account.id.desc()).all()
    return jsonify({'code': 0, 'data': [a.to_dict() for a in accounts]})


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

