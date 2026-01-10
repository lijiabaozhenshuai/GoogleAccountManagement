# -*- coding: utf-8 -*-
"""
页面路由
"""
from flask import render_template
from routes import page_bp


@page_bp.route('/')
def index():
    """首页 - 重定向到账号管理"""
    return render_template('accounts.html', page_title='账号管理', current_url='/accounts')


@page_bp.route('/accounts')
def accounts_page():
    """账号管理页面"""
    return render_template('accounts.html', page_title='账号管理', current_url='/accounts')


@page_bp.route('/phones')
def phones_page():
    """手机号管理页面"""
    return render_template('phones.html', page_title='手机号管理', current_url='/phones')


@page_bp.route('/nodes')
def nodes_page():
    """节点管理页面"""
    return render_template('nodes.html', page_title='节点管理', current_url='/nodes')


@page_bp.route('/browser-create')
def browser_create_page():
    """批量创建浏览器窗口页面"""
    return render_template('browser_create.html', page_title='批量创建窗口', current_url='/browser-create')


@page_bp.route('/browser-list')
def browser_list_page():
    """浏览器窗口列表页面"""
    return render_template('browser_list.html', page_title='浏览器窗口列表', current_url='/browser-list')


@page_bp.route('/settings')
def settings_page():
    """系统设置页面"""
    return render_template('settings.html', page_title='系统设置', current_url='/settings')
