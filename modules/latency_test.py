#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
咩咩Kick! V3.0.0
服务器延迟测试模块
"""

import json
import time
import urllib.request
import urllib.error
import tkinter as tk
from . import config

log = config.log

CART_QUERY = '''
query MiniCartWidgetInitializationQuery($storeFront: String) {
  store(name: $storeFront) {
    cart {
      id
      lineItemsQties
      __typename
    }
    __typename
  }
}
'''

GUI_BG_COLOR = "#A8B4D4"
GUI_TITLE_COLOR = "#1a3a5c"
GUI_TEXT_COLOR = "#2d2d2d"


def measure_latency(cookie_str, csrf_token, count=10, callback=None):
    """测量RSI服务器延迟"""
    results = []
    for i in range(count):
        payload = [{
            "operationName": "MiniCartWidgetInitializationQuery",
            "variables": {"storeFront": "pledge"},
            "query": CART_QUERY.strip()
        }]
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://robertsspaceindustries.com/en/store/pledge/cart',
            'Origin': 'https://robertsspaceindustries.com',
            'Cookie': cookie_str,
        }
        body = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(config.CFG["GRAPHQL_URL"], data=body, headers=headers, method='POST')
        if csrf_token:
            req.add_header('x-csrf-token', csrf_token)

        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                ms = (time.time() - t0) * 1000
                data = json.loads(resp.read().decode())
                if isinstance(data, list): data = data[0]
                errors = data.get('errors', [])
                if errors:
                    status = f"ERROR: {errors[0].get('message','')[:30]}"
                else:
                    cart = data.get('data',{}).get('store',{}).get('cart',{})
                    items = cart.get('lineItemsQties', '?')
                    status = f"OK (items:{items})"
        except urllib.error.HTTPError as e:
            ms = (time.time() - t0) * 1000
            status = f"HTTP_{e.code}"
        except Exception as e:
            ms = (time.time() - t0) * 1000
            status = type(e).__name__

        results.append(ms)
        if callback:
            callback(i + 1, ms, status)
        if i < count - 1:
            time.sleep(1)
    return results


def analyze_results(results):
    """分析延迟结果"""
    if not results:
        return None
    rs = sorted(results)
    avg = sum(results) / len(results)
    p50 = rs[len(rs) // 2]
    p90 = rs[int(len(rs) * 0.9)]
    mn, mx = min(results), max(results)
    if avg < 300: grade = "🟢 极快"
    elif avg < 600: grade = "🟡 正常"
    elif avg < 1000: grade = "🟠 偏慢"
    else: grade = "🔴 很慢"
    return {
        'avg': avg, 'p50': p50, 'p90': p90,
        'min': mn, 'max': mx, 'jitter': mx - mn,
        'grade': grade,
        'poll_rate': avg / 1000 + 0.5
    }


def get_auth_from_browser():
    """从浏览器CDP获取认证信息"""
    try:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        browser = pw.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
        browser_cookies = page.context.cookies()
        cookie_parts = [f"{c['name']}={c['value']}" for c in browser_cookies
                       if c.get('domain','').endswith('robertsspaceindustries.com')]
        cookie_str = "; ".join(cookie_parts)
        csrf_token = ""
        try:
            csrf_token = page.evaluate("""() => {
                const meta = document.querySelector('meta[name="csrf-token"]');
                return meta ? meta.getAttribute('content') : '';
            }""")
        except: pass
        browser.close()
        pw.stop()
        return cookie_str, csrf_token
    except Exception as e:
        log.error(f"获取浏览器认证失败: {e}")
        return None, None


def show_latency_dialog(parent):
    """显示服务器延迟测试对话框"""
    dialog = tk.Toplevel(parent)
    dialog.title("服务器延迟测试")
    dialog.geometry("520x500")
    dialog.configure(bg=GUI_BG_COLOR)
    dialog.resizable(False, False)
    dialog.transient(parent)
    dialog.grab_set()

    # 标题
    title_frame = tk.Frame(dialog, bg=GUI_BG_COLOR, padx=6, pady=3)
    title_frame.pack(fill='x')
    tk.Label(title_frame, text="🕐 RSI服务器延迟测试",
             font=("Microsoft YaHei UI", 16, "bold"),
             fg=GUI_TITLE_COLOR, bg=GUI_BG_COLOR).pack()
    tk.Label(title_frame, text="购物车查询测延迟，不修改任何数据",
             font=("Microsoft YaHei UI", 10), fg=GUI_TEXT_COLOR, bg=GUI_BG_COLOR).pack()

    # 结果区
    result_frame = tk.Frame(dialog, bg=GUI_BG_COLOR, padx=10, pady=5)
    result_frame.pack(fill='both', expand=True)
    result_text = tk.Text(result_frame, font=("Consolas", 10), bg="#1e1e2e", fg="#cdd6f4",
                          width=58, height=18, relief='flat', padx=8, pady=8)
    result_text.pack(fill='both', expand=True)
    result_text.insert('end', "点击「开始测试」测量RSI服务器延迟\n\n")
    result_text.insert('end', "需要浏览器已启动CDP模式并登录RSI\n")
    result_text.config(state='disabled')

    # 统计区
    stats_label = tk.Label(dialog, text="", font=("Microsoft YaHei UI", 12, "bold"),
                           fg=GUI_TITLE_COLOR, bg=GUI_BG_COLOR)
    stats_label.pack(pady=3)

    # 按钮区
    btn_frame = tk.Frame(dialog, bg=GUI_BG_COLOR, pady=5)
    btn_frame.pack()
    test_running = [False]

    def update_text(msg):
        result_text.config(state='normal')
        result_text.insert('end', msg)
        result_text.see('end')
        result_text.config(state='disabled')

    def run_test():
        if test_running[0]: return
        test_running[0] = True
        start_btn.config(state='disabled', text="测试中...")
        result_text.config(state='normal')
        result_text.delete('1.0', 'end')
        result_text.insert('end', "🔄 正在测试...\n\n")
        result_text.config(state='disabled')
        stats_label.config(text="")

        try:
            cookie_str, csrf_token = get_auth_from_browser()
            if not cookie_str:
                update_text("❌ 无法获取Cookies\n请确保浏览器已启动CDP模式并登录RSI\n")
                test_running[0] = False
                start_btn.config(state='normal', text="开始测试")
                return

            update_text("✅ 认证获取成功\n\n")

            def on_result(num, ms, status):
                bar = "█" * int(ms / 100)
                update_text(f"  #{num:02d}  {ms:6.0f}ms {bar} {status}\n")

            results = measure_latency(cookie_str, csrf_token, count=10, callback=on_result)

            stats = analyze_results(results)
            if stats:
                update_text(f"\n{'─' * 45}\n")
                update_text(f"  平均: {stats['avg']:.0f}ms | P50: {stats['p50']:.0f}ms | P90: {stats['p90']:.0f}ms\n")
                update_text(f"  最小: {stats['min']:.0f}ms | 最大: {stats['max']:.0f}ms | 抖动: {stats['jitter']:.0f}ms\n")
                update_text(f"  评级: {stats['grade']}\n")
                update_text(f"  预估轮询: 0.5s间隔实际约{stats['poll_rate']:.1f}秒/次\n")
                stats_label.config(text=f"{stats['grade']}  平均{stats['avg']:.0f}ms  P50={stats['p50']:.0f}ms")
        except Exception as e:
            update_text(f"\n❌ 测试失败: {e}\n请确保浏览器已启动CDP模式\n")

        test_running[0] = False
        start_btn.config(state='normal', text="开始测试")

    start_btn = tk.Button(btn_frame, text="开始测试", command=run_test,
                          font=("Microsoft YaHei UI", 12, "bold"),
                          fg="white", bg="#6A8CBA", relief='flat',
                          padx=20, pady=5, cursor='hand2')
    start_btn.pack(side='left', padx=10)

    close_btn = tk.Button(btn_frame, text="关闭", command=dialog.destroy,
                          font=("Microsoft YaHei UI", 12, "bold"),
                          fg="white", bg="#9E6B7A", relief='flat',
                          padx=20, pady=5, cursor='hand2')
    close_btn.pack(side='left', padx=10)
