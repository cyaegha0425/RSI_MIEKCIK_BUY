#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
咩咩Kick! V3.0.0
主入口模块 - Playwright线程和主循环
"""

import os
import queue
import subprocess
import threading
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

from . import config
from .browser import create_browser, login, run_api_mode, run_page_mode
from .gui_progress import RSIGUI
from .gui_config import _show_clear_cart_dialog
from .api_client import RSIClient
from .calibration import CalibrationScheduler
from .sku_interceptor import SKUInterceptor

# 导入config中的常量
CFG = config.CFG
GUI_TEXT_COLOR = config.GUI_TEXT_COLOR
GUI_BG_DARK = config.GUI_BG_DARK
GUI_BG_COLOR = config.GUI_BG_COLOR
# 延迟获取args，避免PyInstaller导入时触发parse_args
def _get_args():
    return config.get_args()
log = config.log
get_gui = config.get_gui
set_gui = config.set_gui


# ============================================================
# Playwright线程
# ============================================================

def _run_playwright_thread(result_queue):
    """Playwright操作在独立线程中执行，避免与tkinter冲突"""
    try:
        with sync_playwright() as p:
            ctx = create_browser(p)
            page = ctx.new_page()
            
            # Playwright timeout单位是毫秒
            page.set_default_timeout(CFG["TIMEOUT"] * 1000)
            # 登录阶段不屏蔽资源，确保页面正常加载
            page.add_init_script("""
                if ('serviceWorker' in navigator) {
                    navigator.serviceWorker.getRegistrations().then(r => r.forEach(x => x.unregister()));
                }
            """)
            
            try:
                # 登录（不屏蔽资源）
                log.info("\n📍 [1/7] 登录")
                gui = get_gui()
                if gui: gui.update_status("登录验证...", "login")
                login(ctx)
                if gui: gui.update_step("login", True)
                
                # 立即打开商品页面预热
                log.info("\n📍 [2/7] 预热 - 打开页面")
                if gui: gui.update_status("预热加载...", "warmup")
                # 伏击模式预热购物车，正面硬刚预热搜索页
                _warmup_url = CFG["CART_URL"] if CFG.get("AMBUSH_MODE", False) else (CFG["BROWSE_URL_PREFIX"] + CFG["SEARCH_KEYWORDS"])
                for _warmup_attempt in range(3):
                    page.goto(_warmup_url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(2)
                    cur_url = page.url
                    if cur_url and cur_url != "about:blank" and cur_url != "about:blank#":
                        break
                    log.warning(f"⚠️ 预热白屏，重试({_warmup_attempt+1}/3)...")
                log.info("   ✅ 页面已打开，等待抢购时间...")
                if gui: gui.update_step("warmup", True)

                # 清空购物车提醒（预热完成后、校准之前，避免T-0时卡弹窗）
                _clear_cart_event = threading.Event()
                if gui and gui.enabled and not CFG.get("AMBUSH_MODE", False):
                    log.info("   ⏸️ 提醒用户清空购物车...")
                    gui_dialog_thread = threading.Thread(target=_show_clear_cart_dialog, args=(gui, _clear_cart_event), daemon=True)
                    gui_dialog_thread.start()
                    _clear_cart_event.wait()
                    log.info("   ✅ 用户已确认清空购物车，重新加载页面...")
                    for _reload_attempt in range(3):
                        page.goto(CFG["BROWSE_URL_PREFIX"] + CFG["SEARCH_KEYWORDS"], wait_until="domcontentloaded", timeout=15000)
                        time.sleep(1)
                        cur_url = page.url
                        if cur_url and cur_url != "about:blank" and cur_url != "about:blank#":
                            break
                        log.warning(f"⚠️ 重新加载白屏，重试({_reload_attempt+1}/3)...")

                # 预热阶段创建client
                from .api_client import RSIClient
                client = RSIClient(page)
                
                # 时间校准
                log.info("\n📍 [时间校准]")
                if gui: gui.update_status("校准时间...", "calibrate")
                
                # 获取手动偏移（微调值）
                manual_offset = 0.0
                manual_offset_str = CFG.get("MANUAL_TIME_OFFSET", "")
                if manual_offset_str:
                    try:
                        manual_offset = float(manual_offset_str)
                        log.info(f"   手动时间偏移: {manual_offset:+.3f}s")
                    except:
                        log.warning(f"   手动偏移格式错误: {manual_offset_str}")
                
                manual_only = CFG.get("MANUAL_ONLY", False)
                
                if manual_only:
                    # 纯手动模式：跳过自动校准
                    server_offset = manual_offset
                    CFG["SERVER_TIME_OFFSET"] = manual_offset
                    log.info(f"   纯手动模式，偏移: {server_offset:+.3f}s")
                else:
                    # 自动校准 + 手动微调叠加
                    server_offset = client.calibrate_time()
                    CFG["SERVER_TIME_OFFSET"] = server_offset
                    log.info(f"   自动校准偏移: {server_offset:+.3f}s")
                    if manual_offset != 0.0:
                        server_offset += manual_offset
                        CFG["SERVER_TIME_OFFSET"] = server_offset
                        log.info(f"   叠加手动微调: {manual_offset:+.3f}s → 最终: {server_offset:+.3f}s")
                
                if gui: gui.update_step("calibrate", True)
                if gui: gui.update_calibration(server_offset, is_manual=manual_only)
                
                # ===== 伏击模式分支 =====
                if CFG.get("AMBUSH_MODE", False):
                    log.info("\n📍 [伏击模式] 开始执行...")
                    if gui: gui.update_status("伏击模式准备中...", "ambush")
                    
                    # a. 导航到购物车页面
                    log.info("   导航到购物车页面...")
                    if gui: gui.update_status("打开购物车...", "cart")
                    page.goto(CFG["CART_URL"], wait_until="domcontentloaded", timeout=15000)
                    time.sleep(1.5)
                    
                    # 检查购物车是否为空
                    cart_info = client.get_cart_items_from_page()
                    if not cart_info.get('items'):
                        log.error("❌ 购物车为空，请先添加商品！")
                        if gui: gui.show_result(False, "购物车为空，请先添加商品！")
                        result_queue.put(("error", "购物车为空"))
                        ctx.close()
                        return
                    
                    # b. 根据剩余时间决定伏击模式策略
                    time_offset = CFG.get("TIME_OFFSET", 0)
                    target = config.get_target() + time_offset
                    now_ts = time.time()
                    ambush_start = target - 30  # T-30秒开始预装填
                    server_offset = CFG.get("SERVER_TIME_OFFSET", 0)
                    total_remaining = target - now_ts  # 距T-0总剩余时间
                    
                    # 显示取消按钮
                    if gui: gui.show_cancel_button()
                    
                    # ===== 降级策略：剩余时间 < 5秒 =====
                    if total_remaining < 5:
                        log.warning(f"⚠️ 剩余不足5秒，降级为完整API流程")
                        if gui: gui.update_status("降级模式执行...", "ambush")
                        
                        # 等待T-0
                        while time.time() - server_offset < target:
                            if gui and gui.is_cancel_clicked():
                                log.info("⚠️ 用户取消抢购")
                                if gui: gui.close_and_return_to_config()
                                result_queue.put(("cancel", None))
                                return
                            time.sleep(0.01)
                        
                        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        log.info(f"🐑🐑🐑 {now} 降级模式 T-0 开抢！")
                        if gui: gui.update_step("wait", True)
                        
                        # 走完整API流程（跟正面硬刚一样）
                        if gui: gui.update_status("加入购物车...", "cart")
                        cart_success = client.add_to_cart_via_page()
                        if not cart_success:
                            if gui: gui.update_step("cart", False)
                            log.warning("⚠️ 加购失败，降级为页面模式...")
                            success = run_page_mode(page)
                        else:
                            if gui: gui.update_step("cart", True)
                            if gui: gui.update_status("极速结账...", "checkout")
                            success = client.superfast_checkout()
                            if gui: gui.update_step("checkout", success)
                            if not success:
                                log.warning("⚠️ 极速结账失败，降级为页面模式...")
                                success = run_page_mode(page)
                        
                        total = time.time() - target
                        log.info(f"\n📊 总耗时: {total:.2f}秒（从目标时间起算）")
                        
                        if success:
                            if gui: gui.show_result(True, f"总耗时 {total:.2f}秒")
                            config.notify("🎉 咩咩Kick！成功！", f"总耗时{total:.2f}秒")
                        else:
                            if gui: gui.show_result(False, f"总耗时 {total:.2f}秒")
                            config.notify("⚠️ 咩咩Kick！失败", "可能未成功，请检查页面")
                        
                        result_queue.put(("success", success))
                        
                        log.info("\n⏸️ 等待确认关闭...")
                        if gui and gui.enabled:
                            while gui and gui.enabled and not gui.is_result_confirmed():
                                time.sleep(0.5)
                        else:
                            time.sleep(5)
                        
                        ctx.close()
                        return
                    
                    # ===== 正常策略：剩余时间 >= 5秒 =====
                    
                    # 重建校准调度（启动时已做过初始校准，这里规划后续校准点）
                    # 伏击模式校准在预装填等待和T-0等待期间执行
                    scheduler_ambush = CalibrationScheduler(client, target, server_offset=server_offset)
                    
                    # ===== 降级策略：5秒 <= 剩余时间 < 30秒 =====
                    if total_remaining < 30:
                        log.warning(f"⚠️ 剩余不足30秒，立刻执行预装填")
                        if gui: gui.update_status("立刻预装填...", "ambush")
                        
                        # 立刻执行预装填（不等T-30）
                        ambush_ready = client.superfast_ambush()
                        if not ambush_ready:
                            log.error("❌ 预装填失败")
                            if gui: gui.show_result(False, "预装填失败")
                            result_queue.put(("error", "预装填失败"))
                            ctx.close()
                            return
                        if gui: gui.update_step("ambush", True)
                        
                        # 等待T-0
                        log.info("   等待 T-0 卡点...")
                        if gui: gui.update_status("等待T-0卡点...", "wait")
                        
                        while time.time() - server_offset < target:
                            if gui and gui.is_cancel_clicked():
                                log.info("⚠️ 用户取消抢购")
                                if gui: gui.close_and_return_to_config()
                                result_queue.put(("cancel", None))
                                return
                            time.sleep(0.01)
                        
                        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        log.info(f"🐑🐑🐑 {now} 伏击模式 T-0 开抢！")
                        if gui: gui.update_step("wait", True)
                        
                        if gui: gui.update_status("T-0 执行验证...", "checkout")
                        success = client.ambush_validate()
                        if gui: gui.update_step("checkout", success)
                        
                        total = time.time() - target
                        log.info(f"\n📊 总耗时: {total:.2f}秒（从目标时间起算）")
                        
                        if success:
                            if gui: gui.show_result(True, f"总耗时 {total:.2f}秒")
                            config.notify("🎉 伏击成功！", f"总耗时{total:.2f}秒")
                        else:
                            if gui: gui.show_result(False, f"总耗时 {total:.2f}秒")
                            config.notify("⚠️ 伏击失败", "请检查页面")
                        
                        result_queue.put(("success", success))
                        
                        log.info("\n⏸️ 等待确认关闭...")
                        if gui and gui.enabled:
                            while gui and gui.enabled and not gui.is_result_confirmed():
                                time.sleep(0.5)
                        else:
                            time.sleep(5)
                        
                        ctx.close()
                        return
                    
                    # ===== 正常策略：剩余时间 >= 30秒 =====
                    
                    if gui: gui.update_status("等待预装填时间...", "wait")
                    
                    # 等待直到 T-30（动态校准：到点就校准，过了就跳过）
                    while time.time() - server_offset < ambush_start:
                        if gui and gui.is_cancel_clicked():
                            log.info("⚠️ 用户取消抢购")
                            if gui: gui.close_and_return_to_config()
                            result_queue.put(("cancel", None))
                            ctx.close()
                            return
                        
                        # 执行到期校准
                        server_offset = scheduler_ambush.check_and_calibrate()
                        
                        time.sleep(0.01)
                    
                    # c. T-30s 执行预装填
                    log.info("📍 [伏击模式] T-30s 开始预装填...")
                    if gui: gui.update_status("T-30s 预装填...", "ambush")
                    
                    ambush_ready = client.superfast_ambush()
                    if not ambush_ready:
                        log.error("❌ 预装填失败")
                        if gui: gui.show_result(False, "预装填失败")
                        result_queue.put(("error", "预装填失败"))
                        ctx.close()
                        return
                    
                    if gui: gui.update_step("ambush", True)
                    
                    # d. 等待直到 T-0秒
                    log.info("   等待 T-0 卡点...")
                    if gui: gui.update_status("等待T-0卡点...", "wait")
                    
                    while time.time() - server_offset < target:
                        if gui and gui.is_cancel_clicked():
                            log.info("⚠️ 用户取消抢购")
                            if gui: gui.close_and_return_to_config()
                            result_queue.put(("cancel", None))
                            ctx.close()
                            return
                        time.sleep(0.01)
                    
                    # e. T-0s 执行最终验证
                    now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    log.info(f"🐑🐑🐑 {now} 伏击模式 T-0 开抢！")
                    if gui: gui.update_step("wait", True)
                    
                    if gui: gui.update_status("T-0 执行验证...", "checkout")
                    success = client.ambush_validate()
                    if gui: gui.update_step("checkout", success)
                    
                    total = time.time() - target
                    log.info(f"\n📊 总耗时: {total:.2f}秒（从目标时间起算）")
                    
                    if success:
                        if gui: gui.show_result(True, f"总耗时 {total:.2f}秒")
                        config.notify("🎉 伏击成功！", f"总耗时{total:.2f}秒")
                    else:
                        if gui: gui.show_result(False, f"总耗时 {total:.2f}秒")
                        config.notify("⚠️ 伏击失败", "请检查页面")
                    
                    result_queue.put(("success", success))
                    
                    # 等GUI结果弹窗被用户确认后关闭
                    log.info("\n⏸️ 等待确认关闭...")
                    if gui and gui.enabled:
                        while gui and gui.enabled and not gui.is_result_confirmed():
                            time.sleep(0.5)
                    else:
                        time.sleep(5)
                    
                    ctx.close()
                    return
                # ===== V3.0.0 正面硬刚模式 - 全API抢购架构 =====
                
                # 获取输入模式
                input_mode = CFG.get("INPUT_MODE", "intercept")
                sku_id = CFG.get("SKU_ID", "")
                keywords = CFG.get("SEARCH_KEYWORDS", "")
                exclude_keywords = CFG.get("EXCLUDE_KEYWORDS", "")
                
                log.info(f"📍 [V3.0.0 正面硬刚] 输入模式={input_mode}, skuId={sku_id or '无'}, 关键词={keywords or '无'}")
                
                time_offset = CFG.get("TIME_OFFSET", 0)
                if time_offset:
                    log.info(f"   手动时间偏移: {time_offset}s")
                
                target = config.get_target() + time_offset
                # 复用启动时的调度器（已含初始校准）
                scheduler_direct = CalibrationScheduler(client, target, server_offset=server_offset)
                
                if gui: gui.update_status("等待抢购时间...", "wait")
                if gui: gui.show_cancel_button()
                
                # ===== 预热阶段完成后，注册SKU拦截器 =====
                interceptor = None
                if input_mode in ("intercept",):
                    interceptor = SKUInterceptor(page, keywords, exclude_keywords)
                    log.info("   📍 SKU拦截器已注册，等待GraphQL响应...")
                
                # ===== 按模式分两条路径 =====
                cart_success = False
                current_sku_id = sku_id
                
                _cancelled = False
                
                if input_mode == "sku":
                    # ===== SKU ID直购：T-10开始API加购轮询 =====
                    T_MINUS_10 = target - 10
                    
                    # 等待T-10
                    while time.time() - server_offset < T_MINUS_10:
                        if gui and gui.is_cancel_clicked():
                            log.info("⚠️ 用户取消抢购")
                            if gui: gui.close_and_return_to_config()
                            result_queue.put(("cancel", None))
                            return
                        server_offset = scheduler_direct.check_and_calibrate()
                        time.sleep(0.01)
                    
                    log.info(f"   ⏰ T-10s 到达，SKU直购模式开始API加购轮询...")
                    if gui: gui.update_status(f"API加购轮询 skuId={current_sku_id}...", "cart")
                    
                    # API加购轮询 T-10 ~ T+5
                    while time.time() - server_offset < target + 5:
                        if gui and gui.is_cancel_clicked():
                            log.info("⚠️ 用户取消抢购")
                            _cancelled = True
                            break
                        
                        success, error_code = client.api_add_to_cart(current_sku_id)
                        
                        if success:
                            log.info("   ✅ API加购成功!")
                            cart_success = True
                            break
                        
                        if error_code == "OutOfStock":
                            pass  # 静默继续
                        elif error_code == "HTTP429":
                            log.warning("   ⚠️ HTTP 429 (限流)，sleep 3秒...")
                            time.sleep(3)
                            continue
                        elif error_code == "HTTP500":
                            pass  # 静默继续
                        else:
                            log.warning(f"   ⚠️ 加购失败: {error_code}")
                        
                        time.sleep(0.5)
                
                else:
                    # ===== 刷新拦截：等到T-0才刷新拦截 =====
                    # 等待T-0
                    while time.time() - server_offset < target:
                        if gui and gui.is_cancel_clicked():
                            log.info("⚠️ 用户取消抢购")
                            if gui: gui.close_and_return_to_config()
                            result_queue.put(("cancel", None))
                            return
                        server_offset = scheduler_direct.check_and_calibrate()
                        time.sleep(0.01)
                    
                    log.info(f"   ⏰ T-0 到达，刷新拦截模式！")
                    if gui: gui.update_status("T-0！刷新页面...", "cart")
                    
                    # 1. 刷新页面
                    ts = time.time()
                    try:
                        page.reload(wait_until="domcontentloaded", timeout=10000)
                    except Exception as e:
                        log.warning(f"   ⚠️ 刷新异常: {e}，尝试重新打开")
                        page.goto(CFG["BROWSE_URL_PREFIX"] + keywords, wait_until="domcontentloaded", timeout=15000)
                    
                    log.info(f"   ⚡ 页面刷新: {(time.time()-ts)*1000:.0f}ms")
                    
                    # 重置拦截器计时起点
                    if interceptor:
                        interceptor.reset_start_time()
                    
                    # 2. 轮询等卡片DOM渲染(最多5秒)
                    current_sku_id = None
                    for fiber_attempt in range(10):
                        if gui and gui.is_cancel_clicked():
                            log.info("⚠️ 用户取消抢购")
                            _cancelled = True
                            break
                        
                        # 先从卡片fiber提取skuId
                        current_sku_id = client.get_sku_id_from_cards(keywords, CFG.get("EXCLUDE_KEYWORDS", ""))
                        if current_sku_id:
                            break
                        
                        # fiber没拿到，也检查拦截器（listing可能已到）
                        if interceptor:
                            interceptor_sku = interceptor.get_sku_id()
                            if interceptor_sku:
                                current_sku_id = interceptor_sku
                                log.info(f"   🎯 拦截器补充拿到skuId: {current_sku_id}")
                                # 同时保存拦截器拿到的价格
                                interceptor_price = interceptor.get_price()
                                if interceptor_price > 0:
                                    CFG["_INTERCEPTOR_PRICE"] = interceptor_price
                                    log.info(f"   💰 拦截器价格: ${interceptor_price}")
                                break
                        
                        time.sleep(0.5)
                    
                    # 3. 拿到skuId → API加购 → 付款
                    if current_sku_id:
                        log.info(f"   🎯 skuId: {current_sku_id}，API加购！")
                        if gui: gui.update_status(f"skuId={current_sku_id}，API加购...", "cart")
                        
                        # 保存skuId到config供下次SKU ID模式使用
                        CFG["LAST_SKU_ID"] = current_sku_id
                        log.info(f"   💾 已保存skuId={current_sku_id}")
                        # 自动保存到收藏夹(用拦截器的真实商品名+价格)
                        try:
                            from .sku_bookmarks import add_bookmark
                            bm_name = interceptor.get_matched_name() if interceptor else (keywords.strip() or "Unknown")
                            bm_price = interceptor.get_price() if interceptor else float(CFG.get("ITEM_PRICE", 0) or 0)
                            if not bm_price:
                                bm_price = float(CFG.get("ITEM_PRICE", 0) or 0)
                            add_bookmark(bm_name or "Unknown", current_sku_id, bm_price)
                        except: pass
                        
                        success, error_code = client.api_add_to_cart(current_sku_id)
                        if success:
                            log.info("   ✅ API加购成功!")
                            cart_success = True
                        else:
                            log.warning(f"   ⚠️ API加购失败: {error_code}")
                    
                    # 4. API加购失败，继续轮询到T+5
                    if not _cancelled and not cart_success:
                        # 如果还没skuId，继续从拦截器/卡片获取
                        while time.time() - server_offset < target + 5:
                            if gui and gui.is_cancel_clicked():
                                log.info("⚠️ 用户取消抢购")
                                _cancelled = True
                                break
                            
                            if not current_sku_id:
                                # 优先从卡片fiber拿
                                current_sku_id = client.get_sku_id_from_cards(keywords, CFG.get("EXCLUDE_KEYWORDS", ""))
                                if not current_sku_id and interceptor:
                                    current_sku_id = interceptor.get_sku_id()
                            
                            if current_sku_id:
                                success, error_code = client.api_add_to_cart(current_sku_id)
                                if success:
                                    log.info("   ✅ API加购成功!")
                                    cart_success = True
                                    CFG["LAST_SKU_ID"] = current_sku_id
                                    # 自动保存到收藏夹
                                    try:
                                        from .sku_bookmarks import add_bookmark
                                        add_bookmark(keywords.strip() or "Unknown", current_sku_id, float(CFG.get("ITEM_PRICE", 0) or 0))
                                    except: pass
                                    break
                                if error_code == "HTTP429":
                                    log.warning("   ⚠️ HTTP 429 (限流)，sleep 3秒...")
                                    time.sleep(3)
                                    continue
                            
                            time.sleep(0.5)
                
                # ===== T+5s还没抢到，回退DOM加购 =====
                if _cancelled:
                    log.info("   用户已取消，跳过DOM兜底")
                elif not cart_success:
                    log.warning("   ⚠️ API加购失败，回退DOM加购...")
                    if gui: gui.update_status("回退DOM加购...", "cart")
                    
                    # 先扫描当前页面（卡片可能已经渲染好了，不需要reload）
                    cart_success = client.add_to_cart_via_page()
                    
                    if not cart_success:
                        # 当前页面没加购成功，再reload
                        for refresh_attempt in range(2):
                            log.info(f"   📍 第{refresh_attempt+1}次DOM刷新...")
                            ts = time.time()
                            try:
                                page.reload(wait_until="domcontentloaded", timeout=10000)
                            except Exception as e:
                                log.warning(f"   ⚠️ 刷新异常: {e}")
                                page.goto(CFG["BROWSE_URL_PREFIX"] + keywords, wait_until="domcontentloaded", timeout=15000)
                            log.info(f"   ⚡ DOM刷新: {(time.time()-ts)*1000:.0f}ms")
                            
                            # 轮询DOM
                            for poll_attempt in range(8):
                                if gui and gui.is_cancel_clicked():
                                    _cancelled = True
                                    break
                                cart_success = client.add_to_cart_via_page()
                                if cart_success:
                                    break
                                time.sleep(0.5)
                            
                            if cart_success or _cancelled:
                                break
                
                # 记录T-0时间
                now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                log.info(f"🐑🐑🐑 {now} 开抢！ (加购结果: {'成功' if cart_success else '失败'})")
                if gui: gui.update_step("wait", True)
                
                # 执行结账
                log.info("\n📍 [3/5] 执行结账")
                
                if CFG["MODE"] == "api":
                    if cart_success:
                        if gui: gui.update_step("cart", True)
                        # API极速付款
                        if gui: gui.update_status("极速结账...", "checkout")
                        success = client.superfast_checkout()
                        if gui: gui.update_step("checkout", success)
                        if not success:
                            log.warning("⚠️ 极速结账失败，降级为页面模式...")
                            success = run_page_mode(page)
                    else:
                        # 刷新阶段没加购成功，再试一次
                        if gui: gui.update_status("加入购物车...", "cart")
                        cart_success = client.add_to_cart_via_page()
                        if not cart_success:
                            if gui: gui.update_step("cart", False)
                            log.warning("⚠️ 加购失败，降级为页面模式...")
                            success = run_page_mode(page)
                        else:
                            if gui: gui.update_step("cart", True)
                            if gui: gui.update_status("极速结账...", "checkout")
                            success = client.superfast_checkout()
                            if gui: gui.update_step("checkout", success)
                            if not success:
                                log.warning("⚠️ 极速结账失败，降级为页面模式...")
                                success = run_page_mode(page)
                else:
                    success = run_page_mode(page)

                total = time.time() - target
                log.info(f"\n📊 总耗时: {total:.2f}秒（从目标时间起算）")
                
                # 显示结果
                if success:
                    if gui: gui.show_result(True, f"总耗时 {total:.2f}秒")
                    config.notify("🎉 咩咩Kick！成功！", f"总耗时{total:.2f}秒")
                    # 成功后跳转机库页面确认
                    try: page.goto("https://robertsspaceindustries.com/en/account/pledges")
                    except: pass
                else:
                    if gui: gui.show_result(False, f"请检查页面")
                    config.notify("⚠️ 咩咩Kick！失败", "可能未成功，请检查页面")
                
                result_queue.put(("success", success))
                
                # 等GUI结果弹窗被用户确认后关闭（点确定或X）
                log.info("\n⏸️ 等待确认关闭...")
                if gui and gui.enabled:
                    while gui and gui.enabled and not gui.is_result_confirmed():
                        time.sleep(0.5)
                else:
                    time.sleep(5)
                
            except KeyboardInterrupt:
                log.info("\n⚠️ 用户中断")
                if gui: gui.show_result(False, "用户中断")
                result_queue.put(("interrupt", None))
            except Exception as e:
                # 区分取消和其他错误
                if "取消抢购" in str(e):
                    log.info("⚠️ 用户取消抢购")
                    result_queue.put(("cancel", None))
                else:
                    log.error(f"\n❌ 异常: {e}")
                    import traceback; traceback.print_exc()
                    try: config.ss(page, "error")
                    except: pass
                    if gui: gui.show_result(False, str(e))
                    result_queue.put(("error", str(e)))
            finally:
                # 不关闭浏览器，保留页面供用户手动操作
                # 用户可自行关闭Edge，下次启动前build.bat会自动kill
                pass
                # 不在Playwright线程里destroy GUI，让GUI在主线程自行关闭
                
    except Exception as e:
        log.error(f"\n❌ Playwright线程异常: {e}")
        import traceback; traceback.print_exc()
        result_queue.put(("error", str(e)))


# ============================================================
# 配置对话框（从gui_config导入）
# ============================================================

def _show_config_dialog():
    """显示配置窗口，返回是否继续（代理到gui_config）"""
    from .gui_config import _show_config_dialog as _config_dialog
    return _config_dialog()


# ============================================================
# 主入口函数
# ============================================================

def run():
    """主入口，改成while循环支持多次执行"""
    
    while True:
        # 显示配置窗口
        if not _show_config_dialog():
            return  # 用户取消
        
        # Edge进程清理已移到create_browser()中，此处不再重复taskkill
        # 但保留短暂等待确保上次运行完全退出
        time.sleep(0.5)
        
        log.info("=" * 50)
        log.info("咩咩蹄到好船来 V3.0.0 咩咩KICK！")
        log.info(f"⏰ 目标: {CFG['TARGET_TIME']}")
        ambush_mode = CFG.get("AMBUSH_MODE", False)
        log.info(f"🎮 模式: {'伏击模式' if ambush_mode else '正面硬刚'} ({'页面加购+API付款' if CFG['MODE'] == 'api' else '页面模式'})")
        log.info(f"🖥️ GUI: {'启用' if not _get_args().no_gui else '禁用'}")
        log.info("=" * 50)
        
        # 创建线程间通信队列
        result_queue = queue.Queue()
        
        # 初始化GUI
        _gui = RSIGUI(CFG["TARGET_TIME"], mode_label="[伏击模式]" if CFG.get("AMBUSH_MODE", False) else "[正面硬刚]")
        set_gui(_gui)
        
        # 在独立线程中运行Playwright操作
        pw_thread = threading.Thread(target=_run_playwright_thread, args=(result_queue,), daemon=True)
        pw_thread.start()
        
        # 主线程运行GUI mainloop（tkinter要求mainloop在主线程）
        # mainloop会在_quit_requested时退出，或者窗口被关闭时退出
        if _gui.enabled:
            _gui.run_mainloop()
        
        # mainloop退出后，等待Playwright线程完成
        pw_thread.join(timeout=10)
        
        # 清理GUI窗口
        if _gui and _gui.enabled:
            try:
                if _gui.root:
                    _gui.root.destroy()
            except:
                pass
        set_gui(None)
        
        # 检查是否需要继续循环
        try:
            result = result_queue.get_nowait()
            log.info(f"Playwright线程返回: {result}")
            if result[0] in ("cancel", "success", "error", "interrupt"):
                continue  # 重新显示配置界面
        except queue.Empty:
            # 检查是否是用户点击了cancel
            if _gui and _gui.is_cancel_clicked():
                log.info("用户取消，回到配置界面")
                continue
            log.info("未获取到线程返回结果")
            break
    
    # 强制退出，确保不留后台进程
    os._exit(0)


def test():
    """测试模式"""
    log.info("=" * 50)
    log.info("🧪 测试模式")
    log.info("=" * 50)
    
    with sync_playwright() as p:
        ctx = create_browser(p)
        page = ctx.new_page()
        page.set_default_timeout(10000)
        
        try:
            login(ctx)
            
            log.info(f"\n📍 打开页面")
            page.goto(CFG["BROWSE_URL_PREFIX"] + CFG["SEARCH_KEYWORDS"], wait_until="domcontentloaded", timeout=20000)
            log.info(f"   标题: {page.title()}")
            time.sleep(2)
            
            # 直接跑完整流程（含付款）
            log.info("\n📍 开始完整购买流程（含付款）")
            run_api_mode(page)
            
            config.ss(page, "test")
            log.info("\n✅ 完成")
            input("\n按 Enter 退出")
            
        except Exception as e:
            log.error(f"❌ {e}")
            import traceback; traceback.print_exc()
        finally:
            ctx.close()


def help():
    """显示帮助信息"""
    print("""
