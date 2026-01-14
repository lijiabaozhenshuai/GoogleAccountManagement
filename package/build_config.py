# -*- coding: utf-8 -*-
"""
PyInstaller 打包配置
"""
import os

# 应用信息
APP_NAME = "谷歌账号管理系统"
APP_VERSION = "1.0.0"
MAIN_SCRIPT = "main.py"  # 相对于项目根目录
ICON_FILE = None  # 如果有图标，填写图标路径

# 数据文件和文件夹（相对于项目根目录）
datas = [
    ('templates', 'templates'),
    ('static', 'static'),
    ('config.json.example', '.'),
    ('申诉文件.xlsx', '.'),
]

# 隐藏导入（PyInstaller可能检测不到的模块）
hiddenimports = [
    'flask',
    'flask_sqlalchemy',
    'flask_migrate',
    'sqlalchemy.sql.default_comparator',
    'pymysql',
    'pandas',
    'openpyxl',
    'selenium',
    'pyautogui',
    'pyperclip',
    'requests',
]

# 排除的模块（减小打包体积）
excludes = [
    'matplotlib',
    'numpy.testing',
    'scipy',
    'tkinter',
]

# 二进制文件
binaries = []

# 收集所有子包
collect_submodules = [
    'flask',
    'sqlalchemy',
    'alembic',
]

# 收集数据
collect_data = [
    'flask',
    'flask_sqlalchemy',
    'flask_migrate',
]
