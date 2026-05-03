# RSI_MIEKCIK_BUY - AI 开发文档 V3.0.2

> 本文档面向 AI 助手，提供项目架构、关键约束和开发指南。人类用户请阅读 README.md。

## 项目概述

RSI 星际公民商店自动抢购工具。全 API 架构，两种输入模式（SKU ID 直购 + 刷新拦截），Playwright CDP 连接本地 Edge，tkinter GUI。

## 架构

### 核心文件

| 文件 | 职责 |
|------|------|
| `modules/main.py` | 主流程编排：登录→预热→校准→等待→抢购→结账 |
| `modules/api_client.py` | GraphQL API 客户端，所有RSI后端交互 |
| `modules/config.py` | 全局常量、BASE_PATH、cookie管理、日志队列 |
| `modules/gui_config.py` | 配置窗口：模式选择、SKU/关键词/价格输入、收藏夹、高级设置 |
| `modules/gui_progress.py` | 进度窗口：倒计时、步骤状态、日志按钮 |
| `modules/sku_interceptor.py` | GraphQL响应拦截器，从网络请求提取skuId |
| `modules/sku_bookmarks.py` | SKU收藏夹CRUD，首次自动从example复制 |
| `modules/calibration.py` | NTP时间校准：采样→RTT过滤→密度窗口→偏移计算 |
| `modules/browser.py` | Playwright CDP连接Edge，浏览器生命周期管理 |

### 线程模型

- **主线程**：tkinter mainloop，queue+after()轮询处理GUI更新
- **抢购线程**：Playwright操作+API调用，零tkinter接触，只put消息队列
- **关键约束**：Python 3.14 tkinter连after_idle都不允许子线程调用，必须queue+after()

### 消息队列

- `_gui_queue`：抢购线程→GUI，50ms轮询批量处理
- `config._log_queue`：日志队列，QueueHandler推流，日志窗口200ms轮询

### after回调管理

- `_after_ids` 集合跟踪所有after回调ID
- 退出时 `_cancel_all_after()` 批量cancel
- mainloop退出后再cancel+update清理残留
- **必须跟踪**：否则Tcl报 `invalid command name "xxx_update_countdown"`

## 关键约束（踩坑记录）

### Playwright

- timeout单位是**毫秒**，所有timeout参数必须乘以1000
- `page.evaluate()` 只接受1个额外参数，多参数用dict传递
- CDP连接的 `ctx.pages[0]` 是Edge预存tab，Playwright事件hook不上去，必须 `ctx.new_page()`
- JS正则 `$` 和 `\d` 在Python字符串里是无效转义，必须写成 `\\$` 和 `\\d`

### RSI API

- `GRAPHQL_URL`: `https://robertsspaceindustries.com/graphql`
- CartAddInput 只有 `skuId` 字段，没有 `quantity`
- 信用点金额必须精确匹配商品价格，否则结账失败
- RSI商店页面：不带 `keywords=` 走SSR（无GraphQL），带 `keywords=` 走SPA+GraphQL
- **逆向API必须先抓真实请求，严禁猜测**

### GUI

- GUI颜色：`GUI_BG_COLOR=#A8B4D4`, `GUI_TITLE_COLOR=#1a3a5c`, `GUI_TEXT_COLOR=#2d2d2d`
- 窗口630×780
- 所有GUI更新必须走queue，抢购线程零tkinter接触
- 伏击模式隐藏不需要的输入行（SKU/搜索/价格/排除）
- 日志窗口在过程界面，不在配置界面
- 删除确认弹窗用自定义Toplevel + topmost + grab_set（messagebox不置顶）
- 收藏夹滚轮用Enter/Leave + bind_all方式（子控件上也要能滚）

### PyInstaller

- `--onefile` 模式下 `__file__` 指向临时目录
- 必须用 `sys.frozen` 判断 + `sys.executable` 定位EXE目录
- `config.BASE_PATH` 统一所有文件路径：COOKIE_FILE、LOG_FILE、SCREENSHOT_DIR、config_file、BOOKMARKS_FILE
- 数据文件通过build.bat手动复制到dist，不依赖PyInstaller打包

### 时间校准策略

- T-0已过→跳过校准立即开抢
- <8秒→跳过校准
- 8~15秒→快速3次采样
- ≥15秒→正常10次采样

### 耗时计算

- SKU模式：从 `attempt_start`（T-10s开始加购）起算，T-0前完成显示"提前X秒"
- 伏击模式：从T-0执行起算，不是从target时间

## 两种输入模式

### 刷新拦截模式 (intercept)

1. 用户输入搜索关键词（如"Kraken"）
2. T-0刷新RSI商店页面
3. GraphQL拦截器捕获响应，提取skuId
4. API加购 → 极速结账
5. 拦截到的所有商品自动保存到收藏夹

### SKU ID 直购模式 (sku)

1. 用户直接输入skuId和价格（或从收藏夹选择）
2. T-10s开始API加购轮询
3. API加购失败→回退DOM加购
4. 极速结账

### 伏击模式（两种模式通用）

1. 用户提前将商品加入购物车
2. T-30自动预装填（信用点+地址）
3. T-0只执行CartValidateCartMutation
4. page.goto改用JS setTimeout非阻塞

## 极速结账流程

```
AddCreditMutation → NextStepMutation(进入结账) → NextStepMutation(确认) → CartValidateCartMutation(付款)
```

## 收藏夹

- `sku_bookmarks.example.json` 预置商品，首次使用自动复制为 `sku_bookmarks.json`
- `sku_bookmarks.json` 不跟仓库走（gitignore）
- 支持搜索、选择、删除、手动添加
- 删除确认弹窗自定义Toplevel（置顶+grab）

## 已知问题

- **Fiber在Windows Edge上不生效**：Linux Chrome能找到item.id，Edge递归6层搜不到。拦截器兜住，非紧急
- **sku_probe.py首次goto拦截不到**：主流程OK，非紧急

## Debug工作流

**必须严格遵守**：记录问题→总结反馈→确认方案→实施修改

## 版本历史

- V3.0.0：全API架构重构
- V3.0.1：queue+after轮询重构、after回调退出保护、校准自适应、导航冲突修复、付款非阻塞跳转、Edge bing.com防白屏
- V3.0.2：GUI日志窗口、收藏夹bug修（搜索/删除置顶/新建/滚轮翻页）、PyInstaller路径兼容、SKU/伏击耗时修复

---

AI 开发文档 V3.0.2
