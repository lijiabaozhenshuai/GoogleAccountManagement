# -*- coding: utf-8 -*-
"""
PyInstaller 运行时钩子
用于处理打包后的路径问题
"""
import sys
import os

# 获取应用程序路径
if getattr(sys, 'frozen', False):
    # 打包后的环境
    application_path = sys._MEIPASS
    # 设置工作目录为可执行文件所在目录
    os.chdir(os.path.dirname(sys.executable))
else:
    # 开发环境
    application_path = os.path.dirname(os.path.abspath(__file__))

# 确保 app_data 和 instance 目录存在
app_data_dir = os.path.join(os.getcwd(), 'app_data')
instance_dir = os.path.join(os.getcwd(), 'instance')

if not os.path.exists(app_data_dir):
    os.makedirs(app_data_dir)

if not os.path.exists(instance_dir):
    os.makedirs(instance_dir)

print(f"应用程序路径: {application_path}")
print(f"工作目录: {os.getcwd()}")
print(f"数据目录: {app_data_dir}")
print(f"实例目录: {instance_dir}")
