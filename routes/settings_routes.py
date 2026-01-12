# -*- coding: utf-8 -*-
"""
设置管理路由
"""
from flask import request, jsonify
from routes import settings_bp
import json
import os
from threading import Lock

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
# 线程锁，确保并发写入安全
config_lock = Lock()


@settings_bp.route('/get-config', methods=['GET'])
def get_config():
    """获取当前配置"""
    try:
        # 如果配置文件不存在，创建默认配置
        if not os.path.exists(CONFIG_FILE):
            create_default_config()
        
        # 读取 JSON 配置文件
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # 转换为前端需要的格式
        response_data = {
            'mysql': config_data.get('mysql', {}),
            'hubstudio': config_data.get('hubstudio', {}),
            'channel_avatar_path': config_data.get('channel_avatar_path', '')
        }
        
        return jsonify({'success': True, 'data': response_data})
    except json.JSONDecodeError as e:
        return jsonify({'success': False, 'message': f'配置文件格式错误: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@settings_bp.route('/update-config', methods=['POST'])
def update_config():
    """更新配置"""
    try:
        data = request.json
        config_type = data.get('type')
        config_data = data.get('data')
        
        if not config_type or not config_data:
            return jsonify({'success': False, 'message': '参数不完整'}), 400
        
        # 验证配置数据
        if config_type == 'mysql':
            valid, error_msg = validate_mysql_config(config_data)
            if not valid:
                return jsonify({'success': False, 'message': f'配置验证失败: {error_msg}'}), 400
                
        elif config_type == 'hubstudio':
            valid, error_msg = validate_hubstudio_config(config_data)
            if not valid:
                return jsonify({'success': False, 'message': f'配置验证失败: {error_msg}'}), 400
        
        # 使用线程锁确保并发安全
        with config_lock:
            # 如果配置文件不存在，创建默认配置
            if not os.path.exists(CONFIG_FILE):
                create_default_config()
            
            # 读取当前配置
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 根据类型更新配置
            if config_type == 'mysql':
                if 'mysql' not in config:
                    config['mysql'] = {}
                config['mysql'].update(config_data)
                
            elif config_type == 'hubstudio':
                if 'hubstudio' not in config:
                    config['hubstudio'] = {}
                config['hubstudio'].update(config_data)
                
            elif config_type == 'channel_avatar':
                path = config_data.get('path', '')
                # 验证路径是否存在
                if path and not os.path.exists(path):
                    return jsonify({'success': False, 'message': f'路径不存在: {path}'}), 400
                config['channel_avatar_path'] = path
                
            else:
                return jsonify({'success': False, 'message': '未知的配置类型'}), 400
            
            # 写回配置文件（带备份）
            backup_and_save_config(config)
        
        return jsonify({'success': True, 'message': '配置更新成功，请重启应用以生效'})
        
    except json.JSONDecodeError as e:
        return jsonify({'success': False, 'message': f'配置文件格式错误: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'}), 500


def create_default_config():
    """创建默认配置文件"""
    default_config = {
        "mysql": {
            "host": "localhost",
            "port": 3306,
            "user": "root",
            "password": "123456",
            "database": "google_account"
        },
        "hubstudio": {
            "base_url": "http://localhost:6873",
            "app_id": "202601091459192924876173312",
            "app_secret": "MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQCUoDjNJ5nfphNcrMP0SrXnx5d4/4tZO0dYDvTJstk5wCgjoUDGb2WMSOGiXc5uC4vxQdZcnQZ8ae35qaI2+l4ARVpwFE5Fgir9RxTPcMrvRqvQh8rzWLp2z9wCXGOL7ZljDmgbCfrt5oLM/960OVXExy4duzJHgZ1QRTajkgH5hCRfbpJyI3G8MYlBIUhu6pKkHqUWvSLTttP1EO8XPLtQ4DeczaMA2oknI2M5SURVVhtE0AcFxrriJlp6rBmUwQuBCGlx+M6g5gNPy8MFHpZkZWra7b3bKQqe8nVN/q+EypsQDS+IeM77heAQl/9+hp7kJaBYBhZz6i0d02LyS79PAgMBAAECggEAP1/GeKw/L59YODcu4zcMM8Xmr+B/YdAmDsVp2auadsaaFv9GaJbNfTECjUJkqIXh6UDCkAEg5+IfaErN8ZV2ibUI6CuwaHEltZQeqomU7sx6rNOKVZNrBwiA7rzIcb0hn5xgBc+OoOyer50XMFAWY27vGhxdRyJcmwK4Vq0GjIcFzUu8l/NEPpNADmS94KUDQDpiWjoE74EJz2LQKOeTr3pAXQ7MddX5UbyHR1dtUTgWHXnw+aUMhBumjmXUO7IyTis4ZzFMWPGOh0G7Vg/roIQkm9TIqk9xiBlPKizvFT4ugKb+gVHfIiFCNyZI4P918iBlrzj2c52j88t0TUEhMQKBgQDZTzosC8MHpezCOE3wnM+Wkz4kk9b2h5899Z1v5N6fV7zVnYN6p+HZrANekSIZ1q7rBogiZ1+g+afviC+ot7PTuwDFns1kRhJ2OhFMt1qRlkOGWazo1qpkbLKDMgjDq+xxmYzEC6frH0QUYUEoe2pTRemjs9awzaQPBwZZwp+WFwKBgQCvFnTktmzodAaDuUr7Nct4KnBnjTOgZaaxoduyUR99TC6R1RWKxmvasgJWPp0PZBnqeBXVgdRvOx0wA9emUkd0ESKFlMTDXlqrWqJH/Qdc8BD4qwz1dIycnkRQJBOEgthR1hcwDujn2sBEZyNRqglVO0tCfw83zaV6D14klHAbiQKBgQCwnUOaKLUJskEKWNh/hfLxXhpTgBRlqTQzFzwthMWqm5RNyQbi2S8lyjey1CHy/hiLy3M5Ausl2cIzW2vgo+zzWDj4ZGhp5sl6bRdCUoK5cHbQ6nEti8pQdEdheXjGDyTL7xAJBbAj1/Vs2t4qGKQBqgCJm9ARQhDkZcEzkopBYQKBgQCqLAhm9wt5DrP6ORCwgoOFArKHYsznu4S9pxRSBti1PmMQ6Grsm5feUh9FVcvvVpp9skN+ZZZkma7vqPxjMhsyqyjDbmmjfURgwVFy6HHMmaPVHOMWejXkT0sUHUw/AbFgMNYOpp8mIg23Lgs85yf1CBFIyxeuZBjOPruAkCk6CQKBgQDQiEM92ojiO1sYODgslKgALYWN3EFmlszVr8TIVky1J262+wRusxyBTB/Rpuu4frDAgd8eqEPomZ/QCYzeyJGdq7FtOoXQO0PdqaSatqsq4OuWgSHi8wseLVNHBrmAAhIF38RK8Dc3GragwdtuspKj9nVAUfBdkuMPaZc1hp0vGA=="
        },
        "channel_avatar_path": ""
    }
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(default_config, f, ensure_ascii=False, indent=2)


def backup_and_save_config(config):
    """备份并保存配置文件"""
    # 创建备份
    if os.path.exists(CONFIG_FILE):
        backup_file = CONFIG_FILE + '.backup'
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                backup_content = f.read()
            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(backup_content)
        except Exception as e:
            print(f"警告: 创建备份文件失败 - {e}")
    
    # 保存新配置
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def validate_mysql_config(config):
    """验证 MySQL 配置"""
    required_fields = ['host', 'port', 'user', 'password', 'database']
    for field in required_fields:
        if field not in config:
            return False, f'缺少必需字段: {field}'
    
    # 验证端口号
    try:
        port = int(config['port'])
        if port < 1 or port > 65535:
            return False, '端口号必须在 1-65535 之间'
    except (ValueError, TypeError):
        return False, '端口号必须是数字'
    
    return True, None


def validate_hubstudio_config(config):
    """验证 Hubstudio 配置"""
    required_fields = ['base_url', 'app_id', 'app_secret']
    for field in required_fields:
        if field not in config:
            return False, f'缺少必需字段: {field}'
    
    # 验证 URL 格式
    if not config['base_url'].startswith(('http://', 'https://')):
        return False, 'base_url 必须以 http:// 或 https:// 开头'
    
    return True, None
