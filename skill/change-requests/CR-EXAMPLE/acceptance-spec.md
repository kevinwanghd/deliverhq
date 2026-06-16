# Acceptance Spec: CR-EXAMPLE

> 由 Spec Agent 生成，定义可验证的验收条件。

## 验收条件

### AC-1: 创建待办事项
- 请求 `POST /api/todos` 携带 `{title, description, due_date}`
- 返回 201 + 创建的待办事项（含 id、created_at）
- title 为空时返回 422 错误

### AC-2: 查询待办事项列表
- 请求 `GET /api/todos?page=1&size=20&status=pending`
- 返回分页结果 `{items, total, page, size}`
- 支持 status 筛选：pending / done / all

### AC-3: 更新待办事项
- 请求 `PATCH /api/todos/{id}` 携带需更新的字段
- 返回 200 + 更新后的完整对象
- id 不存在时返回 404

### AC-4: 删除待办事项
- 请求 `DELETE /api/todos/{id}`
- 返回 204（软删除，设置 deleted_at）
- 已删除的事项不出现在列表查询中

### AC-5: 非功能验收
- P95 响应时间 < 100ms（1000 条数据下）
- 并发 100 请求无错误
- OpenAPI 文档自动生成且可访问

## 模糊点澄清

| 问题 | 结论 | 决策人 |
|---|---|---|
| 软删除是否可恢复 | 暂不支持恢复，后续 CR 处理 | 产品经理 |
| 分页默认大小 | 20 条/页，最大 100 | 技术负责人 |
| due_date 是否必填 | 选填，默认为空 | 产品经理 |
