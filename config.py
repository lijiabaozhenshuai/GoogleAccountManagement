# -*- coding: utf-8 -*-
"""
配置文件 - 包含菜单结构配置
菜单配置说明：
- name: 菜单显示名称
- icon: 图标类名 (使用 Lucide Icons)
- url: 链接地址 (一级菜单如果有子菜单则设为 None)
- children: 子菜单列表 (二级菜单)
- order: 排序顺序 (数字越小越靠前)
"""

# 菜单配置 - 方便后续调整一级二级菜单及位置
MENU_CONFIG = [
    {
        "name": "数据管理",
        "icon": "database",
        "url": None,
        "order": 1,
        "children": [
            {"name": "账号管理", "icon": "user", "url": "/accounts", "order": 1},
            {"name": "手机号管理", "icon": "phone", "url": "/phones", "order": 2},
            {"name": "节点管理", "icon": "server", "url": "/nodes", "order": 3},
        ]
    },
    # 后续可以在这里添加更多一级菜单
    # {
    #     "name": "系统设置",
    #     "icon": "settings",
    #     "url": None,
    #     "order": 2,
    #     "children": [
    #         {"name": "用户管理", "icon": "users", "url": "/users", "order": 1},
    #     ]
    # },
]

# 数据库配置
# SQLite 配置（已弃用）
# DATABASE_URI = 'sqlite:///google_account.db'

# MySQL 配置
MYSQL_CONFIG = {
    "host": "localhost",      # 数据库主机地址
    "port": 3306,             # 端口
    "user": "root",           # 用户名
    "password": "123456",     # 密码
    "database": "google_account"  # 数据库名
}

DATABASE_URI = f"mysql+pymysql://{MYSQL_CONFIG['user']}:{MYSQL_CONFIG['password']}@{MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}?charset=utf8mb4"

# 应用配置
APP_CONFIG = {
    "SECRET_KEY": "your-secret-key-change-in-production",
    "DEBUG": True,
    "HOST": "0.0.0.0",
    "PORT": 5000,
}

