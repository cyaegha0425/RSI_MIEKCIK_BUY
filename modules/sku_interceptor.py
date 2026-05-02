#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
咩咩Kick! V3.0.0
SKU拦截器模块 - 从GraphQL响应中提取skuId
"""

import json
import re
import time
import logging
from typing import Optional, List, Dict

from . import config

log = config.log


class SKUInterceptor:
    """SKU拦截器 - V3.0.0 全API抢购架构核心组件
    
    功能：
    1. 注册page.on('response')拦截器
    2. 过滤GraphQL响应
    3. 解析store.listing.resources提取商品信息
    4. 支持关键词匹配找skuId
    """
    
    def __init__(self, page, keywords: str = "", exclude_keywords: str = ""):
        """
        Args:
            page: Playwright page对象
            keywords: 搜索关键词（空格分隔）
            exclude_keywords: 排除关键词（英文逗号分隔）
        """
        self.page = page
        self._start_time = None  # 计时用, 刷新时设置
        self.keywords = [k.strip().lower() for k in keywords.split() if k.strip()]
        self.exclude_keywords = [k.strip().lower() for k in exclude_keywords.split(',') if k.strip()]
        
        # 存储拦截到的商品数据
        self._products = []
        self._sku_id = None
        self._intercepted = False
    
    def reset_start_time(self):
        """Reset timing start point, call on page refresh"""
        self._start_time = time.time()
        log.info("   [计时] 计时起点已重置")
        
        # 编译正则表达式
        self._keywords_pattern = None
        if self.keywords:
            pattern = '|'.join(re.escape(k) for k in self.keywords)
            self._keywords_pattern = re.compile(pattern, re.IGNORECASE)
        
        self._exclude_pattern = None
        if self.exclude_keywords:
            pattern = '|'.join(re.escape(k) for k in self.exclude_keywords)
            self._exclude_pattern = re.compile(pattern, re.IGNORECASE)
        
        # 注册拦截器
        self._register_interceptor()
    
    def _register_interceptor(self):
        """注册response拦截器"""
        def handle_response(response):
            try:
                url = response.url
                # 只处理GraphQL响应
                if '/graphql' not in url:
                    return
                
                # DEBUG: 记录所有graphql响应
                log.info(f"   [拦截器DEBUG] 收到GraphQL响应: status={response.status}, url={url[:80]}")
                
                # 只处理成功的响应
                if response.status != 200:
                    return
                
                # 异步获取响应体（不会阻塞）
                try:
                    body = response.text()
                    # DEBUG: 记录响应体前200字符
                    log.info(f"   [拦截器DEBUG] body前200字: {body[:200]}")
                except:
                    return
                
                self._parse_response(body)
                
            except Exception as e:
                log.warning(f"   [拦截器DEBUG] 异常: {e}")
        
        # 注册拦截器
        self.page.on('response', handle_response)
        log.info("📍 [SKU拦截器] 已注册GraphQL响应拦截")
    
    def _parse_response(self, body: str):
        """解析GraphQL响应体"""
        try:
            data = json.loads(body)
            
            # 遍历响应查找listing数据
            self._extract_listings(data)
            
        except json.JSONDecodeError:
            pass
        except Exception as e:
            pass
    
    def _extract_listings(self, obj, depth=0):
        """递归提取listing数据（防止深度过深）"""
        if depth > 10:
            return
        
        if isinstance(obj, dict):
            # 检查是否包含listing.resources
            if 'listing' in obj and 'resources' in obj.get('listing', {}):
                resources = obj['listing']['resources']
                if isinstance(resources, list):
                    for resource in resources:
                        self._process_product(resource)
            
            # 检查是否包含直接的资源列表
            if 'resources' in obj and isinstance(obj['resources'], list):
                for resource in obj['resources']:
                    self._process_product(resource)
            
            # 递归处理子节点
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    self._extract_listings(value, depth + 1)
        
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    self._extract_listings(item, depth + 1)
    
    def _process_product(self, resource: dict):
        """处理单个商品资源"""
        if not isinstance(resource, dict):
            return
        
        # 提取商品信息
        name = resource.get('name', '')
        sku_id = resource.get('skuId', '') or resource.get('id', '')
        in_stock = resource.get('inStock', None)
        if in_stock is None:
            in_stock = resource.get('stockLevel', 'available') != 'none'
        
        # 跳过无skuId或不在架的商品
        if not sku_id:
            return
        
        # 计时：首次拦截到商品的时间(从刷新开始算)
        if self._start_time and self._start_time > 0:
            elapsed = time.time() - self._start_time
            log.info(f"   [计时] 首次商品拦截: +{elapsed:.1f}秒")
            self._start_time = -1  # 只记录一次
        
        # 记录商品信息
        product_info = {
            'name': name,
            'skuId': sku_id,
            'inStock': in_stock
        }
        
        # 去重
        if any(p['skuId'] == sku_id for p in self._products):
            return
        
        self._products.append(product_info)
        log.info(f"   [拦截] {name}: skuId={sku_id}, inStock={in_stock}")
        
        # 检查是否匹配关键词
        if self._is_match(name):
            self._sku_id = sku_id
            self._intercepted = True
            log.info(f"   🎯 匹配成功! skuId={sku_id}")
    
    def _is_match(self, name: str) -> bool:
        """检查商品名称是否匹配关键词"""
        if not name:
            return False
        
        name_lower = name.lower()
        
        # 必须包含所有关键词
        if self._keywords_pattern:
            if not self._keywords_pattern.search(name_lower):
                return False
        
        # 不能包含排除关键词
        if self._exclude_pattern:
            if self._exclude_pattern.search(name_lower):
                return False
        
        return True
    
    def get_sku_id(self) -> Optional[str]:
        """获取拦截到的skuId"""
        return self._sku_id
    
    def get_all_products(self) -> List[Dict]:
        """获取所有拦截到的商品列表"""
        return self._products.copy()
    
    def is_intercepted(self) -> bool:
        """检查是否已拦截到skuId"""
        return self._intercepted
    
    def get_products_summary(self) -> str:
        """获取商品列表摘要"""
        if not self._products:
            return "暂无商品"
        
        lines = []
        for p in self._products:
            match_mark = "🎯" if p['skuId'] == self._sku_id else "  "
            stock_mark = "✅" if p['inStock'] else "❌"
            lines.append(f"{match_mark}{stock_mark} {p['name']}: {p['skuId']}")
        
        return "\n".join(lines)


def create_interceptor(page, keywords: str = "", exclude_keywords: str = "") -> SKUInterceptor:
    """创建SKU拦截器"""
    return SKUInterceptor(page, keywords, exclude_keywords)
