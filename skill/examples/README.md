# Examples 目录说明

## 目录结构

```
examples/
├── self-development/  # DeliverHQ 自身开发的真实 CR
│   ├── CR-001/        # 升级到 v4.6 框架
│   ├── CR-002/        # 实现 Worktree 隔离
│   └── CR-003/        # 实现 Loop Mode
└── README.md          # 本文件
```

---

## 用途

**examples/** 目录存放真实项目的示例 CR，用于：

1. **展示真实用例** - 展示 DeliverHQ 在实际项目中的使用方式
2. **隔离污染** - 防止真实项目术语污染框架模板
3. **学习参考** - 为新用户提供参考案例

---

## 与模板的区别

| 类型 | 位置 | 用途 | 污染检查 |
|------|------|------|---------|
| **框架模板** | `change-requests/CR-TEMPLATE/` | 通用模板，用户复制使用 | ✅ 严格检查 |
| **正例示例** | `change-requests/CR-EXAMPLE/` | 展示完整 CR 结构 | ✅ 严格检查 |
| **反例示例** | `change-requests/CR-BLOCKED-EXAMPLE/` | 展示应被 Gate 阻断的 CR | ✅ 严格检查 |
| **真实示例** | `examples/self-development/CR-*/` | 真实项目 CR | ❌ 不检查（允许项目特定术语） |

---

## selftest 行为

- `change-requests/` 目录下的 CR-TEMPLATE、CR-EXAMPLE、CR-BLOCKED-EXAMPLE 会被严格检查污染
- `examples/` 目录整体被排除，允许包含项目特定术语
- 这样既保证框架模板纯净，又保留真实示例的参考价值

---

## 添加新示例

如果要添加新的真实项目示例：

```bash
# 1. 创建分类目录（如果不存在）
mkdir -p examples/my-project

# 2. 移动真实 CR
mv change-requests/CR-XXX examples/my-project/

# 3. selftest 会自动排除 examples 目录
python scripts/selftest.py
```

---

**重要**: 不要将 `examples/` 中的 CR 作为新 CR 的模板，请使用 `change-requests/CR-TEMPLATE/`。
