# -*- coding: utf-8 -*-
"""
谷歌账号管理系统 - 主应用
"""
from flask import Flask, render_template, request, jsonify, send_file
from models import db, Account, Phone, Node
from config import MENU_CONFIG, DATABASE_URI, APP_CONFIG
import pandas as pd
from io import BytesIO
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = APP_CONFIG['SECRET_KEY']

db.init_app(app)


def get_sorted_menu():
    """获取排序后的菜单配置"""
    menu = sorted(MENU_CONFIG, key=lambda x: x.get('order', 0))
    for item in menu:
        if item.get('children'):
            item['children'] = sorted(item['children'], key=lambda x: x.get('order', 0))
    return menu


@app.context_processor
def inject_menu():
    """注入菜单配置到所有模板"""
    return {'menu_config': get_sorted_menu()}


# ==================== 页面路由 ====================

@app.route('/')
def index():
    """首页 - 重定向到账号管理"""
    return render_template('accounts.html', page_title='账号管理', current_url='/accounts')


@app.route('/accounts')
def accounts_page():
    """账号管理页面"""
    return render_template('accounts.html', page_title='账号管理', current_url='/accounts')


@app.route('/phones')
def phones_page():
    """手机号管理页面"""
    return render_template('phones.html', page_title='手机号管理', current_url='/phones')


@app.route('/nodes')
def nodes_page():
    """节点管理页面"""
    return render_template('nodes.html', page_title='节点管理', current_url='/nodes')


# ==================== 账号管理 API ====================

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """获取账号列表"""
    accounts = Account.query.order_by(Account.id.desc()).all()
    return jsonify({'code': 0, 'data': [a.to_dict() for a in accounts]})


@app.route('/api/accounts', methods=['POST'])
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


@app.route('/api/accounts/<int:id>', methods=['PUT'])
def update_account(id):
    """更新账号"""
    account = Account.query.get_or_404(id)
    data = request.json
    account.account = data.get('account', account.account)
    account.password = data.get('password', account.password)
    account.backup_email = data.get('backup_email', account.backup_email)
    account.status = data.get('status', account.status)
    db.session.commit()
    return jsonify({'code': 0, 'message': '更新成功', 'data': account.to_dict()})


@app.route('/api/accounts/<int:id>', methods=['DELETE'])
def delete_account(id):
    """删除账号"""
    account = Account.query.get_or_404(id)
    db.session.delete(account)
    db.session.commit()
    return jsonify({'code': 0, 'message': '删除成功'})


@app.route('/api/accounts/batch-delete', methods=['POST'])
def batch_delete_accounts():
    """批量删除账号"""
    ids = request.json.get('ids', [])
    Account.query.filter(Account.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'code': 0, 'message': f'成功删除 {len(ids)} 条记录'})


@app.route('/api/accounts/batch-status', methods=['POST'])
def batch_update_accounts_status():
    """批量更新账号状态"""
    data = request.json
    ids = data.get('ids', [])
    status = data.get('status', False)
    Account.query.filter(Account.id.in_(ids)).update({'status': status}, synchronize_session=False)
    db.session.commit()
    return jsonify({'code': 0, 'message': f'成功更新 {len(ids)} 条记录'})


@app.route('/api/accounts/export', methods=['GET'])
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


@app.route('/api/accounts/import', methods=['POST'])
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


@app.route('/api/accounts/template', methods=['GET'])
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


# ==================== 手机号管理 API ====================

@app.route('/api/phones', methods=['GET'])
def get_phones():
    """获取手机号列表"""
    phones = Phone.query.order_by(Phone.id.desc()).all()
    return jsonify({'code': 0, 'data': [p.to_dict() for p in phones]})


@app.route('/api/phones', methods=['POST'])
def add_phone():
    """添加手机号"""
    data = request.json
    expire_time = None
    if data.get('expire_time'):
        try:
            expire_time = datetime.strptime(data.get('expire_time'), '%Y-%m-%d %H:%M:%S')
        except:
            pass
    phone = Phone(
        phone_number=data.get('phone_number', ''),
        sms_url=data.get('sms_url', ''),
        expire_time=expire_time,
        status=data.get('status', False)
    )
    db.session.add(phone)
    db.session.commit()
    return jsonify({'code': 0, 'message': '添加成功', 'data': phone.to_dict()})


