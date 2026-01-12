# -*- coding: utf-8 -*-
"""
路由模块
"""
from flask import Blueprint

# 创建蓝图
page_bp = Blueprint('pages', __name__)
account_bp = Blueprint('accounts', __name__, url_prefix='/api/accounts')
login_bp = Blueprint('login', __name__, url_prefix='/api')
phone_bp = Blueprint('phones', __name__, url_prefix='/api/phones')
node_bp = Blueprint('nodes', __name__, url_prefix='/api/nodes')
browser_bp = Blueprint('browsers', __name__, url_prefix='/api')
settings_bp = Blueprint('settings', __name__, url_prefix='/api/settings')
channel_bp = Blueprint('channels', __name__, url_prefix='/api/channels')

# 导入路由
from routes import page_routes
from routes import account_routes
from routes import login_routes
from routes import phone_routes
from routes import node_routes
from routes import browser_routes
from routes import settings_routes
from routes import channel_routes

