# L1：项目总览

AI 入场的"大堂导览"。

## 文件

- `overview.md` — 模块清单 + 职责 + 技术栈（< 5KB）

## 用途

- AI 首次入场时读取，了解项目有哪些模块、各自负责什么
- 五步定位法第 1 步：L1 总览里 1 秒选出模块（不用 grep）
- 与 L2 模块 wiki 配合，实现 ~300× Token 压缩比

## 维护规则

- 只改 `desc` 和 `module_id`，其他内容由脚本自动跟随
- SHA 基线缓存（`.review_cache.json`）：文件变化时自动 flag "待复核"
- pre-commit hook 阻断：退出码 1 = 有 stale 信号 → 阻止提交

## 示例

```markdown
| module_id | 模块名 | root_dirs | desc |
|-----------|--------|-----------|------|
| auth | 认证模块 | src/auth/ | 用户登录/登出/Token 管理 |
| orders | 订单模块 | src/orders/ | 订单创建/查询/取消 |
```