@app.route('/api/phones/<int:id>', methods=['PUT'])
def update_phone(id):
    """更新手机号"""
    phone = Phone.query.get_or_404(id)
    data = request.json
    phone.phone_number = data.get('phone_number', phone.phone_number)
    phone.sms_url = data.get('sms_url', phone.sms_url)
    phone.status = data.get('status', phone.status)
    if 'expire_time' in data:
        if data.get('expire_time'):
            try:
                phone.expire_time = datetime.strptime(data.get('expire_time'), '%Y-%m-%d %H:%M:%S')
            except:
                pass
        else:
            phone.expire_time = None
    db.session.commit()
    return jsonify({'code': 0, 'message': '更新成功', 'data': phone.to_dict()})


@app.route('/api/phones/<int:id>', methods=['DELETE'])
def delete_phone(id):
    """删除手机号"""
    phone = Phone.query.get_or_404(id)
    db.session.delete(phone)
    db.session.commit()
    return jsonify({'code': 0, 'message': '删除成功'})


@app.route('/api/phones/batch-delete', methods=['POST'])
def batch_delete_phones():
    """批量删除手机号"""
    ids = request.json.get('ids', [])
    Phone.query.filter(Phone.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'code': 0, 'message': f'成功删除 {len(ids)} 条记录'})


@app.route('/api/phones/batch-status', methods=['POST'])
def batch_update_phones_status():
    """批量更新手机号状态"""
    data = request.json
    ids = data.get('ids', [])
    status = data.get('status', False)
    Phone.query.filter(Phone.id.in_(ids)).update({'status': status}, synchronize_session=False)
    db.session.commit()
    return jsonify({'code': 0, 'message': f'成功更新 {len(ids)} 条记录'})


@app.route('/api/phones/export', methods=['GET'])
def export_phones():
    """导出手机号"""
    phones = Phone.query.all()
    data = [{
        '手机号': p.phone_number,
        '接码URL': p.sms_url,
        '过期时间': p.expire_time.strftime('%Y-%m-%d') if p.expire_time else '',
        '状态': '已使用' if p.status else '未使用'
    } for p in phones]
    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=f'phones_{datetime.now().strftime("%Y%m%d%H%M%S")}.xlsx')


@app.route('/api/phones/import', methods=['POST'])
def import_phones():
    """导入手机号"""
    file = request.files.get('file')
    if not file:
        return jsonify({'code': 1, 'message': '请选择文件'})
    
    df = pd.read_excel(file)
    count = 0
    for _, row in df.iterrows():
        expire_time = None
        if '过期时间' in row and pd.notna(row.get('过期时间')):
            try:
                expire_val = row.get('过期时间')
                if isinstance(expire_val, str):
                    expire_val = expire_val.strip()
                    # 尝试解析日期格式
                    if len(expire_val) == 10:  # 格式: 2026-12-31
                        expire_time = datetime.strptime(expire_val, '%Y-%m-%d')
                    else:  # 格式: 2026-12-31 23:59:59
                        expire_time = datetime.strptime(expire_val, '%Y-%m-%d %H:%M:%S')
                elif isinstance(expire_val, pd.Timestamp):
                    expire_time = expire_val.to_pydatetime()
                elif hasattr(expire_val, 'date'):  # datetime.date 或 datetime.datetime 对象
                    expire_time = datetime.combine(expire_val, datetime.min.time())
            except Exception as e:
                print(f"解析过期时间失败: {expire_val}, 错误: {e}")
                pass
        phone = Phone(
            phone_number=str(row.get('手机号', '')),
            sms_url=str(row.get('接码URL', '')),
            expire_time=expire_time,
            status=row.get('状态', '') == '已使用'
        )
        db.session.add(phone)
        count += 1
    db.session.commit()
    return jsonify({'code': 0, 'message': f'成功导入 {count} 条记录'})


