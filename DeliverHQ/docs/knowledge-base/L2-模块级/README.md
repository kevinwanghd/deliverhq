# L2：模块级——文件粒度的"街道地图"

每个模块一个 `<module>.md` 文件，顶部有机器可读的元数据。

## 文件结构

```
L2-模块级/
├── README.md          # 本文件
├── L2-template.md    # 模块 wiki 模板
└── <module>.md       # 各模块文件（如 auth.md, orders.md）
```

## 元数据格式（每文件顶部必须有）

```yaml
---
module_id: auth
module_name: 认证模块
root_dirs:
  - src/auth/
  - tests/auth/
desc: 用户登录/登出/Token 管理
last_reviewed: 2026-08-15
sha_baseline: "abc123"
---
```

## 目录登记格式

每个模块文件包含：

```markdown
## 文件登记表

### Controller
| 文件 | 职责 | 关键方法 |
|------|------|---------|
| | | |

### Service
| 文件 | 职责 | 关键方法 |
|------|------|---------|
| | | |
```

## 用途

- 五步定位法第 2 步：从 L2 模块 wiki 里 5 秒锁定文件（不用读源码）
- AI 搜索前先查 L2 文件列表，精确定位到模块

## 维护规则

- 新增文件时在对应区域补充
- 删除文件时标记 `[已废弃]` 而非直接删除
- SHA 基线缓存：变化时自动 flag "待复核"
