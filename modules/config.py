#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
咩咩Kick! V3.0.0
配置常量和工具函数模块
"""

import json, os, sys, time, logging, subprocess, argparse
import re
from datetime import datetime
from typing import Optional, Dict, Any, List


def resource_path(relative_path):
    """获取资源文件路径（images目录下的图片等）
    开发环境：从项目根目录的images/读取
    EXE运行时：从exe同目录的images/读取
    """
    # 获取exe或脚本所在目录
    if getattr(sys, 'frozen', False):
        # PyInstaller打包后
        base_path = os.path.dirname(sys.executable)
    else:
        # 开发环境
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, 'images', relative_path)

# 项目根目录（兼容PyInstaller打包）
if getattr(sys, 'frozen', False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# GUI背景色常量（用于需要底色的控件，如日志区域）
GUI_BG_COLOR = "#A8B4D4"  # 小底色条颜色（浅蓝灰白）
GUI_TITLE_COLOR = "#1a3a5c"  # 标题文字（深蓝）
GUI_TEXT_COLOR = "#2d2d2d"  # 正文文字（深灰）
GUI_BG_DARK = "#1e1e2e"  # 备用深色背景
GUI_BG_NONE = "#A8B4D4"  # 接近背景底色，浅蓝灰白

# ============================================================
# 命令行参数
# ============================================================

_parser = argparse.ArgumentParser(description='咩咩Kick! V3.0.0')
_parser.add_argument('--no-gui', action='store_true', help='禁用GUI，仅使用命令行模式')
_parser.add_argument('--test', '-t', action='store_true', help='测试模式')

# 延迟解析：PyInstaller分析导入时不触发parse_args
_args = None

def get_args():
    """获取命令行参数，首次调用时解析"""
    global _args
    if _args is None:
        _args = _parser.parse_args()
    return _args

# ============================================================
# 配置区
# ============================================================

CFG = {
    "TARGET_TIME": "2026-05-15 00:00:00",
    "TIMEZONE": "Asia/Shanghai",
    "TIME_OFFSET": 0,  # 手动时间偏移(秒)，网络延迟约0.073s+buffer=提前0.2秒
    
    # 列表页浏览URL前缀（搜索关键词拼接在后面）
    "BROWSE_URL_PREFIX": "https://robertsspaceindustries.com/en/store/pledge/browse/extras/standalone-ships?page=1&sortField=price&sortDir=desc&keywords=",
    # 搜索关键词（空格用+号，如 "Kraken" 或 "Drake+Kraken"）
    "ITEM_PRICE": 0,
    "SEARCH_KEYWORDS": "Kraken",
    # 排除关键词（英文逗号分隔，如"Privateer,DUR"）
    "EXCLUDE_KEYWORDS": "",
    "CART_URL": "https://robertsspaceindustries.com/en/store/pledge/cart",
    
    "GRAPHQL_URL": "https://robertsspaceindustries.com/graphql",
    
    "PROXY": None,
    
    # 执行模式
    "MODE": "api",  # "api" = 列表页加购+API付款, "page" = 纯页面模式
    
    "PRE_WARM": 60,
    "PRE_REFRESH": 0.05,  # 提前50ms刷新，确保服务器已上架
    "DELAY": 0.01,  # API模式极小延迟
    "TIMEOUT": 3,
    
    "UA": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    
    "INPUT_MODE": "intercept",
    "SKU_ID": "",
    "MANUAL_TIME_OFFSET": "-0.1",
    "AUTO_CALIBRATE": False,
    "COOKIE_FILE": os.path.join(BASE_PATH, "scautobuy", "rsi_cookies.json"),
    "LOG_FILE": os.path.join(BASE_PATH, "scautobuy", "rsi_buy.log"),
    "SCREENSHOT_DIR": os.path.join(BASE_PATH, "scautobuy", "screenshots"),
}

# ============================================================
# GraphQL Queries
# ============================================================

QUERIES = {
    # 1. 加购（替代页面点击）
    "AddCartMultiItemMutation": '''
mutation AddCartMultiItemMutation($query: [CartAddInput!], $storeFront: String = "pledge") {
  store(name: $storeFront) {
    cart {
      mutations {
        addMany(query: $query) {
          count
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}
''',
    
    # 2. 应用信用点
    "AddCreditMutation": '''
mutation AddCreditMutation($amount: Float!, $storeFront: String) {
  store(name: $storeFront) {
    cart {
      mutations {
        credit_update(amount: $amount)
        __typename
      }
      __typename
    }
    ...EntityAfterUpdateFragment
    __typename
  }
}

fragment EntityAfterUpdateFragment on TyStore {
  cart {
    lineItemsQties
    billingRequired
    totals {
      total
      credits {
        amount
        __typename
      }
      __typename
    }
    __typename
  }
  __typename
}
''',
    
    # 3. 下一步
    "NextStepMutation": '''
mutation NextStepMutation($storeFront: String) {
  store(name: $storeFront) {
    cart {
      hasDigital
      mutations {
        flow {
          moveNext
          __typename
        }
        __typename
      }
      totals {
        total
        __typename
      }
      __typename
    }
    ...CartFlowFragment
    ...OrderSlugFragment
    __typename
  }
}

fragment CartFlowFragment on TyStore {
  cart {
    flow {
      steps {
        step
        action
        finalStep
        active
        __typename
      }
      current {
        orderCreated
        __typename
      }
      __typename
    }
    __typename
  }
  __typename
}

fragment OrderSlugFragment on TyStore {
  order {
    slug
    __typename
  }
  __typename
}
''',
    
    # 4. 绑定地址
    "CartAddressAssignMutation": '''
mutation CartAddressAssignMutation($billing: ID, $shipping: ID, $storeFront: String) {
  store(name: $storeFront) {
    cart {
      mutations {
        assignAddresses(assign: {billing: $billing, shipping: $shipping})
        __typename
      }
      __typename
    }
    __typename
  }
}
''',
    
    # 5. 确认付款
    "CartValidateCartMutation": '''
mutation CartValidateCartMutation($storeFront: String, $token: String, $mark: String) {
  store(name: $storeFront) {
    cart {
      mutations {
        validate(mark: $mark, token: $token)
        __typename
      }
      __typename
    }
    ...CartFlowFragment2
    ...OrderSlugFragment2
    __typename
  }
}

fragment CartFlowFragment2 on TyStore {
  cart {
    flow {
      steps {
        step
        action
        finalStep
        active
        __typename
      }
      current {
        orderCreated
        __typename
      }
      __typename
    }
    __typename
  }
  __typename
}

fragment OrderSlugFragment2 on TyStore {
  order {
    slug
    __typename
  }
  __typename
}
''',
    
    # 6. 获取购物车信息
    "MiniCartWidgetInitializationQuery": '''
query MiniCartWidgetInitializationQuery($storeFront: String!) {
  store(name: $storeFront) {
    cart {
      id
      lineItemsQties
      __typename
    }
    __typename
  }
}
''',
    
    # 7. 获取地址
    "AddressBookQuery": '''
query AddressBookQuery {
  store {
    addressBook {
      id
      defaultBilling
      company
      firstname
      lastname
      addressLine
      postalCode
      phone
      city
      __typename
    }
    cart {
      totals {
        credits {
          amount
          __typename
        }
        __typename
      }
      __typename
    }
    __typename
  }
}
''',

}


# ============================================================
# 日志
# ============================================================

os.makedirs(os.path.dirname(CFG["LOG_FILE"]), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler(CFG["LOG_FILE"], encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger()

# GUI日志队列 - 日志窗口从这里读取
import queue as _queue_mod
_log_queue = _queue_mod.Queue(-1)  # 无限大小

class _QueueLogHandler(logging.Handler):
    """将日志推送到GUI队列的Handler"""
    def emit(self, record):
        try:
            msg = self.format(record)
            _log_queue.put_nowait(msg)
        except:
            pass

_queue_handler = _QueueLogHandler()
_queue_handler.setFormatter(logging.Formatter('%(asctime)s.%(msecs)03d %(message)s', datefmt='%H:%M:%S'))
log.addHandler(_queue_handler)

def get_log_queue():
    """返回日志队列，供GUI日志窗口读取"""
    return _log_queue

# ============================================================
# 工具函数
# ============================================================

def get_target():
    """获取目标时间戳（UTC）"""
    # Windows兼容：用timedelta代替ZoneInfo（UTC+8）
    from datetime import timedelta
    from calendar import timegm
    tz_offset = timedelta(hours=8)  # Asia/Shanghai = UTC+8
    local_dt = datetime.strptime(CFG["TARGET_TIME"], "%Y-%m-%d %H:%M:%S")
    utc_dt = local_dt - tz_offset
    return timegm(utc_dt.timetuple())

def get_server_time_offset():
    """通过RSI服务器HTTP头获取本地与服务器的时间差（秒）
    正值=本地比服务器快，负值=本地比服务器慢
    """
    import urllib.request
    offsets = []
    for url in ["https://robertsspaceindustries.com", "https://robertsspaceindustries.com/en"]:
        try:
            req = urllib.request.Request(url, method="HEAD")
            t1 = time.time()
            resp = urllib.request.urlopen(req, timeout=10000)
            t2 = time.time()
            server_date = resp.headers.get("Date")
            if server_date:
                # 用strptime+timegm避免Windows datetime.timestamp()的bug
                from calendar import timegm
                try:
                    dt = datetime.strptime(server_date, "%a, %d %b %Y %H:%M:%S GMT")
                    server_ts = timegm(dt.timetuple())
                except:
                    try:
                        dt = datetime.strptime(server_date.replace("GMT", "").strip(), "%a, %d %b %Y %H:%M:%S")
                        server_ts = timegm(dt.timetuple())
                    except:
                        log.warning(f"   无法解析: {server_date}")
                        continue
                local_ts = (t1 + t2) / 2
                offsets.append(local_ts - server_ts)
                log.info(f"   服务器: {server_date} → ts={server_ts:.3f}, 本地: {local_ts:.3f}, 差: {local_ts-server_ts:.3f}s")
        except Exception as e:
            log.warning(f"   时间校准失败: {e}")
            continue
    if offsets:
        offset = sum(offsets) / len(offsets)
        log.info(f"   服务器时间差: {offset:.3f}秒 ({'本地快' if offset > 0 else '本地慢'})")
        return offset
    log.warning("   ⚠️ 未获取到服务器时间，使用本地时间")
    return 0.0

def ss(page, name):
    """截图函数"""
    if page:
        os.makedirs(CFG["SCREENSHOT_DIR"], exist_ok=True)
        path = f"{CFG['SCREENSHOT_DIR']}/{name}_{datetime.now().strftime('%H%M%S_%f')}.png"
        try:
            page.screenshot(path=path)
            log.info(f"📸 {path}")
        except: pass
        return path
    return ""

def notify(title, msg):
    """系统通知"""
    try:
        if sys.platform == 'win32':
            subprocess.run(['powershell', '-Command', 
                f'[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime] | Out-Null; '
                f'$x=[Windows.UI.Notifications.ToastTemplateType]::ToastText02; '
                f'$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($x); '
                f'$t.GetElementsByTagName("text")[0].AppendChild($t.CreateTextNode("{title}")); '
                f'$t.GetElementsByTagName("text")[1].AppendChild($t.CreateTextNode("{msg}")); '
                f'[Windows.UI.Notifications.ToastNotification]::new($t) | %{{[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("RSI").Show($_)}}'
            ], capture_output=True, timeout=5)
        elif sys.platform == 'darwin':
            os.system(f"osascript -e 'display notification \"{msg}\" with title \"{title}\"'")
    except: pass

def _force_exit():
    """强制结束进程"""
    try:
        subprocess.run(['taskkill', '/F', '/IM', 'msedge.exe'], 
                       capture_output=True, timeout=5)
    except:
        pass
    os._exit(0)

# ============================================================
# 全局GUI实例（放在config中避免循环引用）
# ============================================================

_gui = None

def set_gui(gui):
    """设置全局GUI实例"""
    global _gui
    _gui = gui

def get_gui():
    """获取全局GUI实例"""
    global _gui
    return _gui