@app.route('/api/phones/template', methods=['GET'])
def download_phones_template():
    """下载手机号导入模板"""
    data = [{
        '手机号': '13800138000',
        '接码URL': 'https://sms.example.com/receive',
        '过期时间': '2026-12-31',
        '状态': '未使用'
    }]
    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='手机号导入模板.xlsx')


# ==================== 节点管理 API ====================

@app.route('/api/nodes', methods=['GET'])
def get_nodes():
    """获取节点列表"""
    nodes = Node.query.order_by(Node.id.desc()).all()
    return jsonify({'code': 0, 'data': [n.to_dict() for n in nodes]})


@app.route('/api/nodes', methods=['POST'])
def add_node():
    """添加节点"""
    data = request.json
    node = Node(
        ip=data.get('ip', ''),
        port=data.get('port', 0),
        username=data.get('username', ''),
        password=data.get('password', ''),
        status=data.get('status', False)
    )
    db.session.add(node)
    db.session.commit()
    return jsonify({'code': 0, 'message': '添加成功', 'data': node.to_dict()})


@app.route('/api/nodes/<int:id>', methods=['PUT'])
def update_node(id):
    """更新节点"""
    node = Node.query.get_or_404(id)
    data = request.json
    node.ip = data.get('ip', node.ip)
    node.port = data.get('port', node.port)
    node.username = data.get('username', node.username)
    node.password = data.get('password', node.password)
    node.status = data.get('status', node.status)
    db.session.commit()
    return jsonify({'code': 0, 'message': '更新成功', 'data': node.to_dict()})


@app.route('/api/nodes/<int:id>', methods=['DELETE'])
def delete_node(id):
    """删除节点"""
    node = Node.query.get_or_404(id)
    db.session.delete(node)
    db.session.commit()
    return jsonify({'code': 0, 'message': '删除成功'})


@app.route('/api/nodes/batch-delete', methods=['POST'])
def batch_delete_nodes():
    """批量删除节点"""
    ids = request.json.get('ids', [])
    Node.query.filter(Node.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'code': 0, 'message': f'成功删除 {len(ids)} 条记录'})


@app.route('/api/nodes/batch-status', methods=['POST'])
def batch_update_nodes_status():
    """批量更新节点状态"""
    data = request.json
    ids = data.get('ids', [])
    status = data.get('status', False)
    Node.query.filter(Node.id.in_(ids)).update({'status': status}, synchronize_session=False)
    db.session.commit()
    return jsonify({'code': 0, 'message': f'成功更新 {len(ids)} 条记录'})


@app.route('/api/nodes/export', methods=['GET'])
def export_nodes():
    """导出节点"""
    nodes = Node.query.all()
    data = [{
        '节点IP': n.ip,
        '端口': n.port,
        '用户名': n.username,
        '密码': n.password,
        '状态': '已使用' if n.status else '未使用'
    } for n in nodes]
    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=f'nodes_{datetime.now().strftime("%Y%m%d%H%M%S")}.xlsx')


@app.route('/api/nodes/import', methods=['POST'])
def import_nodes():
    """导入节点"""
    file = request.files.get('file')
    if not file:
        return jsonify({'code': 1, 'message': '请选择文件'})
    
    df = pd.read_excel(file)
    count = 0
    for _, row in df.iterrows():
        node = Node(
            ip=str(row.get('节点IP', '')),
            port=int(row.get('端口', 0)),
            username=str(row.get('用户名', '')),
            password=str(row.get('密码', '')),
            status=row.get('状态', '') == '已使用'
        )
        db.session.add(node)
        count += 1
    db.session.commit()
    return jsonify({'code': 0, 'message': f'成功导入 {count} 条记录'})


@app.route('/api/nodes/template', methods=['GET'])
def download_nodes_template():
    """下载节点导入模板"""
    data = [{
        '节点IP': '192.168.1.1',
        '端口': 8080,
        '用户名': 'admin',
        '密码': 'password',
        '状态': '未使用'
    }]
    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='节点导入模板.xlsx')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host=APP_CONFIG['HOST'], port=APP_CONFIG['PORT'], debug=APP_CONFIG['DEBUG'])
