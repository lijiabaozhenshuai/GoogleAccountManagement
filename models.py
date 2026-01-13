# -*- coding: utf-8 -*-
"""
数据模型定义
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


# 登录状态枚举
LOGIN_STATUS = {
    'not_logged': '未登录',
    'logging': '登录中',
    'success': '登录成功',
    'password_error': '密码错误',
    'need_phone': '需要绑定手机号',
    'need_2fa': '需要2FA验证',
    'disabled': '账号被禁用',
    'need_appeal': '需要申诉',
    'appeal_success': '已申诉成功',
    'appeal_failed': '申诉失败',
    'failed': '登录失败',
}


class Account(db.Model):
    """账号管理模型"""
    __tablename__ = 'accounts'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    account = db.Column(db.String(255), nullable=False, comment='账号')
    password = db.Column(db.String(255), nullable=False, comment='密码')
    backup_email = db.Column(db.String(255), nullable=True, comment='辅助邮箱')
    phone_id = db.Column(db.Integer, db.ForeignKey('phones.id'), nullable=True, comment='绑定的手机号ID')
    status = db.Column(db.Boolean, default=False, comment='状态：是否使用')
    login_status = db.Column(db.String(50), default='not_logged', comment='登录状态')
    browser_env_id = db.Column(db.String(100), nullable=True, comment='浏览器环境ID')
    channel_status = db.Column(db.String(50), default='not_created', comment='频道状态：not_created/created/failed')
    channel_url = db.Column(db.String(500), nullable=True, comment='频道链接')
    monetization_requirement = db.Column(db.String(10), nullable=True, comment='创收次数要求：3m/10m')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    
    # 关联登录日志
    login_logs = db.relationship('LoginLog', backref='account_ref', lazy='dynamic')
    # 关联手机号
    phone = db.relationship('Phone', backref='bound_account', foreign_keys=[phone_id])
    
    def to_dict(self):
        # 频道状态映射
        channel_status_map = {
            'not_created': '未创建',
            'created': '创建成功',
            'failed': '创建失败',
        }
        return {
            'id': self.id,
            'account': self.account,
            'password': self.password,
            'backup_email': self.backup_email or '',
            'phone_id': self.phone_id,
            'phone_number': self.phone.phone_number if self.phone else '',
            'status': self.status,
            'login_status': self.login_status or 'not_logged',
            'login_status_text': LOGIN_STATUS.get(self.login_status, '未知'),
            'browser_env_id': self.browser_env_id or '',
            'channel_status': self.channel_status or 'not_created',
            'channel_status_text': channel_status_map.get(self.channel_status, '未创建'),
            'channel_url': self.channel_url or '',
            'monetization_requirement': self.monetization_requirement or '',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else '',
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else '',
        }


class LoginLog(db.Model):
    """登录日志模型"""
    __tablename__ = 'login_logs'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False, comment='账号ID')
    browser_env_id = db.Column(db.String(100), nullable=True, comment='浏览器环境ID')
    action = db.Column(db.String(50), nullable=False, comment='操作类型')
    status = db.Column(db.String(50), nullable=False, comment='状态')
    message = db.Column(db.Text, nullable=True, comment='详细信息')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    
    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'browser_env_id': self.browser_env_id or '',
            'action': self.action,
            'status': self.status,
            'message': self.message or '',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else '',
        }


class BrowserEnv(db.Model):
    """浏览器环境状态模型（本地记录HubStudio环境使用状态）"""
    __tablename__ = 'browser_envs'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    container_code = db.Column(db.String(100), unique=True, nullable=False, comment='环境ID')
    container_name = db.Column(db.String(255), nullable=True, comment='环境名称')
    status = db.Column(db.Boolean, default=False, comment='状态：是否已使用')
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True, comment='关联账号ID')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    
    def to_dict(self):
        return {
            'id': self.id,
            'container_code': self.container_code,
            'container_name': self.container_name or '',
            'status': self.status,
            'account_id': self.account_id,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else '',
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else '',
        }


class Phone(db.Model):
    """手机号管理模型"""
    __tablename__ = 'phones'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    phone_number = db.Column(db.String(50), nullable=False, comment='手机号')
    sms_url = db.Column(db.String(500), nullable=True, comment='接码URL')
    expire_time = db.Column(db.DateTime, nullable=True, comment='过期时间')
    status = db.Column(db.Boolean, default=False, comment='状态：是否使用')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    
    def to_dict(self):
        return {
            'id': self.id,
            'phone_number': self.phone_number,
            'sms_url': self.sms_url or '',
            'expire_time': self.expire_time.strftime('%Y-%m-%d') if self.expire_time else '',
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else '',
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else '',
        }


class Node(db.Model):
    """节点管理模型"""
    __tablename__ = 'nodes'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ip = db.Column(db.String(50), nullable=False, comment='节点IP')
    port = db.Column(db.Integer, nullable=False, comment='端口')
    username = db.Column(db.String(100), nullable=True, comment='用户名')
    password = db.Column(db.String(255), nullable=True, comment='密码')
    status = db.Column(db.Boolean, default=False, comment='状态：是否使用')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    
    def to_dict(self):
        return {
            'id': self.id,
            'ip': self.ip,
            'port': self.port,
            'username': self.username or '',
            'password': self.password or '',
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else '',
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else '',
        }


