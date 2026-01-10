# -*- coding: utf-8 -*-
"""
谷歌账号管理系统 - 主应用
"""
from flask import Flask
from flask_migrate import Migrate
from models import db
from config import MENU_CONFIG, DATABASE_URI, APP_CONFIG

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = APP_CONFIG['SECRET_KEY']

db.init_app(app)
migrate = Migrate(app, db)


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


# 注册蓝图
from routes import page_bp, account_bp, login_bp, phone_bp, node_bp, browser_bp, settings_bp

app.register_blueprint(page_bp)
app.register_blueprint(account_bp)
app.register_blueprint(login_bp)
app.register_blueprint(phone_bp)
app.register_blueprint(node_bp)
app.register_blueprint(browser_bp)
app.register_blueprint(settings_bp)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host=APP_CONFIG['HOST'], port=APP_CONFIG['PORT'], debug=APP_CONFIG['DEBUG'])
