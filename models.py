# -*- coding: utf-8 -*-
"""
数据模型定义
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Account(db.Model):
    """账号管理模型"""
    __tablename__ = 'accounts'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    account = db.Column(db.String(255), nullable=False, comment='账号')
    password = db.Column(db.String(255), nullable=False, comment='密码')
    backup_email = db.Column(db.String(255), nullable=True, comment='辅助邮箱')
    status = db.Column(db.Boolean, default=False, comment='状态：是否使用')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    
    def to_dict(self):
        return {
            'id': self.id,
            'account': self.account,
            'password': self.password,
            'backup_email': self.backup_email or '',
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else '',
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else '',
        }


class Phone(db.Model):
    """手机号管理模型"""
    __tablename__ = 'phones'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    phone_number = db.Column(db.String(50), nullable=False, comment='手机号')
    sms_url = db.Column(db.String(500), nullable=True, comment='接码URL')
    status = db.Column(db.Boolean, default=False, comment='状态：是否使用')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    
    def to_dict(self):
        return {
            'id': self.id,
            'phone_number': self.phone_number,
            'sms_url': self.sms_url or '',
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


