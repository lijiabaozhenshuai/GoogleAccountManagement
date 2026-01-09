# -*- coding: utf-8 -*-
"""
浏览器管理路由
"""
import json
import random
import time
from flask import request, jsonify, Response
from models import db, Node
from routes import browser_bp
from services import hubstudio_service
from datetime import datetime


@browser_bp.route('/hubstudio/status', methods=['GET'])
def check_hubstudio_status():
    """检查HubStudio API连接状态"""
    connected = hubstudio_service.check_api_status()
    return jsonify({'code': 0, 'data': {'connected': connected}})


@browser_bp.route('/hubstudio/groups', methods=['GET'])
def get_hubstudio_groups():
    """获取HubStudio分组列表"""
    groups = hubstudio_service.get_groups()
    return jsonify({'code': 0, 'data': groups})


@browser_bp.route('/hubstudio/browsers', methods=['GET'])
def get_hubstudio_browsers():
    """获取HubStudio浏览器窗口列表"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    search = request.args.get('search', '', type=str)
    group_code = request.args.get('group_code', '', type=str)
    
    result = hubstudio_service.get_browsers(page, page_size, search, group_code)
    
    return jsonify({
        'code': 0,
        'data': result['browsers'],
        'total': result['total'],
        'page': page,
        'page_size': page_size
    })


@browser_bp.route('/hubstudio/batch-create', methods=['POST'])
def batch_create_browser():
    """批量创建HubStudio浏览器窗口"""
    from flask import current_app
    app = current_app._get_current_object()
    
    data = request.json
    count = data.get('count', 1)
    group_code = data.get('group_code', '')
    core_version = data.get('core_version', 'random')
    
    # 可选内核版本
    available_cores = [112, 113, 117, 122, 124, 126, 128, 130, 131]
    
    def generate():
        with app.app_context():
            nodes = Node.query.filter_by(status=False).limit(count).all()
            if len(nodes) < count:
                yield f"data: {json.dumps({'type': 'log', 'level': 'error', 'message': f'可用节点不足，需要{count}个，仅有{len(nodes)}个'})}\n\n"
                return
            
            # 获取分组名称
            group_name = ''
            if group_code:
                groups = hubstudio_service.get_groups()
                group_name = next((g['tagName'] for g in groups if g['tagCode'] == group_code), '')
            
            # 生成环境名称前缀
            env_prefix = datetime.now().strftime("%m%d%H%M")
            
            yield f"data: {json.dumps({'type': 'log', 'level': 'info', 'message': f'开始创建，环境前缀: {env_prefix}'})}\n\n"
            
            for idx, node in enumerate(nodes, 1):
                try:
                    # 确定内核版本
                    if core_version == 'random':
                        current_core = random.choice(available_cores)
                    else:
                        current_core = int(core_version)
                    
                    # 构建环境名称
                    env_name = f"{env_prefix}_{idx}"
                    proxy_info = f"{node.ip}:{node.port}"
                    
                    yield f"data: {json.dumps({'type': 'log', 'level': 'info', 'message': f'正在创建环境 #{idx}: {env_name} (内核: {current_core})'})}\n\n"
                    
                    # 创建环境
                    success, result = hubstudio_service.create_environment(
                        env_name, group_name, node.ip, node.port, 
                        node.username, node.password, current_core
                    )
                    
                    if success:
                        # 标记节点为已使用
                        node.status = True
                        db.session.commit()
                        
                        yield f"data: {json.dumps({'type': 'log', 'level': 'success', 'message': f'环境 #{idx} 创建成功，ID: {result}'})}\n\n"
                        yield f"data: {json.dumps({'type': 'progress', 'index': idx, 'success': True, 'env_name': env_name, 'container_code': result, 'proxy': proxy_info})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'log', 'level': 'error', 'message': f'环境 #{idx} 创建失败: {result}'})}\n\n"
                        yield f"data: {json.dumps({'type': 'progress', 'index': idx, 'success': False, 'env_name': env_name, 'container_code': '', 'proxy': proxy_info, 'error': result})}\n\n"
                    
                    # 添加延时避免频率限制
                    time.sleep(random.uniform(1, 2))
                    
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'log', 'level': 'error', 'message': f'环境 #{idx} 创建异常: {str(e)}'})}\n\n"
                    yield f"data: {json.dumps({'type': 'progress', 'index': idx, 'success': False, 'env_name': '', 'container_code': '', 'proxy': f'{node.ip}:{node.port}', 'error': str(e)})}\n\n"
            
            yield f"data: {json.dumps({'type': 'log', 'level': 'info', 'message': '批量创建任务完成'})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

