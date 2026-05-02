#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skuId收藏夹 - 本地存储+GUI选择"""

import json
import os

BOOKMARKS_FILE = os.path.join(os.path.dirname(__file__), '..', 'sku_bookmarks.json')

def load_bookmarks():
    """加载收藏的skuId列表"""
    try:
        with open(BOOKMARKS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        # 如果bookmarks不存在，从example复制
        import shutil
        example_file = os.path.join(os.path.dirname(__file__), '..', 'sku_bookmarks.example.json')
        if os.path.exists(example_file):
            try:
                shutil.copy2(example_file, BOOKMARKS_FILE)
                with open(BOOKMARKS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
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

