# 运行时验证闭环

> 来源：企业微信团队"AI代码生成率94%"经验总结。
> 核心原则：**AI 从"改完代码"到"敢说做完了"经历多道把关，每道关都有机器可校验的产物。**

## 两道闸门

| 闸门 | 验证对象 | 判据 |
|------|----------|------|
| 编译验证 | 代码层 | 退出码 0 + `build_report.txt` |
| 模拟器验证 | 运行时 + 视觉 | 截图 + `runtime.log` 日志命中 |

**全部由文件证明，不靠 AI 自报。**

## 闸门一：编译验证

### A/B 分类

| 类型 | 问题 | 处理 |
|------|------|------|
| A 可自修复 | 缺分号、标识符未声明、类型不匹配、枚举漏 case | 自动修复，最多 3 轮 |
| B 需用户介入 | BUILD 配置错、链接错误、三方 framework | 强制停下，报告用户 |

### Red Line

> ⛔ **RL-C01**：编译必须通过。`bazel build` / `flutter build` / `npm run build` 退出码 0 是唯一判据。
> 自修复硬上限 3 轮：超过 3 轮仍编译不过 → 强制停下报告用户。

### sentinel 文件 = 成功的唯一判据

```bash
# ❌ 错误：不靠 stdout
$ npm run build && echo "SUCCESS"
SUCCESS

# ✅ 正确：靠文件存在证明
$ npm run build
$ test -f build_report.txt && test -f dist/bundle.js && echo "SUCCESS"
SUCCESS
```

## 闸门二：模拟器验证

### 路径推导法

从 git diff 反推 UI 验证路径：

| 改动类型 | 验证终点 |
|----------|----------|
| 改 UI（View/Controller） | 该 UI 的真实可见状态（截图能看到） |
| 改数据/解析 | UI 上能体现该数据的页面 + 抓日志确认数据流 |
| 改纯逻辑 | `XYZLOG_WARN` 日志关键字命中 |

### 桥梁法（跨文件变量赋值溯源）

| 模式 | 代码示例 | 溯源方式 |
|------|----------|----------|
| 通知 | `postNotificationName:` | 搜索通知中心 |
| KVO | `RACObserve(` | 搜索 KVO 监听 |
| Delegate | `<XxxDelegate> =` | 搜索代理设置 |

### A/B/C 三类诊断

| 类型 | 问题 | 处理 |
|------|------|------|
| A 真问题 | 代码 bug | 回「实现」阶段 |
| B 路径不通 | 验证设计错 | 修订 verify_plan 或跳过 |
| C 脚本/时序 | 可自修复 | 阶段内重试 ≤ 2 轮 |

### Red Line

> ⛔ **RL-S05**：视觉对齐核对。UI 改动必须逐项核对数值，未对齐 ≥ 1 → FAIL。

## 运行时小坑清单

| 死角 | 为什么不行 | 替代方案 |
|------|-----------|----------|
| 边缘左滑返回 | UIScreenEdgePanGestureRecognizer 要求真实时序 | 找 nav_back_arrow 的 AX 标识 + tap |
| 3D Touch / 力度长按 | 模拟器不支持力度感应 | 用菜单按钮/开 debug 后门 |
| 物理像素 ↔ 逻辑像素 | 截图是物理像素，idb ui tap 吃逻辑像素 | scale = logical_w / physical_w 动态换算 |
| 登录态丢失 | simctl uninstall 清沙盒会丢登录 | 同 bundle id simctl install 不动沙盒 |
| shell heredoc 里 !r | zsh 当 history expansion | 改用 `repr(x)` 或独立 .py 文件 |

## 验证产物要求

每道闸门必须有机器可校验的产物：

| 产物 | 来源 | 验证方式 |
|------|------|----------|
| `build_report.txt` | 编译命令输出 | 退出码 0 |
| 截图 | 模拟器截图 | 人工确认或视觉比对 |
| `runtime.log` | 运行时日志 | 日志关键字命中 |
| `result.md` | 验证结果 | 状态字段 = pass/fail |

---

*本文件固化自企业微信团队"AI代码生成率94%"文章。*
