#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
咩咩Kick! V3.0.0
浏览器操作模块
"""

import json
import os
import subprocess
import time

from . import config
from .api_client import RSIClient

# 导入config中的常量
CFG = config.CFG
log = config.log


# ============================================================
# 浏览器基础函数
# ============================================================

def proxy():
    """获取代理设置"""
    if CFG.get("PROXY"):
        return CFG["PROXY"]
    if os.name == 'nt':  # Windows
        try:
            env = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
            if env: return env
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
            if winreg.QueryValueEx(k, "ProxyEnable")[0]:
                s = winreg.QueryValueEx(k, "ProxyServer")[0]
                return f"http://{s.split('=')[-1].split(';')[0]}"
            winreg.CloseKey(k)
        except: pass
    return None

def cookies_save(ctx):
    """保存cookies"""
    with open(CFG["COOKIE_FILE"], 'w') as f:
        json.dump(ctx.cookies(), f)
    log.info("✅ Cookies已保存")

def cookies_load():
    """加载cookies"""
    if os.path.exists(CFG["COOKIE_FILE"]):
        try:
            with open(CFG["COOKIE_FILE"]) as f:
                return json.load(f)
        except: pass
    return None

# ============================================================
# 浏览器创建和登录
# ============================================================

def find_edge():
    """查找Edge安装路径"""
    paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\Application\msedge.exe"),
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def find_edge_profile():
    """查找Edge用户数据目录"""
    base = os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\User Data")
    if os.path.exists(base):
        return base
    return None

def create_browser(p):
    """创建浏览器上下文"""
    px = proxy()
    if px:
        log.info(f"📡 代理: {px}")
    
    # 优先通过CDP连接本地Edge（无自动化标记，RSI不拦截）
    edge_path = find_edge()
    edge_profile = find_edge_profile()
    
    if edge_path and edge_profile:
        log.info("🌐 启动本地Edge (CDP模式)")
        try:
            debug_port = 9222
            
            # 先强制杀残留Edge进程，确保端口干净
            log.info("   清理残留Edge进程...")
            try:
                result = subprocess.run(['taskkill', '/F', '/IM', 'msedge.exe'],
                               capture_output=True, timeout=5)
                if result.returncode == 0:
                    log.info("   已杀残留Edge，等待端口释放...")
                    time.sleep(3)
                else:
                    log.info("   无残留Edge进程")
            except:
                pass
            
            # 启动Edge并开启远程调试
            log.info("   启动Edge...")
            cmd = [
                edge_path,
                f"--remote-debugging-port={debug_port}",
                f"--user-data-dir={edge_profile}",
                "--no-first-run",
                "--disable-extensions",
            ]
            _edge_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # 等待Edge启动就绪
            import urllib.request
            log.info("   等待CDP端口就绪...")
            for i in range(20):
                time.sleep(1)
                try:
                    resp = urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json/version", timeout=2000)
                    log.info(f"   CDP端口就绪 (第{i+1}秒)")
                    break
                except:
                    if (i + 1) % 5 == 0:
                        log.info(f"   仍在等待CDP... (第{i+1}秒)")
                    pass
            else:
                raise Exception("Edge启动超时(20秒)")
            
            # 通过CDP连接（最多3次尝试）
            browser = None
            for cdp_attempt in range(3):
                try:
                    log.info(f"   CDP连接尝试{cdp_attempt+1}/3...")
                    browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}", timeout=15000)
                    break
                except Exception as cdp_err:
                    log.warning(f"   CDP连接失败(尝试{cdp_attempt+1}/3): {cdp_err}")
                    if cdp_attempt == 2:
                        # 第三次失败：杀Edge重启再连
                        log.info("   杀Edge重启再试...")
                        try:
                            subprocess.run(['taskkill', '/F', '/IM', 'msedge.exe'], capture_output=True, timeout=5)
                        except:
                            pass
                        time.sleep(3)
                        _edge_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        # 等CDP端口就绪
                        for i in range(20):
                            time.sleep(1)
                            try:
                                urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json/version", timeout=2000)
                                log.info(f"   Edge重启后CDP端口就绪 (第{i+1}秒)")
                                break
                            except:
                                pass
                        else:
                            raise Exception("Edge重启后CDP仍不可用")
                        # 最后一次连接
                        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}", timeout=15000)
                    else:
                        time.sleep(1)
            
            if not browser:
                raise Exception("CDP连接3次均失败")
            
            ctx = browser.contexts[0] if browser.contexts else browser.new_context(
                user_agent=CFG["UA"],
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                ignore_https_errors=True
            )
            log.info("✅ Edge已连接")
            # CDP连接后等Edge内部状态稳定，防止frame detached
            time.sleep(1.5)
            return ctx
        except Exception as e:
            log.warning(f"⚠️ Edge CDP连接失败: {e}，回退Chromium")
    
    # 回退：使用Chromium
    log.info("🌐 使用Chromium浏览器")
    browser = p.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-dev-shm-usage'],
        proxy={"server": px} if px else None
    )
    
    ctx = browser.new_context(
        user_agent=CFG["UA"],
        viewport={'width': 1920, 'height': 1080},
        locale='en-US',
        ignore_https_errors=True
    )
    
    ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    
    return ctx

def login(ctx):
    """登录验证，使用已存在的ctx"""
    cookies = cookies_load()
    if cookies:
        try:
            ctx.add_cookies(cookies)
            log.info("✅ Cookies已加载")
            return True
        except: pass
    
    # 使用传入的ctx创建页面，不需要再创建playwright实例
    page = ctx.new_page()
    # 导航可能因Edge初始化未完成而ERR_ABORTED，重试
    target_url = CFG["BROWSE_URL_PREFIX"] + CFG["SEARCH_KEYWORDS"]
    for _nav_attempt in range(3):
        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
            break
        except Exception as e:
            if _nav_attempt < 2:
                log.warning(f"⚠️ 导航失败(重试{_nav_attempt+1}/3): {e}")
                time.sleep(1)
            else:
                raise
    
    btn = page.query_selector('button:has-text("Sign In")')
    if btn and btn.is_visible():
        btn.click()
        log.info("\n⏳ 请在浏览器登录，完成后按 Enter")
        input()
        cookies_save(ctx)
    
    page.close()
    
    return True


# ============================================================
# API模式 V2.0.0
# ============================================================

def run_api_mode(page, dry_run=None, target_time=0):
    """全页面极速模式：加购→购物车→MAX→继续→确认，一路点到底
    dry_run=True 时跳过最后确认付款步骤
    dry_run=None 时自动读取CFG["TEST_MODE"]
    target_time: 目标时间戳，用于计算总耗时
    """
    # 自动读取TEST_MODE配置
    if dry_run is None:
        dry_run = CFG.get("TEST_MODE", False)
    
    # 获取全局GUI实例
    gui = config.get_gui()
    
    t0 = target_time if target_time else time.time()
    client = RSIClient(page)
    
    # 步骤1: 页面加购
    if gui: gui.update_status("加入购物车...", "cart")
    cart_success = client.add_to_cart_via_page()
    if not cart_success:
        if gui: gui.update_step("cart", False)
        return run_page_mode(page)
    if gui: gui.update_step("cart", True)
    
    # 步骤2: 等购物车加载，点MAX
    if gui: gui.update_status("应用信用点...", "credit")
    try:
        page.wait_for_selector('.c-summary', timeout=10000)
    except:
        time.sleep(2)
    
    # 点MAX - 等按钮渲染后点击
    try:
        page.wait_for_selector('button:has-text("MAX")', timeout=5000)
        max_btn = page.locator('button:has-text("MAX")').first
        max_btn.click(force=True, timeout=3000)
        log.info("   ✅ MAX")
    except:
        # 备用JS点击
        try:
            page.evaluate("""() => {
                const btns = [...document.querySelectorAll('button')];
                const m = btns.find(b => (b.innerText||'').trim().toUpperCase() === 'MAX');
                if (m) m.click();
            }""")
            log.info("   ✅ MAX (JS)")
        except:
            log.warning("   ⚠️ MAX未找到")
    if gui: gui.update_step("credit", True)
    time.sleep(0.5)
    
    # 步骤3: 点继续（进入地址步骤）
    if gui: gui.update_status("结算...", "next")
    try:
        page.locator('.m-cartActionBar__button').first.click(force=True, timeout=3000)
    except:
        page.evaluate("""() => {
            const btns = [...document.querySelectorAll('button')];
            const c = btns.find(b => {const t=(b.innerText||'').trim().toLowerCase(); return t==='continue'||t==='继续';});
            if (c) c.click();
        }""")
    log.info("   ✅ 继续")
    time.sleep(1)
    if gui: gui.update_step("next", True)
    
    # 步骤4: 地址步骤 - 再点继续
    if gui: gui.update_status("确认地址...", "address")
    try:
        page.locator('.m-cartActionBar__button').first.click(force=True, timeout=3000)
    except:
        page.evaluate("""() => {
            const btns = [...document.querySelectorAll('button')];
            const c = btns.find(b => {const t=(b.innerText||'').trim().toLowerCase(); return t==='continue'||t==='继续';});
            if (c) c.click();
        }""")
    log.info("   ✅ 地址确认")
    time.sleep(1)
    if gui: gui.update_step("address", True)
    
    # 步骤4.5: 勾选Disclaimer弹窗的agree复选框
    # 直接点击checkbox不检查状态
    try:
        checkbox = page.locator('input[type="checkbox"]').first
        checkbox.click(force=True)
        log.info("   ✅ 勾选agree")
    except:
        try:
            page.evaluate("""() => {
                const cb = document.querySelector('input[type="checkbox"]');
                if (cb) cb.click();
                const label = document.querySelector('.a-checkbox, [class*="checkbox"]');
                if (label) label.click();
            }""")
            log.info("   ✅ JS勾选agree")
        except:
            log.warning("   ⚠️ 未找到agree复选框")
    time.sleep(0.3)
    
    # 步骤4.5: dry_run跳过点 - 勾选checkbox之后、点击I Agree之前
    if dry_run:
        log.info("   ⏸️ 跳过确认付款（测试模式）")
        total = time.time() - t0
        log.info(f"\n📊 测试流程完成，耗时 {total:.2f}秒")
        config.ss(page, "DRY_RUN")
        return True
    
    # 步骤5: 确认付款
    if gui: gui.update_status("确认付款...", "confirm")
    
    # 尝试点击多个可能的确认按钮
    # I AGREE失败时等1秒重勾选再试
    for agree_attempt in range(1, 3):
        clicked = False
        for sel in ['button:has-text("I AGREE")', 'button:has-text("Confirm")', 'button:has-text("Place Order")', 'button:has-text("Complete")', '.m-cartActionBar__button']:
            try:
                btn = page.locator(sel).first
                btn.click(force=True, timeout=3000)
                clicked = True
                break
            except:
                continue
        
        if clicked:
            break
        
        # I AGREE失败时等1秒重勾选
        if agree_attempt < 2:
            log.warning(f"   ⚠️ I AGREE尝试{agree_attempt}失败，等1秒重试...")
            time.sleep(1)
            try:
                checkbox = page.locator('input[type="checkbox"]').first
                checkbox.click(force=True)
                log.info("   ✅ 重新勾选agree")
            except:
                pass
    
    log.info("   ✅ 确认付款")
    
    # 等待页面跳转到确认页（用Playwright等URL变化）
    confirm_keywords = ['success', 'confirm', 'complete', 'thank', 'hangar']
    try:
        page.wait_for_url(f"**/confirm/**", timeout=15000)
        url = page.url.lower()
    except:
        # wait_for_url超时，手动检查当前URL
        url = page.url.lower()
    
    total = time.time() - t0
    
    # 付款结果根据URL判断return True/False
    if any(x in url for x in confirm_keywords):
        log.info(f"\n🎉🎉🎉 好船来啦！不愧是我！流程耗时 {total:.2f}秒 🎉🎉🎉")
        if gui: gui.update_step("confirm", True)
        config.ss(page, "SUCCESS")
        config.notify("🎉 咩咩Kick！成功！", f"耗时{total:.2f}秒")
    else:
        log.warning(f"⚠️ 请人工确认 (流程耗时{total:.2f}秒)")
        if gui: gui.update_step("confirm", False)
        config.ss(page, "CHECK")
    return True


# ============================================================
# 页面模式（备用）
# ============================================================

def js_click(page, selector):
    """JS点击元素"""
    try:
        r = page.evaluate(f"""
            () => {{
                const el = document.querySelector('{selector}');
                if (el) {{ el.click(); return true; }}
                return false;
            }}
        """)
        if r:
            log.info(f"⚡ 点击: {selector[:40]}")
        return r
    except:
        return False

def find_card(page):
    """查找商品卡片"""
    for sel in [".offer-card", ".pledge-card", ".offer-item"]:
        try:
            cards = page.query_selector_all(sel)
            if cards:
                log.info(f"📍 扫描{len(cards)}个卡片...")
                for i, card in enumerate(cards):
                    try:
                        is_wb = card.evaluate("""
                            () => {
                                const t = this.innerText.toLowerCase();
                                return t.includes('warbond') || t.includes('cannot be acquired with store credit');
                            }
                        """)
                        if is_wb:
                            log.info(f"   [{i+1}] ❌ Warbond")
                            continue
                        log.info(f"   [{i+1}] ✅ 可用")
                        return card
                    except:
                        continue
        except:
            continue
    return None

def click_card_btn(page, card):
    """点击卡片按钮"""
    for sel in ["button:has-text('Add to Cart')", "button:has-text('Select')", "button"]:
        try:
            r = card.evaluate(f"""
                () => {{
                    const btn = this.querySelector('{sel}');
                    if (btn) {{ btn.click(); return true; }}
                    return false;
                }}
            """)
            if r:
                return True
        except:
            continue
    try:
        card.click(force=True)
        return True
    except:
        return False

def handle_max(page):
    """点击MAX按钮"""
    for sel in ["button:has-text('MAX')", ".max-btn"]:
        try:
            r = page.evaluate(f"""
                () => {{
                    const btn = document.querySelector('{sel}');
                    if (btn && btn.offsetWidth > 0) {{ btn.click(); return true; }}
                    return false;
                }}
            """)
            if r:
                log.info(f"⚡ MAX: {sel}")
                return True
        except:
            continue
    return False

def run_page_mode(page):
    """纯页面模式"""
    # 获取全局GUI实例
    gui = config.get_gui()
    
    t0 = time.time()
    log.info("📍 [页面模式]")
    
    # 找卡片
    if gui: gui.update_status("查找商品卡片...")
    card = find_card(page)
    if not card:
        config.ss(page, "no_card")
        log.error("❌ 未找到卡片")
        if gui: gui.update_step("cart", False)
        return False
    
    # 点击
    if not click_card_btn(page, card):
        config.ss(page, "click_fail")
        log.error("❌ 点击失败")
        if gui: gui.update_step("cart", False)
        return False
    
    if gui: gui.update_step("cart", True)
    time.sleep(0.1)
    
    # 购物车
    if gui: gui.update_status("进入购物车...")
    page.goto(CFG["CART_URL"], wait_until="domcontentloaded", timeout=5000)
    
    # 结账
    for sel in ["button:has-text('Checkout')"]:
        if js_click(page, sel):
            break
    time.sleep(0.2)
    
    # 信用点
    if gui: gui.update_status("应用信用点...")
    for sel in ["input[value='credits']"]:
        if js_click(page, sel):
            break
    
    handle_max(page)
    time.sleep(0.1)
    
    # 确认
    if gui: gui.update_status("确认订单...")
    for sel in ["button:has-text('Complete Order')", "button:has-text('Place Order')"]:
        if js_click(page, sel):
            break
    
    time.sleep(1.5)
    
    total = time.time() - t0
    url = page.url.lower()
    
    if any(x in url for x in ['success', 'confirm', 'complete', 'thank', 'order', 'hangar']):
        log.info(f"\n🎉🎉🎉 成功！耗时 {total:.2f}秒 🎉🎉🎉")
        if gui: gui.update_step("confirm", True)
        config.ss(page, "PAGE_SUCCESS")
        config.notify("🎉 咩咩Kick！成功！", f"页面模式，耗时{total:.2f}秒")
    else:
        log.warning("⚠️ 请人工确认")
        if gui: gui.update_step("confirm", False)
        config.ss(page, "check")
    
    return True
