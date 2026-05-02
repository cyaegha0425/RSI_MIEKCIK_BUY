# RSI_MIEKCIK_BUY - 咩咩Kick! V3.0.0

![Version](https://img.shields.io/badge/version-V3.0.0-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)

## 项目介绍

**咩咩Kick! V3.0.0** 是一款基于 Playwright + GraphQL API 的 RSI 抢船工具，采用全 API 抢购架构。

## 核心特性

### 🎯 三种输入模式

1. **SKU ID直购** - 直接输入商品SKU ID进行加购，最快速
2. **关键词搜索** - 输入搜索关键词，系统自动匹配商品
3. **刷新拦截** - T-0时刷新页面，自动从GraphQL响应中提取skuId

### ⚡ 全API抢购架构 (V3.0.0 新特性)

- **T-5s** 开始 API 加购轮询
- **0.5秒** 轮询间隔
- **API直购** 绕过 DOM 加购延迟
- **智能回退** API失败时自动回退到DOM加购

### 🔧 技术栈

- **Playwright** - 浏览器自动化
- **GraphQL API** - RSI 后端直连
- **tkinter** - GUI 界面
- **多级时间校准** - 精确到毫秒级同步

## 使用方法

### 首次使用

```bash
# 安装依赖
pip install playwright
python -m playwright install chromium

# 运行测试模式
python main.py --test
```

### 正常运行

```bash
python main.py
```

### 命令行参数

- `--no-gui` - 禁用GUI，仅使用命令行模式
- `--test` - 测试模式

## 目录结构

```
RSI_MIEKCIK_BUY/
├── modules/
│   ├── __init__.py
│   ├── api_client.py      # GraphQL API 客户端
│   ├── browser.py         # 浏览器操作
│   ├── calibration.py    # 时间校准
│   ├── config.py          # 配置常量和工具
│   ├── gui_config.py      # 配置窗口 GUI
│   ├── gui_progress.py   # 进度窗口 GUI
│   ├── main.py            # 主入口
│   └── sku_interceptor.py # SKU 拦截器 (V3.0.0)
├── scautobuy/
│   ├── rsi_cookies.json   # 保存的登录状态
│   └── rsi_config.json    # 配置文件
├── images/
│   └── gui_bg.png         # GUI 背景图
├── build.bat              # Windows 构建脚本
└── README.md
```

## 抢购流程

### 正面硬刚模式

```
1. 预热阶段（登录 + 清空购物车 + 校准）
2. 注册 page.on('response') 拦截器
3. T-5s: 开始 API 加购轮询
   - 有 skuId → 直接轮询 api_add_to_cart
   - 有关键词 → T-0 刷新页面，拦截 GraphQL 拿 skuId
4. API 加购轮询 (T-5s ~ T+3s)
   - 0.5秒间隔
   - OutOfStock → 继续轮询
   - HTTP 429 → sleep 3秒
   - HTTP 500 → 直接下一次
   - 加购成功 → 立刻切付款流程
5. T+3s 还没抢到 → 回退 DOM 加购
6. 付款流程：AddCredit → NextStep → NextStep → Validate
```

### 伏击模式

```
1. 预热阶段（登录 + 校准）
2. 将目标商品加入购物车
3. T-30s: 自动预装填
4. T-0: 执行最终验证
```

## 版本历史

### V3.0.0 (咩咩Kick!)

- ✅ 全 API 抢购架构
- ✅ 三种输入模式支持
- ✅ SKU 拦截器
- ✅ 智能回退机制

### V2.0.0 (超级咩Impact！)

- ✅ 页面加购 + API 付款
- ✅ GUI 进度显示
- ✅ 多级时间校准

## 注意事项

⚠️ **请确保**：
1. 提前清空购物车
2. 已登录 RSI 账号
3. 网络稳定
4. 系统时间准确

## 免责声明

本工具仅供学习交流使用，请遵守 RSI 服务条款。

---

**by 咩咩莉娅 V3.0.0**
