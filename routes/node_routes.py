# -*- coding: utf-8 -*-
"""
节点管理路由
"""
from flask import request, jsonify, send_file
from models import db, Node
from routes import node_bp
import pandas as pd
from io import BytesIO
from datetime import datetime


@node_bp.route('', methods=['GET'])
def get_nodes():
    """获取节点列表（支持分页和筛选）"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    ip = request.args.get('ip', '')
    status = request.args.get('status', '')
    
    # 限制每页最大数量
    page_size = min(page_size, 100)
    
    # 构建查询
    query = Node.query
    
    if ip:
        query = query.filter(Node.ip.like(f'%{ip}%'))
        
    if status != '':
        query = query.filter(Node.status == (status == 'true' or status == '1'))
        
    # 分页查询
    pagination = query.order_by(Node.id.desc()).paginate(
        page=page, per_page=page_size, error_out=False
    )
    
    return jsonify({
        'code': 0,
        'data': [n.to_dict() for n in pagination.items],
        'total': pagination.total,
        'page': page,
        'page_size': page_size,
        'total_pages': pagination.pages
    })


@node_bp.route('', methods=['POST'])
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


@node_bp.route('/<int:id>', methods=['PUT'])
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


@node_bp.route('/<int:id>', methods=['DELETE'])
def delete_node(id):
    """删除节点"""
    node = Node.query.get_or_404(id)
    db.session.delete(node)
    db.session.commit()
    return jsonify({'code': 0, 'message': '删除成功'})


@node_bp.route('/batch-delete', methods=['POST'])
def batch_delete_nodes():
    """批量删除节点"""
    ids = request.json.get('ids', [])
    Node.query.filter(Node.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'code': 0, 'message': f'成功删除 {len(ids)} 条记录'})


@node_bp.route('/batch-status', methods=['POST'])
def batch_update_nodes_status():
    """批量更新节点状态"""
    data = request.json
    ids = data.get('ids', [])
    status = data.get('status', False)
    Node.query.filter(Node.id.in_(ids)).update({'status': status}, synchronize_session=False)
    db.session.commit()
    return jsonify({'code': 0, 'message': f'成功更新 {len(ids)} 条记录'})


@node_bp.route('/export', methods=['GET'])
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


@node_bp.route('/import', methods=['POST'])
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


@node_bp.route('/template', methods=['GET'])
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


@node_bp.route('/available-count', methods=['GET'])
def get_available_nodes_count():
    """获取可用（未使用）节点数量"""
    count = Node.query.filter_by(status=False).count()
    return jsonify({'code': 0, 'count': count})


