#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skuId收藏夹 - 本地存储+GUI选择"""

import json
import os
import sys

from . import config as _cfg

BOOKMARKS_FILE = os.path.join(_cfg.BASE_PATH, 'sku_bookmarks.json')

def load_bookmarks():
    """加载收藏的skuId列表，首次使用自动从example复制"""
    if not os.path.exists(BOOKMARKS_FILE):
        import shutil
        example_file = os.path.join(_cfg.BASE_PATH, 'sku_bookmarks.example.json')
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f'[收藏夹] BOOKMARKS_FILE不存在: {BOOKMARKS_FILE}')
        logger.info(f'[收藏夹] example路径: {example_file}')
        logger.info(f'[收藏夹] BASE_PATH: {_cfg.BASE_PATH}')
        logger.info(f'[收藏夹] example存在: {os.path.exists(example_file)}')
        if os.path.exists(example_file):
            try:
                os.makedirs(os.path.dirname(BOOKMARKS_FILE), exist_ok=True)
                shutil.copy2(example_file, BOOKMARKS_FILE)
                logger.info(f'[收藏夹] 复制成功')
            except Exception as e:
                logger.error(f'[收藏夹] 复制失败: {e}')
        else:
            logger.warning(f'[收藏夹] example文件不存在，跳过复制')
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

