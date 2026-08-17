# 5维搜索矩阵

> 把"产品语言"翻译成"代码关键词"的5个维度。

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

| 产品描述 | Python/Node | Go/Java | 说明 |
|---------|-------------|---------|------|
| 点击按钮 | `on_click`, `handle_click` | `onClick`, `actionPerformed` | 事件处理器 |
| 输入变化 | `on_change`, `handle_input` | `onChange`, `valueChanged` | 表单输入 |
| 页面加载 | `on_load`, `useEffect` | `onCreate`, `onStart` | 生命周期 |
| 列表选择 | `on_select`, `handle_item_select` | `onItemSelected` | 列表项选中 |

### 维度②：功能语义英文同义词

| 产品意图 | 英文同义词（搜索用） |
|---------|------------------|
| 创建/新增 | create, add, new, insert, initialize |
| 读取/查询 | get, fetch, load, read, query, find |
| 更新/修改 | update, modify, edit, change, patch |
| 删除/移除 | delete, remove, destroy, drop, clear |
| 列表/列表 | list, query, search, filter, browse |
| 详情/查看 | detail, view, get, read, info |
| 提交/保存 | submit, save, commit, persist, post |

### 维度③：项目命名习惯

| 命名风格 | 示例 | 适用场景 |
|---------|------|---------|
| `get_*` | `get_user()`, `get_by_id()` | 获取单个对象 |
| `list_*` | `list_orders()`, `list_items()` | 获取列表 |
| `create_*` | `create_user()`, `create_order()` | 创建资源 |
| `update_*` | `update_profile()`, `update_status()` | 更新资源 |
| `delete_*` | `delete_user()`, `delete_item()` | 删除资源 |
| `handle_*` | `handle_click()`, `handle_error()` | 事件处理 |
| `on_*` | `on_mount()`, `on_change()` | 生命周期/回调 |

### 维度④：协议/代理模式

| 场景 | Python | TypeScript/Node | 说明 |
|------|--------|-----------------|------|
| 事件监听 | `add_listener()` | `on()`, `addEventListener()` | 事件订阅 |
| 中间件 | `middleware` | `middleware` | 请求拦截 |
| 回调 | `callback` | `callback`, `Promise` | 异步回调 |
| Hook | `use_*` | `useEffect`, `useState` | React Hooks |

### 维度⑤：通知/回调模式

| 场景 | Python | TypeScript/Node | 说明 |
|------|--------|-----------------|------|
| 事件发射 | `emit()` | `emit()`, `emit()` | 事件发射 |
| 全局状态 | `set_state()` | `setState()` | 状态更新 |
| 路由跳转 | `navigate()` | `router.push()` | 页面导航 |
| 通知提示 | `show_toast()` | `notification.show()` | 用户提示 |

## 联想 vs 引用边界

> ⚠️ **RL-SM-01**：联想用于搜索，引用用于决策。

| 用途 | 依据 |
|------|------|
| 搜索 | L2 模块 wiki + 本 search-matrix |
| 决策 | glossary.md + 文档原文 + 用户原话 |

禁止凭语义联想扩大改动范围。