╔══════════════════════════════════════════════════════════╗
║   咩咩蹄到好船来 V3.0.0 咩咩KICK！ - 抢光CIG的机库   ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  用法:                                                  ║
║    python RSI_MIEBUY_V1.py                  # 运行(默认GUI)  ║
║    python RSI_MIEBUY_V1.py --no-gui         # 运行(无GUI)    ║
║    python RSI_MIEBUY_V1.py --test           # 测试           ║
║                                                          ║
║  GUI功能:                                               ║
║    - 实时显示抢购进度和步骤状态                         ║
║    - 倒计时显示（窗口置顶）                             ║
║    - 抢购成功/失败弹窗提醒                              ║
║    - 使用 --no-gui 禁用GUI                             ║
║                                                          ║
║  首次:                                                  ║
║    pip install playwright                                  ║
║    python -m playwright install chromium                   ║
║    python RSI_MIEBUY_V1.py --test                    ║
║                                                          ║
║  V2.0.0 新流程:                                           ║
║    1. 页面点击加购 → 绕过SKU提取问题                    ║
║    2. API应用信用点                                     ║
║    3. API进入结算                                       ║
║    4. API绑定地址                                       ║
║    5. API确认付款                                       ║
║                                                          ║
║  目标: 全程 1-2秒                                       ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
""")
