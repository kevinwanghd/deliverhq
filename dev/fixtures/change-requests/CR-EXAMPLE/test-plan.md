# Test Plan: CR-EXAMPLE

> 由 Test Agent 产出。待办事项 CRUD 接口测试计划。

## 测试范围

### 单元测试
| 测试项 | 覆盖 |
|---|---|
| TodoService.create | 正常创建、title 为空校验 |
| TodoService.list | 分页、状态筛选、排除已删除 |
| TodoService.update | 正常更新、不存在返回 None |
| TodoService.delete | 软删除设置 deleted_at |

### 集成测试
| 测试项 | 方法 |
|---|---|
| POST /api/todos | 创建成功 201、校验失败 422 |
| GET /api/todos | 分页返回、筛选正确 |
| PATCH /api/todos/{id} | 更新成功 200、不存在 404 |
| DELETE /api/todos/{id} | 删除成功 204、不存在 404 |

### 性能测试
- 1000 条数据下 CRUD 操作 P95 < 100ms
- 100 并发请求无 5xx 错误

## 测试环境
- 数据库：PostgreSQL（测试专用 schema，每次运行前清空）
- 框架：pytest + httpx（AsyncClient）

## 测试结果

| 类型 | 通过 | 失败 | 跳过 |
|---|---|---|---|
| 单元测试 | 12 | 0 | 0 |
| 集成测试 | 8 | 0 | 0 |
| 性能测试 | 2 | 0 | 0 |

**总计**: 22 pass, 0 fail
