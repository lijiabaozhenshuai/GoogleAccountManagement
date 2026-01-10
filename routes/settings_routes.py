# -*- coding: utf-8 -*-
"""
设置管理路由
"""
from flask import request, jsonify
from routes import settings_bp
import re


@settings_bp.route('/get-config', methods=['GET'])
def get_config():
    """获取当前配置"""
    try:
        # 读取config.py文件
        with open('config.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取配置信息
        config_data = {
            'mysql': extract_mysql_config(content),
            'hubstudio': extract_hubstudio_config(content),
            'channel_avatar_path': extract_channel_avatar_path(content)
        }
        
        return jsonify({'success': True, 'data': config_data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@settings_bp.route('/update-config', methods=['POST'])
def update_config():
    """更新配置"""
    try:
        data = request.json
        config_type = data.get('type')
        config_data = data.get('data')
        
        # 读取当前配置文件
        with open('config.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 根据类型更新配置
        if config_type == 'mysql':
            content = update_mysql_config(content, config_data)
        elif config_type == 'hubstudio':
            content = update_hubstudio_config(content, config_data)
        elif config_type == 'channel_avatar':
            content = update_channel_avatar_path(content, config_data)
        else:
            return jsonify({'success': False, 'message': '未知的配置类型'}), 400
        
        # 写回配置文件
        with open('config.py', 'w', encoding='utf-8') as f:
            f.write(content)
        
        return jsonify({'success': True, 'message': '配置更新成功，请重启应用以生效'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'}), 500


def extract_mysql_config(content):
    """从配置文件内容中提取MySQL配置"""
    mysql_config = {}
    
    # 提取host
    match = re.search(r'"host":\s*"([^"]*)"', content)
    if match:
        mysql_config['host'] = match.group(1)
    
    # 提取port
    match = re.search(r'"port":\s*(\d+)', content)
    if match:
        mysql_config['port'] = int(match.group(1))
    
    # 提取user
    match = re.search(r'"user":\s*"([^"]*)"', content)
    if match:
        mysql_config['user'] = match.group(1)
    
    # 提取password
    match = re.search(r'"password":\s*"([^"]*)"', content)
    if match:
        mysql_config['password'] = match.group(1)
    
    # 提取database
    match = re.search(r'"database":\s*"([^"]*)"', content)
    if match:
        mysql_config['database'] = match.group(1)
    
    return mysql_config


def extract_hubstudio_config(content):
    """从配置文件内容中提取Hubstudio配置"""
    hubstudio_config = {}
    
    # 提取base_url
    match = re.search(r'HUBSTUDIO_CONFIG\s*=\s*{[^}]*"base_url":\s*"([^"]*)"', content, re.DOTALL)
    if match:
        hubstudio_config['base_url'] = match.group(1)
    
    # 提取app_id
    match = re.search(r'HUBSTUDIO_CONFIG\s*=\s*{[^}]*"app_id":\s*"([^"]*)"', content, re.DOTALL)
    if match:
        hubstudio_config['app_id'] = match.group(1)
    
    # 提取app_secret
    match = re.search(r'HUBSTUDIO_CONFIG\s*=\s*{[^}]*"app_secret":\s*"([^"]*)"', content, re.DOTALL)
    if match:
        hubstudio_config['app_secret'] = match.group(1)
    
    return hubstudio_config


def extract_channel_avatar_path(content):
    """从配置文件内容中提取频道头像路径配置"""
    match = re.search(r'CHANNEL_AVATAR_PATH\s*=\s*"([^"]*)"', content)
    if match:
        return match.group(1)
    return ""


def update_mysql_config(content, config_data):
    """更新MySQL配置"""
    # 更新host
    if 'host' in config_data:
        content = re.sub(
            r'("host":\s*)"[^"]*"',
            r'\1"' + config_data['host'] + '"',
            content
        )
    
    # 更新port
    if 'port' in config_data:
        content = re.sub(
            r'("port":\s*)\d+',
            r'\1' + str(config_data['port']),
            content
        )
    
    # 更新user
    if 'user' in config_data:
        content = re.sub(
            r'("user":\s*)"[^"]*"',
            r'\1"' + config_data['user'] + '"',
            content
        )
    
    # 更新password
    if 'password' in config_data:
        content = re.sub(
            r'("password":\s*)"[^"]*"',
            r'\1"' + config_data['password'] + '"',
            content
        )
    
    # 更新database
    if 'database' in config_data:
        content = re.sub(
            r'("database":\s*)"[^"]*"',
            r'\1"' + config_data['database'] + '"',
            content
        )
    
    return content


def update_hubstudio_config(content, config_data):
    """更新Hubstudio配置"""
    # 更新base_url
    if 'base_url' in config_data:
        content = re.sub(
            r'(HUBSTUDIO_CONFIG\s*=\s*{[^}]*"base_url":\s*)"[^"]*"',
            r'\1"' + config_data['base_url'] + '"',
            content,
            flags=re.DOTALL
        )
    
    # 更新app_id
    if 'app_id' in config_data:
        content = re.sub(
            r'(HUBSTUDIO_CONFIG\s*=\s*{[^}]*"app_id":\s*)"[^"]*"',
            r'\1"' + config_data['app_id'] + '"',
            content,
            flags=re.DOTALL
        )
    
    # 更新app_secret
    if 'app_secret' in config_data:
        content = re.sub(
            r'(HUBSTUDIO_CONFIG\s*=\s*{[^}]*"app_secret":\s*)"[^"]*"',
            r'\1"' + config_data['app_secret'] + '"',
            content,
            flags=re.DOTALL
        )
    
    return content


def update_channel_avatar_path(content, config_data):
    """更新频道头像路径配置"""
    path = config_data.get('path', '')
    
    # 检查是否已存在CHANNEL_AVATAR_PATH配置
    if 'CHANNEL_AVATAR_PATH' in content:
        # 更新现有配置
        content = re.sub(
            r'CHANNEL_AVATAR_PATH\s*=\s*"[^"]*"',
            f'CHANNEL_AVATAR_PATH = "{path}"',
            content
        )
    else:
        # 添加新配置（在CAPTCHA_CONFIG之后）
        captcha_end = content.rfind('}', 0, content.rfind('CAPTCHA_CONFIG'))
        if captcha_end != -1:
            # 找到CAPTCHA_CONFIG结束的位置
            insert_pos = content.find('\n', captcha_end) + 1
            new_config = f'\n# 频道头像路径配置\nCHANNEL_AVATAR_PATH = "{path}"\n'
            content = content[:insert_pos] + new_config + content[insert_pos:]
    
    return content
