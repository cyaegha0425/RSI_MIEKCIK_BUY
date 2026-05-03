# RSI_MIEKCIK_BUY - 咩咩蹄到好船来 V3.0.4

![Version](https://img.shields.io/badge/version-V3.0.4-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)

## 项目介绍

**咩咩蹄到好船来 V3.0.4** 是一款基于 Playwright + GraphQL API 的 RSI 星际公民商店自动抢购工具，采用全 API 抢购架构，不依赖 DOM 点击，实现极速抢购。

## 核心特性

### 两种输入模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| **刷新拦截模式 (intercept)** | 输入搜索关键词，T-0 刷新页面，自动从 GraphQL 响应中提取 skuId 并加购 | 不知道具体 SKU ID 的商品 |
| **SKU ID 直购模式 (sku)** | 直接输入商品 SKU ID 进行 API 加购 | 已知道目标商品 SKU ID |

### 全 API 抢购架构

- **T-10 开始轮询**：SKU 模式提前 10 秒启动 API 加购轮询
- **T-0 刷新拦截**：intercept 模式在 T-0 瞬间刷新页面，GraphQL 拦截获取 skuId
- **极速结账**：信用点自动付款，NextStep x 2 + Validate 确认
- **智能回退**：API 失败时自动回退到 DOM 加购

### 关键功能

- **SKU 收藏夹**：拦截成功自动保存所有商品（名称 + skuId），支持搜索、手动添加、滚轮翻页
- **伏击模式**：提前将商品加入购物车，T-30 自动预装填，T-0 只执行验证
- **时间校准**：NTP 采样 + 密度窗口过滤 + 自适应校准策略
- **CDP 浏览器模式**：连接本地 Edge 浏览器，无自动化检测标记
- **GUI 界面**：配置窗口 + 进度窗口双界面，含实时日志窗口
- **EXE 打包**：PyInstaller 打包，路径自动兼容

### 技术栈

- Python 3.8+（已测试兼容 Python 3.14）
- Playwright（CDP 模式连接本地 Edge）
- tkinter（GUI 界面）
- GraphQL API（直连 RSI 后端）

## 环境要求

### 必要环境

- **操作系统**：Windows 10/11（需要 Edge 浏览器）
- **Python**：3.8 或更高版本（开发时需要，EXE 不需要）
- **浏览器**：Microsoft Edge（保持登录状态）
- **网络**：稳定的互联网连接

## 安装步骤

### 1. 克隆项目

```bash
git clone git@github.com:cyaegha0425/RSI_MIEKCIK_BUY.git
cd RSI_MIEKCIK_BUY
```

### 2. 安装依赖

```bash
pip install playwright
python -m playwright install chromium
```

### 3. 首次登录

确保 Edge 浏览器已登录 RSI 账号，运行程序时会自动提取并保存登录状态。

## 使用方法

### 启动程序

```bash
python RSI_MIEKCIK_BUY.py
```

### EXE 用户

直接双击 `RSI_MIEKCIK_BUY.exe`，详见 `GUIDE.txt`。

### 基本配置流程

1. **选择输入模式**
   - **刷新拦截**：输入搜索关键词（如 "Kraken"）
   - **SKU ID 直购**：输入商品 SKU ID 和价格，可从收藏夹选择

2. **设置抢购时间**
   - 格式：YYYY-MM-DD HH:MM:SS

3. **点击开始**
   - 程序自动执行登录、预热、校准、抢购全流程

### 命令行参数

| 参数 | 说明 |
|------|------|
| --no-gui | 禁用 GUI，仅使用命令行模式 |
| --test | 测试模式（跳过最终付款确认） |

## 抢购流程

### 正面硬刚模式（默认）

```
登录 → 预热打开页面 → 提醒清空购物车 → 时间校准 → 等待抢购时间
→ 拦截模式：T-0刷新 → GraphQL拦截获取skuId → API加购
→ SKU模式：T-10开始API加购轮询
→ API加购失败 → 回退DOM加购
→ 极速结账：信用点应用 → NextStepx2 → Validate确认
```

### 伏击模式

```
登录 → 预热打开购物车 → 时间校准 → 等待 T-30 → 自动预装填
→ 等待 T-0 → 执行最终验证 → 付款成功/失败通知
```

## 目录结构

```
RSI_MIEKCIK_BUY/
├── modules/                    # 核心模块
│   ├── api_client.py           # GraphQL API 客户端
│   ├── browser.py              # 浏览器操作（CDP模式）
│   ├── calibration.py          # 时间校准
│   ├── config.py               # 配置常量和工具
│   ├── gui_config.py           # 配置窗口 GUI
│   ├── gui_progress.py         # 进度窗口 GUI
│   ├── sku_bookmarks.py        # SKU 收藏夹
│   ├── sku_interceptor.py      # SKU 拦截器
│   └── main.py                 # 主入口
├── scautobuy/                  # 运行数据目录
│   ├── rsi_cookies.json        # 保存的登录状态
│   └── rsi_buy.log             # 运行日志
├── images/                     # GUI 资源图片
├── sku_bookmarks.example.json  # 预置收藏夹
├── build.bat                   # Windows 构建脚本
└── README.md
```

## 注意事项

1. 提前清空购物车（正面硬刚模式）
2. Edge 浏览器已登录 RSI 账号
3. 信用点金额必须与商品价格精确匹配
4. 伏击模式确保购物车只有目标商品

## 免责声明

1. 本工具仅供学习交流使用
2. 请遵守 RSI 服务条款
3. 作者不对使用本工具造成的任何后果负责

---

咩咩蹄到好船来 V3.0.4
