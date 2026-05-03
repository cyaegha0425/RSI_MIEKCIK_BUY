#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
咩咩Kick! V3.0.0 SKU探测脚本
用法: python sku_probe.py [关键词]
例:   python sku_probe.py Hercules

功能：搜索关键词，列出拦截到的所有商品（名称+skuId+价格），不执行加购。
"""

import sys
import json
import time

# 添加项目路径
sys.path.insert(0, '.')

from modules.browser import create_browser, login
from modules.sku_interceptor import SKUInterceptor
from modules.sku_bookmarks import add_bookmark, load_bookmarks
from modules import config
from playwright.sync_api import sync_playwright

CFG = config.CFG


def probe(keywords: str):
    """搜索关键词，拦截并显示所有商品"""
    print(f"\n{'='*60}")
    print(f"  SKU探测 — 关键词: {keywords}")
    print(f"{'='*60}\n")

    with sync_playwright() as p:
        ctx = create_browser(p)
        page = ctx.new_page()
        page.set_default_timeout(15000)

        try:
            login(ctx)

            # 先创建拦截器并注册（必须在goto之前，否则漏掉响应）
            interceptor = SKUInterceptor(page, keywords, "")
            interceptor.register()  # 注册page.on('response')
            print(f"  📍 拦截器已注册，等待GraphQL响应...\n")

            # 构造带keywords的URL（触发SPA+GraphQL）
            url = CFG["BROWSE_URL_PREFIX"] + keywords
            print(f"  📍 打开: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=20000)


            # 等待拦截器收集
            print(f"  ⏳ 等待5秒收集响应...\n")
            time.sleep(5)

            # 刷新一次触发更多GraphQL
            print(f"  🔄 刷新页面...")
            interceptor.reset_start_time()  # 重置计时+重新注册
            page.reload(wait_until="domcontentloaded", timeout=15000)
            time.sleep(5)

            # 获取结果
            products = interceptor.get_all_products()

            if not products:
                print(f"\n  ❌ 未拦截到任何商品")
                print(f"  提示：尝试不同关键词，或检查登录状态")
                return

            # 显示结果
            print(f"\n{'='*60}")
            print(f"  拦截到 {len(products)} 个商品:")
            print(f"{'='*60}\n")

            # 按名称排序
            products.sort(key=lambda x: x.get('name', '').lower())

            for i, p in enumerate(products, 1):
                name = p.get('name', 'Unknown')
                sku_id = p.get('skuId', '?')
                price = p.get('price', 0)
                in_stock = p.get('inStock', True)
                stock_mark = "✅" if in_stock else "❌"
                price_str = f"${price}" if price else "价格未知"

                # 高亮匹配关键词的
                if keywords.lower() in name.lower():
                    print(f"  🎯 {i:2d}. {stock_mark} {name}")
                else:
                    print(f"     {i:2d}. {stock_mark} {name}")
                print(f"         SKU: {sku_id}  |  {price_str}")

            # 询问是否保存到收藏夹
            print(f"\n{'='*60}")
            print(f"  是否保存这些商品到收藏夹？")
            save = input("  输入 y 保存，其他键跳过: ").strip().lower()

            if save == 'y':
                saved = 0
                for p in products:
                    name = p.get('name', '')
                    sku_id = p.get('skuId', '')
                    price = p.get('price', 0) or 0
                    if not name.strip() or name.strip().lower() == 'unknown':
                        continue
                    add_bookmark(name, str(sku_id), price)
                    saved += 1
                print(f"\n  ✅ 已保存 {saved} 个商品到收藏夹")

                # 显示当前收藏夹
                bookmarks = load_bookmarks()
                print(f"\n  📦 收藏夹现有 {len(bookmarks)} 个条目")
            else:
                print(f"\n  跳过保存")

            # 导出JSON
            output_file = f"sku_probe_{keywords}_{time.strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
            print(f"\n  📄 完整数据已保存: {output_file}")

        except Exception as e:
            print(f"\n  ❌ 错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            ctx.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python sku_probe.py [关键词]")
        print("例:   python sku_probe.py Hercules")
        print("      python sku_probe.py PTV")
        sys.exit(1)

    keyword = " ".join(sys.argv[1:])
    probe(keyword)
