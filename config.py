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
    {
        "name": "浏览器管理",
        "icon": "chrome",
        "url": None,
        "order": 2,
        "children": [
            {"name": "批量创建窗口", "icon": "plus-square", "url": "/browser-create", "order": 1},
            {"name": "浏览器窗口列表", "icon": "layout-grid", "url": "/browser-list", "order": 2},
        ]
    },
    {
        "name": "系统管理",
        "icon": "settings",
        "url": None,
        "order": 3,
        "children": [
            {"name": "系统设置", "icon": "sliders", "url": "/settings", "order": 1},
        ]
    },
]

# Hubstudio API 配置
HUBSTUDIO_CONFIG = {
    "base_url": "http://localhost:6873",
    "app_id": "202601091459192924876173312",
    "app_secret": "MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQCUoDjNJ5nfphNcrMP0SrXnx5d4/4tZO0dYDvTJstk5wCgjoUDGb2WMSOGiXc5uC4vxQdZcnQZ8ae35qaI2+l4ARVpwFE5Fgir9RxTPcMrvRqvQh8rzWLp2z9wCXGOL7ZljDmgbCfrt5oLM/960OVXExy4duzJHgZ1QRTajkgH5hCRfbpJyI3G8MYlBIUhu6pKkHqUWvSLTttP1EO8XPLtQ4DeczaMA2oknI2M5SURVVhtE0AcFxrriJlp6rBmUwQuBCGlx+M6g5gNPy8MFHpZkZWra7b3bKQqe8nVN/q+EypsQDS+IeM77heAQl/9+hp7kJaBYBhZz6i0d02LyS79PAgMBAAECggEAP1/GeKw/L59YODcu4zcMM8Xmr+B/YdAmDsVp2auadsaaFv9GaJbNfTECjUJkqIXh6UDCkAEg5+IfaErN8ZV2ibUI6CuwaHEltZQeqomU7sx6rNOKVZNrBwiA7rzIcb0hn5xgBc+OoOyer50XMFAWY27vGhxdRyJcmwK4Vq0GjIcFzUu8l/NEPpNADmS94KUDQDpiWjoE74EJz2LQKOeTr3pAXQ7MddX5UbyHR1dtUTgWHXnw+aUMhBumjmXUO7IyTis4ZzFMWPGOh0G7Vg/roIQkm9TIqk9xiBlPKizvFT4ugKb+gVHfIiFCNyZI4P918iBlrzj2c52j88t0TUEhMQKBgQDZTzosC8MHpezCOE3wnM+Wkz4kk9b2h5899Z1v5N6fV7zVnYN6p+HZrANekSIZ1q7rBogiZ1+g+afviC+ot7PTuwDFns1kRhJ2OhFMt1qRlkOGWazo1qpkbLKDMgjDq+xxmYzEC6frH0QUYUEoe2pTRemjs9awzaQPBwZZwp+WFwKBgQCvFnTktmzodAaDuUr7Nct4KnBnjTOgZaaxoduyUR99TC6R1RWKxmvasgJWPp0PZBnqeBXVgdRvOx0wA9emUkd0ESKFlMTDXlqrWqJH/Qdc8BD4qwz1dIycnkRQJBOEgthR1hcwDujn2sBEZyNRqglVO0tCfw83zaV6D14klHAbiQKBgQCwnUOaKLUJskEKWNh/hfLxXhpTgBRlqTQzFzwthMWqm5RNyQbi2S8lyjey1CHy/hiLy3M5Ausl2cIzW2vgo+zzWDj4ZGhp5sl6bRdCUoK5cHbQ6nEti8pQdEdheXjGDyTL7xAJBbAj1/Vs2t4qGKQBqgCJm9ARQhDkZcEzkopBYQKBgQCqLAhm9wt5DrP6ORCwgoOFArKHYsznu4S9pxRSBti1PmMQ6Grsm5feUh9FVcvvVpp9skN+ZZZkma7vqPxjMhsyqyjDbmmjfURgwVFy6HHMmaPVHOMWejXkT0sUHUw/AbFgMNYOpp8mIg23Lgs85yf1CBFIyxeuZBjOPruAkCk6CQKBgQDQiEM92ojiO1sYODgslKgALYWN3EFmlszVr8TIVky1J262+wRusxyBTB/Rpuu4frDAgd8eqEPomZ/QCYzeyJGdq7FtOoXQO0PdqaSatqsq4OuWgSHi8wseLVNHBrmAAhIF38RK8Dc3GragwdtuspKj9nVAUfBdkuMPaZc1hp0vGA=="
}

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

# 2Captcha API 配置（用于解决人机验证）
CAPTCHA_CONFIG = {
    "api_key": "d9718240bbbf8709464fc7f74f6498bc",  # 请替换为您的2captcha API密钥
    "enabled": True,  # 是否启用验证码解决功能
}

# 频道头像路径配置
CHANNEL_AVATAR_PATH = ""

