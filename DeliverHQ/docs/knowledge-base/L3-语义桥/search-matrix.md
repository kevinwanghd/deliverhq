# 5维搜索矩阵

> 把"产品语言"翻译成"代码关键词"的5个维度。
> 用于五步定位法第 3 步（关键词搜索）和第 4 步（调用链追踪）。

## 使用方法

当用户说"XXX 功能"时，按以下5个维度展开搜索：

| 维度 | 出发点 | 命中目标 | 优先级 |
|------|--------|---------|--------|
| ① 平台 API | 标准系统 API | 平台事件方法名 | P1 |
| ② 功能语义 | 产品意图的英文同义词 | 功能相关关键词 | P1 |
| ③ 命名习惯 | 项目里的命名前缀 | 符合项目风格的代码 | P1 |
| ④ 协议/代理 | 谁通知谁 | 代理模式下的方法 | P2 |
| ⑤ 通知/回调 | 跨模块通信 | 通知中心/事件名 | P2 |

## 维度详解

### 维度①：平台 API 事件方法

| 产品描述 | 平台 | 搜索关键词 |
|---------|------|----------|
| 点击某行 | iOS | `didSelectRowAtIndexPath` / `handleTapGesture` |
| 点击某行 | Android | `onItemClick` / `setOnClickListener` |
| 滑动列表 | iOS | `scrollViewDidScroll` |
| 输入框变化 | iOS | `textFieldDidChange` |

### 维度②：功能语义英文同义词

| 产品意图 | 英文同义词（搜索用） |
|---------|------------------|
| 提示/警告 | tips / banner / warning / notice / alert |
| 弹窗 | modal / popup / dialog / sheet |
| 红点未读 | badge / unread / count |
| 刷新 | refresh / reload / pull-to-refresh |

### 维度③：项目命名习惯

| 命名风格 | 前缀示例 | 适用场景 |
|---------|---------|---------|
| show* | `showAlert()` / `showModal()` | 展示类方法 |
| handle* | `handleTap()` / `handleInput()` | 事件处理方法 |
| on* | `onDataReceived()` / `onError()` | 回调方法 |
| goto* | `gotoDetail()` / `gotoSettings()` | 导航方法 |

### 维度④：协议/代理模式

| 产品描述 | iOS 代理 | Android 接口 |
|---------|---------|-------------|
| 表格点击 | `UITableViewDelegate` | `AdapterView.OnItemClickListener` |
| 网络回调 | `NSURLSessionDelegate` | `Callback` |

### 维度⑤：通知/回调模式

| 场景 | iOS 通知 | Android 广播/EventBus |
|------|---------|---------------------|
| 登录成功 | `NotificationName.loginSuccess` | `EventBus.loginSuccess` |
| 数据刷新 | `NotificationName.dataRefreshed` | `EventBus.dataRefreshed` |

## 联想 vs 引用边界

> ⛔ **RL-SM-01**：联想用于搜索，引用用于决策。
> - 联想依据：L2 模块 wiki + 本 search-matrix，关键词命中率 > 80% 时启用
> - 引用依据：glossary.md + 文档原文 + 用户原话
> - 禁止凭语义联想扩大改动范围
