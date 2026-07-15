# Lo-Fi Spec: CR-EXAMPLE

> 本 CR 为纯 API 接口，无 UI 界面，此文件仅作结构占位。

## 说明
- ui_type: api_only
- 本 CR 不涉及用户界面设计
- 接口文档通过 FastAPI 自动生成的 OpenAPI/Swagger 页面提供
- 如需 API 调试界面，使用 `/docs`（Swagger UI）或 `/redoc`

## API 接口概览

```
POST   /api/todos      — 创建待办事项
GET    /api/todos      — 查询列表（分页）
PATCH  /api/todos/{id} — 更新
DELETE /api/todos/{id} — 删除（软删除）
```
