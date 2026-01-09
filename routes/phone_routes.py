# -*- coding: utf-8 -*-
"""
手机号管理路由
"""
from flask import request, jsonify, send_file
from models import db, Phone
from routes import phone_bp
import pandas as pd
from io import BytesIO
from datetime import datetime


@phone_bp.route('', methods=['GET'])
def get_phones():
    """获取手机号列表（支持分页）"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    
    # 限制每页最大数量
    page_size = min(page_size, 100)
    
    # 分页查询
    pagination = Phone.query.order_by(Phone.id.desc()).paginate(
        page=page, per_page=page_size, error_out=False
    )
    
    return jsonify({
        'code': 0,
        'data': [p.to_dict() for p in pagination.items],
        'total': pagination.total,
        'page': page,
        'page_size': page_size,
        'total_pages': pagination.pages
    })


@phone_bp.route('', methods=['POST'])
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


@phone_bp.route('/<int:id>', methods=['PUT'])
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


@phone_bp.route('/<int:id>', methods=['DELETE'])
def delete_phone(id):
    """删除手机号"""
    phone = Phone.query.get_or_404(id)
    db.session.delete(phone)
    db.session.commit()
    return jsonify({'code': 0, 'message': '删除成功'})


@phone_bp.route('/batch-delete', methods=['POST'])
def batch_delete_phones():
    """批量删除手机号"""
    ids = request.json.get('ids', [])
    Phone.query.filter(Phone.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'code': 0, 'message': f'成功删除 {len(ids)} 条记录'})


@phone_bp.route('/batch-status', methods=['POST'])
def batch_update_phones_status():
    """批量更新手机号状态"""
    data = request.json
    ids = data.get('ids', [])
    status = data.get('status', False)
    Phone.query.filter(Phone.id.in_(ids)).update({'status': status}, synchronize_session=False)
    db.session.commit()
    return jsonify({'code': 0, 'message': f'成功更新 {len(ids)} 条记录'})


@phone_bp.route('/export', methods=['GET'])
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


@phone_bp.route('/import', methods=['POST'])
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
                    if len(expire_val) == 10:
                        expire_time = datetime.strptime(expire_val, '%Y-%m-%d')
                    else:
                        expire_time = datetime.strptime(expire_val, '%Y-%m-%d %H:%M:%S')
                elif isinstance(expire_val, pd.Timestamp):
                    expire_time = expire_val.to_pydatetime()
                elif hasattr(expire_val, 'date'):
                    expire_time = datetime.combine(expire_val, datetime.min.time())
            except Exception as e:
                print(f"解析过期时间失败: {expire_val}, 错误: {e}")
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


@phone_bp.route('/template', methods=['GET'])
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

