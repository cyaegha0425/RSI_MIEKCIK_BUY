#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
咩咩Kick! V3.0.0
RSI GraphQL API 客户端模块
"""

import json
import re
import time
from typing import Dict, Optional

from . import config

# 导入config中的常量
CFG = config.CFG
QUERIES = config.QUERIES
log = config.log


class RSIClient:
    """RSI GraphQL API 客户端 - V2.0.0 页面加购+API付款模式"""
    
    def __init__(self, page):
        self.page = page
        self.url = CFG["GRAPHQL_URL"]
        self.billing_address_id = None  # 默认地址ID，可从API获取或hardcode
        self.cart_data = {}
        self.cart_total = 0.0  # 购物车总额
    
    def gql(self, operation_name: str, variables: Dict = None, return_headers: bool = False) -> Dict:
        """执行GraphQL请求（使用urllib，从浏览器取cookies）
        
        Args:
            operation_name: GraphQL操作名
            variables: 变量字典
            return_headers: 是否返回响应头（用于时间校准）
        Returns:
            如果return_headers=True，返回 (result_dict, headers_dict) 元组
            否则返回 result_dict
        """
        import urllib.request
        # 检查是否取消
        gui = config.get_gui()
        if gui and gui.is_cancel_clicked():
            raise Exception("用户取消抢购")

        
        query = QUERIES.get(operation_name, "")
        if not query:
            log.error(f"❌ 未找到query: {operation_name}")
            return {}
        
        payload = [{
            "operationName": operation_name,
            "variables": variables or {},
            "query": query.strip()
        }]
        
        try:
            # 从浏览器上下文获取cookies
            cookie_str = ""
            try:
                browser_cookies = self.page.context.cookies()
                cookie_parts = []
                for c in browser_cookies:
                    if c.get('domain', '').endswith('robertsspaceindustries.com'):
                        cookie_parts.append(f"{c['name']}={c['value']}")
                cookie_str = "; ".join(cookie_parts)
            except Exception as e:
                log.warning(f"   获取浏览器cookies异常: {e}")
            
            # 从页面获取CSRF token
            csrf_token = ""
            try:
                csrf_token = self.page.evaluate("""
                    () => {
                        const meta = document.querySelector('meta[name="csrf-token"]');
                        return meta ? meta.getAttribute('content') : '';
                    }
                """)
            except:
                pass
            
            req = urllib.request.Request(
                self.url,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Accept': '*/*',
                    'accept-language': 'en',
                    'Cookie': cookie_str,
                    'Referer': self.page.url,
                }
            )
            if csrf_token:
                req.add_header('x-csrf-token', csrf_token)
            
            log.info(f"   📤 发送: op={operation_name}, cookies={len(cookie_str.split('; ')) if cookie_str else 0}个, csrf={'有' if csrf_token else '无'}")
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                headers = dict(resp.headers)
            
            
            # RSI GraphQL响应可能是批量数组格式
            if isinstance(result, list):
                for item in result:
                    if isinstance(item, dict) and item.get('data'):
                        final_result = item
                        break
                else:
                    final_result = result[0] if result else {}
            else:
                final_result = result or {}
            
            if return_headers:
                return final_result, headers
            return final_result
        except urllib.error.HTTPError as e:
            log.error(f"❌ GraphQL请求HTTP错误: {e.code} {e.reason}")
            return {"__http_status__": e.code}
        except Exception as e:
            log.error(f"❌ GraphQL请求失败: {e}")
            return {}

    def calibrate_time(self, samples: int = 10, interval: float = 0.5, deadline: float = 0) -> float:
        """校准本地与RSI服务器的时间偏移（1秒密度窗口算法）
        
        通过发送多次轻量API请求，从响应头获取RSI服务器时间
        使用1秒密度窗口 + 顺序统计量偏置修正，消除Date头秒级精度的随机误差
        
        算法：
        1. 多次采样，记录 (偏移值, RTT)
        2. 过滤RTT异常的样本（>中位数2倍）
        3. 1秒滑动窗口找包含最多点的区间（真实偏移必在此区间内）
        4. 取窗口内最低25%样本，减去Uniform顺序统计量偏置
        
        Args:
            samples: 采样次数
            interval: 采样间隔（秒）
            deadline: 截止时间戳（UTC），校准不得晚于此时间，0表示无限制
        
        Returns:
            时间偏移（秒），正值=本地比服务器慢，失败返回0.0
        """
        log.info(f"📍 [时间校准] 采样{samples}次, 间隔{interval}秒")
        
        try:
            import urllib.request
            from email.utils import parsedate_to_datetime
            import statistics
            
            # 获取cookies
            cookie_str = ""
            try:
                browser_cookies = self.page.context.cookies()
                cookie_parts = []
                for c in browser_cookies:
                    if c.get('domain', '').endswith('robertsspaceindustries.com'):
                        cookie_parts.append(f"{c['name']}={c['value']}")
                cookie_str = "; ".join(cookie_parts)
            except Exception as e:
                log.warning(f"   获取cookies异常: {e}")
            
            # 采样（用GraphQL请求获取RSI后端真实Date头，不用HEAD/CDN缓存）
            raw_samples = []  # (offset, rtt)
            for sample_i in range(samples):
                try:
                    req = urllib.request.Request(
                        self.url,
                        data=json.dumps([{
                            "operationName": "MiniCartWidgetInitializationQuery",
                            "variables": {"storeFront": "pledge"},
                            "query": QUERIES.get("MiniCartWidgetInitializationQuery", "").strip()
                        }]).encode('utf-8'),
                        headers={
                            'Content-Type': 'application/json',
                            'Accept': '*/*',
                            'accept-language': 'en',
                            'Cookie': cookie_str,
                            'Referer': self.page.url,
                        }
                    )
                    
                    t1 = time.time()
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        t2 = time.time()
                        date_str = resp.headers.get('Date', '')
                        if not date_str:
                            continue
                        
                        server_dt = parsedate_to_datetime(date_str)
                        server_ts = server_dt.timestamp()
                        mid = (t1 + t2) / 2.0
                        rtt = t2 - t1
                        d = mid - server_ts
                        raw_samples.append((d, rtt))
                        log.info(f"   采样{sample_i+1}: d={d:+.3f}s, rtt={rtt*1000:.0f}ms")
                        
                except:
                    continue
                
                # 接近deadline时提前结束采样
                if deadline > 0 and time.time() >= deadline - 2:
                    log.info(f"   接近截止时间，采样{sample_i+1}次后提前结束")
                    break
                
                if sample_i < samples - 1:
                    time.sleep(interval)
            
            if len(raw_samples) < 3:
                log.warning(f"⚠️ 有效采样仅{len(raw_samples)}次，不足3次")
                return 0.0
            
            # RTT过滤：剔除RTT > 中位数2倍的样本
            rtts = [s[1] for s in raw_samples]
            rtt_median = statistics.median(rtts)
            filtered = [(d, rtt) for d, rtt in raw_samples if rtt <= rtt_median * 2]
            if len(filtered) < 3:
                filtered = raw_samples  # 过滤太多就全用
            
            d_values = sorted([d for d, _ in filtered])
            n = len(d_values)
            
            log.info(f"   RTT过滤: {len(raw_samples)}→{n}个 (中位RTT={rtt_median*1000:.0f}ms)")
            
            # 1秒密度窗口：找包含最多点的长度为1.0的区间
            best_left = d_values[0]
            best_count = 1
            j = 0
            for i in range(n):
                while j < n and d_values[j] - d_values[i] <= 1.0:
                    j += 1
                count = j - i
                if count > best_count:
                    best_count = count
                    best_left = d_values[i]
            
            # 窗口内的点
            window = [d for d in d_values if best_left <= d <= best_left + 1.0]
            window.sort()
            m = len(window)
            
            log.info(f"   密度窗口: [{best_left:+.3f}, {best_left+1.0:+.3f}), {m}个点")
            
            # 顺序统计量偏置修正
            # 取窗口内最低的25%（至少2个）
            k = max(2, m // 4)
            low_k = window[:k]
            mean_low = statistics.mean(low_k)
            # Uniform(0,1)前k个顺序统计量的均值偏置 = (k+1)/(2*(m+1))
            bias = (k + 1) / (2.0 * (m + 1))
            delta = mean_low - bias
            
            # 误差估计
            uniform_err = 1.0 / (m + 1)
            noise_err = statistics.stdev(low_k) / (k ** 0.5) if k >= 2 else 0.05
            err = (uniform_err ** 2 + noise_err ** 2) ** 0.5
            
            log.info(f"🕐 校准结果: Δ={delta:+.3f}s ±{err*1000:.0f}ms (偏置修正-{bias:.3f}s, {m}/{n}窗口内)")
            
            return delta
                
        except Exception as e:
            log.warning(f"⚠️ 时间校准失败: {e}，使用默认偏移0")
            return 0.0
    
    def get_billing_address(self) -> Optional[str]:
        """获取账单地址ID（照抄真实API返回结构）"""
        log.info("📍 [获取地址]")
        
        result = self.gql("AddressBookQuery")
        
        # 真实API返回: data.store.addressBook 是直接数组
        address_book = result.get('data', {}).get('store', {}).get('addressBook', [])
        
        if address_book:
            # 优先默认账单地址
            for addr in address_book:
                if addr.get('defaultBilling'):
                    addr_id = str(addr['id'])
                    addr_str = f"{addr.get('addressLine', '')}, {addr.get('city', '')}"
                    log.info(f"   默认账单地址: {addr_id} ({addr_str})")
                    self.billing_address_id = addr_id
                    return addr_id
            
            # 没有默认就取第一个
            addr = address_book[0]
            addr_id = str(addr['id'])
            addr_str = f"{addr.get('addressLine', '')}, {addr.get('city', '')}"
            log.info(f"   第一地址: {addr_id} ({addr_str})")
            self.billing_address_id = addr_id
            return addr_id
        
        log.warning("⚠️ 未找到地址（RSI使用默认地址，无需手动绑定）")
        return None
    
    def api_add_to_cart(self, sku_id: str) -> tuple:
        """API加购方法 - V3.0.0 全API抢购架构核心
        
        Args:
            sku_id: 商品SKU ID
            
        Returns:
            (success, error_code)
            - success=True: 加购成功
            - error_code: "OutOfStock" / "HTTP429" / "HTTP500" / "Other"
        """
        log.info(f"📍 [API加购] skuId={sku_id}")
        
        variables = {
            "query": [{"skuId": sku_id}],
            "storeFront": "pledge"
        }
        
        try:
            result = self.gql("AddCartMultiItemMutation", variables)
            
            # 检查HTTP层错误（gql返回__http_status__表示HTTPError）
            http_status = result.get('__http_status__')
            if http_status:
                if http_status == 429:
                    return (False, "HTTP429")
                elif http_status == 500:
                    return (False, "HTTP500")
                return (False, "Other")
            
            if result.get('errors'):
                errors = result['errors']
                log.warning(f"   ⚠️ 加购错误: {errors}")
                # 解析错误类型
                error_str = str(errors)
                if 'TyOutOfStockException' in error_str or 'out of stock' in error_str.lower() or 'OutOfStock' in error_str:
                    return (False, "OutOfStock")
                elif '429' in error_str:
                    return (False, "HTTP429")
                elif '500' in error_str or 'Internal Server Error' in error_str:
                    return (False, "HTTP500")
                return (False, "Other")
            
            # 检查响应结构
            data = result.get('data', {})
            store = data.get('store', {})
            cart = store.get('cart', {})
            mutations = cart.get('mutations', {})
            add_many = mutations.get('addMany', {})
            
            count = add_many.get('count', 0)
            typename = add_many.get('__typename', '')
            
            if count and int(count) > 0:
                log.info(f"   ✅ 加购成功! count={count}, type={typename}")
                return (True, None)
            
            # 检查其他成功标识
            if typename == 'CartLineItem' or typename == 'AddManyResult':
                log.info(f"   ✅ 加购成功!")
                return (True, None)
            
            # 无明确错误但也未成功
            log.warning(f"   ⚠️ 加购结果未知: {add_many}")
            return (True, None)
            
        except Exception as e:
            error_str = str(e)
            log.error(f"   ❌ 加购异常: {e}")
            
            # 解析异常类型
            if '429' in error_str or 'Too Many Requests' in error_str:
                return (False, "HTTP429")
            elif '500' in error_str or 'Internal Server Error' in error_str:
                return (False, "HTTP500")
            elif 'TyOutOfStockException' in error_str or 'out of stock' in error_str.lower():
                return (False, "OutOfStock")
            
            return (False, "Other")


    def get_cart_total(self) -> float:
        """获取购物车总额（优先DOM精确读取，API备选）
        
        购物车DOM结构（从真实页面确认）：
        - 右侧 Order Summary: .c-summary → .m-summaryLineItem[label=Total] → .a-priceUnit__amount
        - 底部 sticky bar: .m-cartActionBar → .m-cartActionBar__price → .a-priceUnit__amount
        - 商品行: .c-cartLineItem → .c-cartLineItem__price → .a-priceUnit__amount
        """
        log.info("📍 [获取购物车总额]")
        
        # 确保购物车页面DOM已渲染
        try:
            self.page.wait_for_selector('.c-cartLineItem, .c-summary', timeout=5000)
        except:
            log.warning("   购物车DOM未完全加载，尝试读取...")
        
        # 调试：先看页面状态
        try:
            debug_info = self.page.evaluate("""
                () => {
                    return {
                        url: location.href,
                        hasCartLineItem: !!document.querySelector('.c-cartLineItem'),
                        hasSummary: !!document.querySelector('.c-summary'),
                        hasActionBar: !!document.querySelector('.m-cartActionBar'),
                        summaryLabels: [...document.querySelectorAll('.c-summary .m-summaryLineItem__label')].map(el => el.getAttribute('data-original-value') || el.innerText.trim()),
                        allPriceAmounts: [...document.querySelectorAll('.a-priceUnit__amount')].map(el => el.innerText.trim()),
                        actionBarTitle: document.querySelector('.m-cartActionBar__title') ? (document.querySelector('.m-cartActionBar__title').getAttribute('data-original-value') || document.querySelector('.m-cartActionBar__title').innerText.trim()) : null,
                        bodyText: document.body.innerText.substring(0, 500)
                    };
                }
            """)
            log.info(f"   🔍 调试: URL={debug_info.get('url')}, cartItem={debug_info.get('hasCartLineItem')}, summary={debug_info.get('hasSummary')}, actionBar={debug_info.get('hasActionBar')}")
            log.info(f"   🔍 summaryLabels={debug_info.get('summaryLabels')}")
            log.info(f"   🔍 allPriceAmounts={debug_info.get('allPriceAmounts')}")
            log.info(f"   🔍 actionBarTitle={debug_info.get('actionBarTitle')}")
        except Exception as e:
            log.warning(f"   调试信息获取失败: {e}")
        
        # 方法1: DOM - Order Summary 的 Total 行（最可靠）
        try:
            dom_total = self.page.evaluate("""
                () => {
                    // 策略A: Order Summary 中 label 为 "Total" 的行
                    const summaryItems = document.querySelectorAll('.c-summary .m-summaryLineItem');
                    for (const item of summaryItems) {
                        const label = item.querySelector('.m-summaryLineItem__label');
                        const labelVal = label ? (label.getAttribute('data-original-value') || label.innerText.trim()).toUpperCase() : '';
                        if (labelVal === 'TOTAL') {
                            const priceEl = item.querySelector('.a-priceUnit__amount');
                            if (priceEl) {
                                const m = priceEl.innerText.match(/\\$([\\d,.]+)/);
                                if (m) return parseFloat(m[1].replace(',', ''));
                            }
                        }
                    }
                    
                    // 策略B: 底部 sticky bar 的 Total
                    const actionBarTitle = document.querySelector('.m-cartActionBar__title');
                    if (actionBarTitle) {
                        const titleVal = (actionBarTitle.getAttribute('data-original-value') || actionBarTitle.innerText.trim()).toUpperCase();
                        if (titleVal === 'TOTAL') {
                            const actionBarPrice = document.querySelector('.m-cartActionBar__price .a-priceUnit__amount');
                            if (actionBarPrice) {
                                const m = actionBarPrice.innerText.match(/\\$([\\d,.]+)/);
                                if (m) return parseFloat(m[1].replace(',', ''));
                            }
                        }
                    }
                    
                    // 策略C: 读取每个 c-cartLineItem 的价格求和
                    const lineItems = document.querySelectorAll('.c-cartLineItem');
                    let prices = [];
                    for (const item of lineItems) {
                        const priceEl = item.querySelector('.c-cartLineItem__price .a-priceUnit__amount');
                        if (priceEl) {
                            const m = priceEl.innerText.match(/\\$([\\d,.]+)/);
                            if (m) prices.push(parseFloat(m[1].replace(',', '')));
                        }
                    }
                    if (prices.length > 0) return prices.reduce((a,b) => a+b, 0);
                    
                    // 策略D: Subtotal 行（Total前的合计）
                    for (const item of summaryItems) {
                        const label = item.querySelector('.m-summaryLineItem__label');
                        const labelVal = label ? (label.getAttribute('data-original-value') || label.innerText.trim()).toUpperCase() : '';
                        if (labelVal === 'SUBTOTAL') {
                            const priceEl = item.querySelector('.a-priceUnit__amount');
                            if (priceEl) {
                                const m = priceEl.innerText.match(/\\$([\\d,.]+)/);
                                if (m) return parseFloat(m[1].replace(',', ''));
                            }
                        }
                    }
                    
                    return 0;
                }
            """)
            if dom_total and dom_total > 0:
                log.info(f"   购物车总额(DOM): ${dom_total}")
                self.cart_total = dom_total
                return dom_total
        except Exception as e:
            log.warning(f"   DOM读取异常: {e}")
        
        # 方法2: API
        result = self.gql("MiniCartWidgetInitializationQuery", {"storeFront": "pledge"})
        
        # 检查API错误
        if result.get('errors'):
            err_msg = result['errors'][0].get('message', 'Unknown error')
            err_code = result['errors'][0].get('code', '')
            log.warning(f"   API错误: [{err_code}] {err_msg}")
            return 0.0
        
        cart = result.get('data', {}).get('store', {}).get('cart', {})
        total_raw = cart.get('total', 0)
        if isinstance(total_raw, dict):
            total = float(total_raw.get('amount', 0))
        elif isinstance(total_raw, (int, float)):
            total = float(total_raw)
        elif isinstance(total_raw, str):
            total = float(re.sub(r'[^\d.]', '', total_raw) or '0')
        else:
            total = 0.0
        
        if total > 0:
            log.info(f"   购物车总额(API): ${total}")
            self.cart_total = total
            return total
        
        log.warning(f"⚠️ 未能获取购物车总额")
        return 0.0

    def superfast_checkout(self) -> bool:
        """极速结账：API完成付款
        
        前提：购物车里已有商品（通过页面add_to_cart_via_page完成）
        流程（照抄真实浏览器请求）：
        1. 应用信用点 (AddCreditMutation / credit_update)
        2. NextStep (flow.moveNext)
        3. 再次NextStep（跳过地址绑定，RSI使用默认地址）
        4. NextStep (flow.moveNext)
        5. 获取token/mark → validate
        """
        # 步骤1: 使用加购时记录的SKU价格
        log.info("📍 [极速结账] 开始结账...")
        total = self.cart_total
        if total <= 0:
            log.error("❌ 未获取到商品价格，无法结账")
            return False
        log.info(f"   商品价格: ${total}")
        
        # 步骤2: 应用信用点 (credit_update)
        log.info("📍 [极速结账] 应用信用点...")
        result = self.gql("AddCreditMutation", {"amount": total, "storeFront": "pledge"})
        time.sleep(0.1)
        credits = result.get('data', {}).get('store', {}).get('cart', {}).get('totals', {}).get('credits', {})
        if credits:
            log.info(f"   ✅ 信用点: {credits.get('amount', '?')}, max={credits.get('maxApplicable', '?')}")
        else:
            log.warning(f"   ⚠️ 信用点结果: {json.dumps(result, ensure_ascii=False)[:300]}")
        
        # 步骤3: NextStep (flow.moveNext)
        log.info("📍 [极速结账] NextStep...")
        result = self.gql("NextStepMutation", {"storeFront": "pledge"})
        time.sleep(0.1)
        move_next = result.get('data', {}).get('store', {}).get('cart', {}).get('mutations', {}).get('flow', {}).get('moveNext', False)
        flow_steps = result.get('data', {}).get('store', {}).get('cart', {}).get('flow', {}).get('steps', [])
        log.info(f"   moveNext={move_next}, steps={[s.get('step') for s in flow_steps]}")
        
        # 步骤4: 再次NextStep（跳过地址绑定，RSI使用默认地址）
        log.info("📍 [极速结账] NextStep (确认)...")
        result = self.gql("NextStepMutation", {"storeFront": "pledge"})
        time.sleep(0.1)
        move_next = result.get('data', {}).get('store', {}).get('cart', {}).get('mutations', {}).get('flow', {}).get('moveNext', False)
        order_slug = result.get('data', {}).get('store', {}).get('order', {}).get('slug', '')
        log.info(f"   moveNext={move_next}, orderSlug={order_slug}")
        
        # 步骤6: validate确认付款（信用点付款无需recaptcha token）
        log.info("📍 [极速结账] 确认付款...")
        
        result = self.gql("CartValidateCartMutation", {"token": "", "mark": "", "storeFront": "pledge"})
        time.sleep(0.1)
        
        validate_result = result.get('data', {}).get('store', {}).get('cart', {}).get('mutations', {}).get('validate', '')
        order_slug = result.get('data', {}).get('store', {}).get('order', {}).get('slug', '')
        
        if validate_result or order_slug:
            order_num = order_slug or validate_result
            log.info(f"   🎉 付款成功! 订单号: {order_num}")
            try:
                self.page.goto("https://robertsspaceindustries.com/en/account/pledges", timeout=10000)
            except:
                pass
            return True
        else:
            log.error(f"   ❌ 付款失败: {json.dumps(result, ensure_ascii=False)[:500]}")
            return False

    
    
    def add_to_cart_via_page(self) -> bool:
        """列表页直接加购 - v4
        目标SKU：信用点版（无Warbond标签）且可加购（按钮不是OUT OF STOCK）
        流程：打开筛选搜索URL → 找到目标卡片 → 直接点购物车按钮 → 跳购物车
        
        DOM结构（已验证）：
        - 卡片容器：.browsePage-cardStack__grid
        - 卡片：.c-skuCard
        - 标签：.c-skuCard__tag（文字如"Warbond"、"Out of Stock"、"Concept"等）
        - 购物车按钮：.a-skuButton（可用时文字"Add to Cart"，不可用时"OUT OF STOCK"）
        """
        log.info("📍 [列表页加购]")
        
        # 确保在列表页
        browse_url = CFG["BROWSE_URL_PREFIX"] + CFG["SEARCH_KEYWORDS"]
        
        # 白屏检测：如果当前URL是about:blank，重新打开列表页
        cur_url = self.page.url
        if not cur_url or cur_url == "about:blank" or cur_url == "about:blank#":
            log.warning("⚠️ 页面白屏，重新打开列表页...")
            self.page.goto(browse_url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(2)
        cur_url = self.page.url
        if CFG["SEARCH_KEYWORDS"] not in cur_url:
            log.info(f"   跳转到列表页: {browse_url}")
            self.page.goto(browse_url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(2)  # 等React渲染
        
        # 检查列表页是否有卡片（开抢后刷新可能刷早了，商品还没上架）
        # 最多刷5次，每次间隔1秒
        for attempt in range(1, 6):
            check_result = self.page.evaluate("""
                () => {
                    const cards = document.querySelectorAll('.c-skuCard');
                    return { cardCount: cards.length };
                }
            """)
            card_count = check_result['cardCount']
            
            if attempt == 1:
                log.info(f"   📋 第{attempt}次检查: {card_count}个卡片")
            
            if card_count > 0:
                break  # 有卡片了，继续正常流程
            
            # 没卡片，赶紧再刷
            if attempt < 5:
                log.info(f"   ⚠️ 无卡片(第{attempt}次)，赶紧再刷...")
                self.page.reload(wait_until="domcontentloaded", timeout=10000)
                time.sleep(1)  # 等渲染
            else:
                log.error("❌ 5次刷新后仍无卡片（商品可能未上架）")
                config.ss(self.page, "NO_CARDS")
                return False
        
        log.info(f"   ✅ 找到{card_count}个卡片，继续...")
        
        # 获取排除关键词
        exclude_keywords = [kw.strip().lower() for kw in CFG["EXCLUDE_KEYWORDS"].split(',') if kw.strip()]
        if exclude_keywords:
            log.info(f"   🚫 排除关键词: {exclude_keywords}")
        
        # 遍历卡片找目标
        log.info("   🔍 扫描卡片...")
        r = self.page.evaluate(f"""
            () => {{
                const cards = document.querySelectorAll('.c-skuCard');
                let targetCard = null;
                let targetPrice = 0;
                let info = [];
                
                // 排除关键词（小写）
                const excludeList = {exclude_keywords};
                
                for (const card of cards) {{
                    // 获取卡片标题
                    const titleEl = card.querySelector('.c-skuCard__title, .c-skuCard__name, [class*="title"]');
                    const title = titleEl ? titleEl.innerText.trim() : 'Unknown';
                    const titleLower = title.toLowerCase();
                    
                    // 检查是否包含排除词
                    const isExcluded = excludeList.some(kw => titleLower.includes(kw));
                    if (isExcluded) {{
                        info.push({{title, status: '排除', hasWarbond: false, isOutOfStock: false}});
                        continue;
                    }}
                    
                    // 获取所有标签
                    const tags = [...card.querySelectorAll('.c-skuCard__tag')]
                        .map(t => t.innerText.trim());
                    const hasWarbond = tags.some(t => t.toUpperCase().includes('WARBOND'));
                    
                    // 获取按钮文字
                    const btn = card.querySelector('.a-skuButton');
                    const btnText = btn ? btn.innerText.trim() : '';
                    const isOutOfStock = btnText.toUpperCase().includes('OUT OF STOCK');
                    
                    // 读取卡片价格
                    const priceEl = card.querySelector('.a-priceUnit__amount');
                    const priceText = priceEl ? priceEl.innerText.trim() : '';
                    const priceMatch = priceText.match(/\$([\d,.]+)/);
                    const price = priceMatch ? parseFloat(priceMatch[1].replace(',', '')) : 0;
                    
                    info.push({{title, status: '目标', hasWarbond, btnText, isOutOfStock, price}});
                    
                    // 目标条件：无Warbond标签 且 可加购
                    if (!hasWarbond && !isOutOfStock) {{
                        targetCard = card;
                        targetPrice = price;
                    }}
                }}
                
                return {{
                    total: cards.length,
                    info: info,
                    found: !!targetCard,
                    price: targetPrice
                }};
            }}
        """)
        
        log.info(f"   📋 共{r.get('total', 0)}个卡片")
        
        # [DEBUG] 探测卡片React fiber，找skuId/id字段
        try:
            fiber_debug = self.page.evaluate("""
                () => {
                    const cards = document.querySelectorAll('.c-skuCard');
                    if (cards.length === 0) return { error: 'no cards' };
                    
                    const results = [];
                    for (let i = 0; i < Math.min(cards.length, 2); i++) {
                        const card = cards[i];
                        const titleEl = card.querySelector('.c-skuCard__title, .c-skuCard__name, [class*="title"]');
                        const title = titleEl ? titleEl.innerText.trim() : 'Unknown';
                        
                        const found = {};
                        
                        // 方法1: 遍历React fiber找含id/sku的props
                        for (const key of Object.keys(card)) {
                            if (!key.startsWith('__react')) continue;
                            try {
                                let obj = card[key];
                                const search = (o, depth, path) => {
                                    if (!o || typeof o !== 'object' || depth > 3) return;
                                    for (const [k, v] of Object.entries(o)) {
                                        const np = path ? path + '.' + k : k;
                                        if (typeof k === 'string' && (k === 'id' || k === 'skuId' || k === 'sku' || k === 'productId' || k === 'slug' || k === 'resourceId')) {
                                            found[np] = String(v).substring(0, 100);
                                        }
                                        if (v && typeof v === 'object' && !np.includes('parent')) {
                                            try { search(v, depth + 1, np); } catch(e) {}
                                        }
                                    }
                                };
                                search(obj, 0, key.substring(0, 15));
                            } catch(e) {}
                        }
                        
                        // 方法2: 检查卡片所有data-*属性
                        for (const attr of card.attributes) {
                            if (attr.name.startsWith('data-')) {
                                found['attr.' + attr.name] = attr.value.substring(0, 100);
                            }
                        }
                        
                        // 方法3: 检查按钮的React fiber
                        const btn = card.querySelector('.a-skuButton');
                        if (btn) {
                            for (const key of Object.keys(btn)) {
                                if (!key.startsWith('__reactProps')) continue;
                                try {
                                    const props = btn[key];
                                    if (props && typeof props === 'object') {
                                        found['btn.' + key.substring(0, 20)] = JSON.stringify(props).substring(0, 300);
                                    }
                                } catch(e) {}
                            }
                        }
                        
                        // 方法4: 检查卡片内所有a[href]链接
                        const links = card.querySelectorAll('a[href]');
                        links.forEach((a, idx) => {
                            found['link' + idx] = a.href;
                        });
                        
                        results.push({ title, found });
                    }
                    return results;
                }
            """)
            
            if isinstance(fiber_debug, list):
                for item in fiber_debug:
                    log.info(f"   [Fiber探针] 卡片: {item.get('title', '?')}")
                    for k, v in item.get('found', {}).items():
                        log.info(f"      {k} = {v}")
            else:
                log.info(f"   [Fiber探针] {fiber_debug}")
        except Exception as e:
            log.warning(f"   [Fiber探针] 失败: {e}")
        for d in r.get('info', []):
            if d.get('status') == '排除':
                log.info(f"      [{d['title'][:30]}] 🚫 排除")
            else:
                tag_info = "Warbond" if d['hasWarbond'] else "信用点版"
                stock_info = "缺货" if d['isOutOfStock'] else "可购"
                log.info(f"      [{d['title'][:30]}] {tag_info} | {stock_info}")
        
        if not r.get('found'):
            # 未找到目标卡片（可能Out of Stock或无信用点版），刷新重试5次
            log.warning("   ⚠️ 未找到符合条件的卡片，刷新重试...")
            for retry in range(1, 6):
                self.page.reload(wait_until="domcontentloaded", timeout=10000)
                time.sleep(1)
                # 重新扫描
                r2 = self.page.evaluate(f"""
                    () => {{
                        const cards = document.querySelectorAll('.c-skuCard');
                        let targetCard = null;
                        let info = [];
                        const excludeList = {exclude_keywords};
                        for (const card of cards) {{
                            const titleEl = card.querySelector('.c-skuCard__title, .c-skuCard__name, [class*="title"]');
                            const title = titleEl ? titleEl.innerText.trim() : 'Unknown';
                            const titleLower = title.toLowerCase();
                            const isExcluded = excludeList.some(kw => titleLower.includes(kw));
                            if (isExcluded) {{
                                info.push({{title, status: '排除', hasWarbond: false, isOutOfStock: false}});
                                continue;
                            }}
                            const tags = [...card.querySelectorAll('.c-skuCard__tag')]
                                .map(t => t.innerText.trim());
                            const hasWarbond = tags.some(t => t.toUpperCase().includes('WARBOND'));
                            const btn = card.querySelector('.a-skuButton');
                            const btnText = btn ? btn.innerText.trim() : '';
                            const isOutOfStock = btnText.toUpperCase().includes('OUT OF STOCK');
                            info.push({{title, status: '目标', hasWarbond, btnText, isOutOfStock}});
                            if (!hasWarbond && !isOutOfStock) {{
                                targetCard = card;
                            }}
                        }}
                        return {{ total: cards.length, info: info, found: !!targetCard }};
                    }}
                """)
                log.info(f"   📋 第{retry}次重试: {r2.get('total', 0)}个卡片")
                for d in r2.get('info', []):
                    if d.get('status') != '排除':
                        tag_info = "Warbond" if d['hasWarbond'] else "信用点版"
                        stock_info = "缺货" if d['isOutOfStock'] else "可购"
                        log.info(f"      [{d['title'][:30]}] {tag_info} | {stock_info}")
                if r2.get('found'):
                    r = r2
                    break
                if retry == 5:
                    log.error("❌ 5次刷新后仍无符合条件的卡片（信用点版+可加购）")
                    config.ss(self.page, "NO_TARGET_CARD")
                    return False
        
        # 点击加购按钮（最多5次）
        for click_attempt in range(1, 6):
            log.info(f"   🔘 加购尝试 {click_attempt}/5...")
            
            # 找目标卡片并点击（带排除关键词的JS版本）
            try:
                # 使用JS点击，更精确地过滤排除词
                click_result = self.page.evaluate(f"""
                    () => {{
                        const cards = document.querySelectorAll('.c-skuCard');
                        const excludeList = {exclude_keywords};
                        
                        for (const card of cards) {{
                            // 获取卡片标题
                            const titleEl = card.querySelector('.c-skuCard__title, .c-skuCard__name, [class*="title"]');
                            const title = titleEl ? titleEl.innerText.trim() : '';
                            const titleLower = title.toLowerCase();
                            
                            // 检查是否包含排除词
                            const isExcluded = excludeList.some(kw => titleLower.includes(kw));
                            if (isExcluded) continue;
                            
                            // 检查Warbond和库存
                            const tags = [...card.querySelectorAll('.c-skuCard__tag')]
                                .map(t => t.innerText.trim());
                            const hasWarbond = tags.some(t => t.toUpperCase().includes('WARBOND'));
                            
                            const btn = card.querySelector('.a-skuButton');
                            const btnText = btn ? btn.innerText.trim() : '';
                            const isOutOfStock = btnText.toUpperCase().includes('OUT OF STOCK');
                            
                            if (!hasWarbond && !isOutOfStock && btn) {{
                                btn.click();
                                return {{ success: true, title: title }};
                            }}
                        }}
                        return {{ success: false }};
                    }}
                """)
                if click_result.get('success'):
                    log.info(f"   ✅ 点击加购按钮: {click_result.get('title', '')}")
                else:
                    log.warning("   ⚠️ JS点击未找到目标卡片")
            except Exception as e:
                log.warning(f"   JS点击失败({e})")
            
            # 等1秒
            time.sleep(1)
            
            # 检查是否出现加购成功提示
            has_success = self.page.evaluate("""
                () => {
                    return document.body.innerText.includes('successfully added');
                }
            """)
            
            if has_success:
                # 保存SKU价格作为购物车总额
                sku_price = r.get('price', 0) or 0
                if sku_price > 0:
                    self.cart_total = sku_price
                    log.info(f"   ✅ 加购成功！价格: ${sku_price}")
                else:
                    log.info("   ✅ 加购成功！")
                # Superfast版：不跳转购物车，直接API结账
                return True
        
        # 5次都失败
        log.error("❌ 加购失败（5次）")
        config.ss(self.page, "CART_RETRY_FAILED")
        return False
    
    def apply_credits(self, amount: float = None) -> Dict:
        """1. 应用信用点"""
        log.info(f"📍 [应用信用点] amount=${amount or '全部'}")
        
        if amount is None:
            # 优先从购物车获取总额
            amount = self.get_cart_total()
            if amount <= 0:
                amount = self.cart_total or 1000  # 默认为较大值
        
        variables = {
            "amount": amount,
            "storeFront": "pledge"
        }
        
        # 重试逻辑（高并发补偿）
        result = {}
        for _retry in range(3):
            result = self.gql("AddCreditMutation", variables)
            if result and not result.get('errors'):
                break
            if _retry < 2:
                log.warning(f"   信用点重试({_retry+1}/2)...")
                time.sleep(0.2)
        
        if result.get('errors'):
            log.warning(f"⚠️ 信用点错误: {result['errors']}")
            return {"success": False, "data": result}
        
        # 检查响应结构
        add_credits = result.get('data', {}).get('store', {}).get('cart', {}).get('mutations', {}).get('addCredit', {})
        
        if add_credits:
            applied_amount = add_credits.get('amount', 0)
            log.info(f"✅ 信用点应用成功! 金额: ${applied_amount}")
            return {"success": True, "data": result}
        
        # 检查是否有其他成功标识
        if result.get('data'):
            log.info("✅ 信用点请求已发送")
            return {"success": True, "data": result}
        
        log.warning("⚠️ 信用点应用结果未知")
        return {"success": True, "data": result}
    
    def next_step(self) -> Dict:
        """2. 下一步"""
        log.info("📍 [进入结算]")
        
        variables = {"storeFront": "pledge"}
        # 重试逻辑（高并发补偿）
        result = {}
        for _retry in range(3):
            result = self.gql("NextStepMutation", variables)
            if result and not result.get('errors'):
                break
            if _retry < 2:
                log.warning(f"   NextStep重试({_retry+1}/2)...")
                time.sleep(0.2)
        
        if result.get('errors'):
            log.warning(f"⚠️ NextStep错误: {result['errors']}")
            return {"success": False, "data": result}
        
        # 从响应中提取step和token
        mutations = result.get('data', {}).get('store', {}).get('cart', {}).get('mutations', {})
        next_step_data = mutations.get('nextStep', {})
        step = next_step_data.get('step', 'unknown')
        token = next_step_data.get('token', '')
        
        log.info(f"   step={step}, token={token[:20] if token else 'N/A'}...")
        
        # 保存token供后续使用
        if token:
            self.cart_data['token'] = token
        
        return {"success": True, "data": result, "step": step, "token": token}
    
    def assign_address(self, address_id: str = None) -> Dict:
        """3. 绑定地址"""
        log.info(f"📍 [绑定地址]")
        
        if address_id is None:
            address_id = self.billing_address_id
        
        if address_id is None:
            log.warning("⚠️ 无地址ID，跳过")
            return {"success": True, "skipped": True}
        
        variables = {
            "billing": address_id,
            "storeFront": "pledge"
        }
        
        result = self.gql("CartAddressAssignMutation", variables)
        
        if result.get('errors'):
            log.warning(f"⚠️ 地址错误: {result['errors']}")
            return {"success": False, "data": result}
        
        # 检查响应
        mutations = result.get('data', {}).get('store', {}).get('cart', {}).get('mutations', {})
        assign_result = mutations.get('addressAssign', {})
        
        if assign_result or result.get('data'):
            log.info("✅ 地址绑定成功")
            return {"success": True, "data": result}
        
        log.warning("⚠️ 地址绑定结果未知")
        return {"success": True, "data": result}
    
    def validate_cart(self, token: str = None, mark: bool = True) -> Dict:
        """4. 确认付款"""
        log.info("📍 [确认付款]")
        
        # 使用传入的token或从之前步骤保存的
        if token is None:
            token = self.cart_data.get('token', '')
        
        # mark通常是boolean true
        if not mark:
            mark = True
        
        log.info(f"   token={token[:30] if token else 'N/A'}..., mark={mark}")
        
        variables = {
            "storeFront": "pledge",
            "token": token or "PLACEHOLDER",
            "mark": mark
        }
        
        result = self.gql("CartValidateCartMutation", variables)
        
        if result.get('errors'):
            log.warning(f"⚠️ Validate错误: {result['errors']}")
            return {"success": False, "data": result}
        
        # 检查响应
        mutations = result.get('data', {}).get('store', {}).get('cart', {}).get('mutations', {})
        validate_result = mutations.get('validateCart', {})
        
        if validate_result:
            result_val = validate_result.get('result')
            order_number = validate_result.get('number')
            
            if result_val or order_number:
                log.info(f"✅ 验证成功! 订单号: {order_number or result_val}")
                return {"success": True, "data": result}
        
        # 如果没有明确错误，也认为成功
        if result.get('data'):
            log.info("✅ 验证请求已发送")
            return {"success": True, "data": result}
        
        return {"success": False, "data": result}

    def get_cart_items_from_page(self) -> list:
        """从购物车页面DOM读取商品信息（伏击模式用）
        
        返回格式：[{'title': str, 'price': float}]
        """
        log.info("📍 [读取购物车商品]")
        
        # 确保购物车页面DOM已渲染
        try:
            self.page.wait_for_selector('.c-cartLineItem, .c-summary', timeout=5000)
        except:
            log.warning("   购物车DOM未完全加载，尝试读取...")
        
        # 读取购物车商品信息
        try:
            items = self.page.evaluate("""
                () => {
                    const result = {
                        items: [],
                        total: 0
                    };
                    
                    // 读取商品行
                    const lineItems = document.querySelectorAll('.c-cartLineItem');
                    for (const item of lineItems) {
                        const titleEl = item.querySelector('.c-cartLineItem__name, .c-cartLineItem__title, [class*="name"]');
                        const priceEl = item.querySelector('.c-cartLineItem__price, [class*="price"] .a-priceUnit__amount');
                        
                        const title = titleEl ? titleEl.innerText.trim() : 'Unknown';
                        let price = 0;
                        
                        if (priceEl) {
                            const priceText = priceEl.innerText.trim();
                            const m = priceText.match(/\$?([\d,.]+)/);
                            if (m) {
                                price = parseFloat(m[1].replace(',', ''));
                            }
                        }
                        
                        if (price > 0) {
                            result.items.push({title, price});
                        }
                    }
                    
                    // 读取总价（如果能获取）
                    const summaryItems = document.querySelectorAll('.c-summary .m-summaryLineItem');
                    for (const item of summaryItems) {
                        const label = item.querySelector('.m-summaryLineItem__label');
                        const labelVal = label ? (label.getAttribute('data-original-value') || label.innerText.trim()).toUpperCase() : '';
                        if (labelVal === 'TOTAL') {
                            const priceEl = item.querySelector('.a-priceUnit__amount');
                            if (priceEl) {
                                const priceText = priceEl.innerText.trim();
                                const m = priceText.match(/\$?([\d,.]+)/);
                                if (m) {
                                    result.total = parseFloat(m[1].replace(',', ''));
                                }
                            }
                        }
                    }
                    
                    return result;
                }
            """)
            
            log.info(f"   购物车商品: {len(items.get('items', []))}个")
            for item in items.get('items', []):
                log.info(f"      - {item['title'][:40]}: ${item['price']}")
            log.info(f"   总价: ${items.get('total', 0)}")
            
            return items
        except Exception as e:
            log.error(f"❌ 读取购物车失败: {e}")
            return {"items": [], "total": 0}

    def superfast_ambush(self) -> bool:
        """伏击模式极速结账
        
        前提：物品已在购物车
        流程：
        1. 从购物车页面DOM读取商品总价
        2. T-30s执行预装填：AddCreditMutation → NextStepMutation → NextStepMutation（跳过地址绑定）
        3. T-0s执行：CartValidateCartMutation
        """
        log.info("📍 [伏击模式] 开始执行...")
        
        # 步骤1: 读取购物车总价
        cart_info = self.get_cart_items_from_page()
        items = cart_info.get('items', [])
        total = cart_info.get('total', 0)
        
        if not items:
            log.error("❌ 购物车为空，无法执行伏击模式")
            return False
        
        # 如果total为0，累加所有商品价格
        if total <= 0:
            total = sum(item['price'] for item in items)
        
        if total <= 0:
            log.error("❌ 无法获取商品价格，无法执行伏击模式")
            return False
        
        log.info(f"   商品总价: ${total}")
        
        # 步骤2: 应用信用点 (AddCreditMutation)
        log.info("📍 [伏击模式] 应用信用点...")
        result = self.gql("AddCreditMutation", {"amount": total, "storeFront": "pledge"})
        time.sleep(0.1)
        credits = result.get('data', {}).get('store', {}).get('cart', {}).get('totals', {}).get('credits', {})
        if credits:
            log.info(f"   ✅ 信用点: {credits.get('amount', '?')}, max={credits.get('maxApplicable', '?')}")
        else:
            log.warning(f"   ⚠️ 信用点结果: {json.dumps(result, ensure_ascii=False)[:300]}")
        
        # 步骤3: NextStep
        log.info("📍 [伏击模式] NextStep...")
        result = self.gql("NextStepMutation", {"storeFront": "pledge"})
        time.sleep(0.1)
        move_next = result.get('data', {}).get('store', {}).get('cart', {}).get('mutations', {}).get('flow', {}).get('moveNext', False)
        log.info(f"   moveNext={move_next}")
        
        # 步骤4: 再次NextStep（跳过地址绑定，RSI使用默认地址）
        log.info("📍 [伏击模式] NextStep (确认)...")
        result = self.gql("NextStepMutation", {"storeFront": "pledge"})
        time.sleep(0.1)
        move_next = result.get('data', {}).get('store', {}).get('cart', {}).get('mutations', {}).get('flow', {}).get('moveNext', False)
        order_slug = result.get('data', {}).get('store', {}).get('order', {}).get('slug', '')
        log.info(f"   moveNext={move_next}, orderSlug={order_slug}")
        
        log.info("📍 [伏击模式] 预装填完成，等待T-0...")
        
        # 预装填完成，后续validate由主线程在精确时间执行
        self.cart_data['ambush_ready'] = True
        return True
    
    def ambush_validate(self) -> bool:
        """伏击模式 - T-0时刻执行最终验证（带重试）
        
        失败则0.3秒间隔重试，最多3次
        """
        for attempt in range(1, 9):
            log.info(f"📍 [伏击模式] T-0 执行验证... (尝试 {attempt}/8)")
            
            result = self.gql("CartValidateCartMutation", {"token": "", "mark": "", "storeFront": "pledge"})
            
            validate_result = result.get('data', {}).get('store', {}).get('cart', {}).get('mutations', {}).get('validate', '')
            order_slug = result.get('data', {}).get('store', {}).get('order', {}).get('slug', '')
            
            if validate_result or order_slug:
                order_num = order_slug or validate_result
                log.info(f"   🎉 付款成功! 订单号: {order_num}")
                try:
                    self.page.goto("https://robertsspaceindustries.com/en/account/pledges", timeout=10000)
                except:
                    pass
                return True
            
            if attempt < 8:
                log.warning(f"   ⚠️ 验证失败，0.2秒后重试...")
                time.sleep(0.2)
            else:
                log.error(f"   ❌ 验证失败: {json.dumps(result, ensure_ascii=False)[:500]}")
        
        return False
