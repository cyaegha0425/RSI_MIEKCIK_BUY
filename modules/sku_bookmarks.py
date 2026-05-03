#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skuId收藏夹 - 本地存储+GUI选择"""

import json
import os
import sys

# PyInstaller打包后用EXE所在目录，开发环境用项目根目录
if getattr(sys, 'frozen', False):
    _BASE_PATH = os.path.dirname(sys.executable)
else:
    _BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BOOKMARKS_FILE = os.path.join(_BASE_PATH, 'sku_bookmarks.json')

def load_bookmarks():
    """加载收藏的skuId列表，首次使用自动从example复制"""
    if not os.path.exists(BOOKMARKS_FILE):
        import shutil
        example_file = os.path.join(_BASE_PATH, 'sku_bookmarks.example.json')
        if os.path.exists(example_file):
            try:
                os.makedirs(os.path.dirname(BOOKMARKS_FILE), exist_ok=True)
                shutil.copy2(example_file, BOOKMARKS_FILE)
            except:
                pass
    try:
        with open(BOOKMARKS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_bookmarks(bookmarks):
    """保存收藏的skuId列表"""
    with open(BOOKMARKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(bookmarks, f, ensure_ascii=False, indent=2)

def add_bookmark(name: str, sku_id: str, price: float = 0):
    """添加一个skuId到收藏夹"""
    bookmarks = load_bookmarks()
    # 检查是否已存在（按skuId去重）
    for b in bookmarks:
        if b.get('sku_id') == sku_id:
            b['name'] = name  # 更新名称
            b['price'] = price
            save_bookmarks(bookmarks)
            return
    bookmarks.append({'name': name, 'sku_id': sku_id, 'price': price})
    save_bookmarks(bookmarks)

def remove_bookmark(sku_id: str):
    """删除一个收藏"""
    bookmarks = load_bookmarks()
    bookmarks = [b for b in bookmarks if b.get('sku_id') != sku_id]
    save_bookmarks(bookmarks)

