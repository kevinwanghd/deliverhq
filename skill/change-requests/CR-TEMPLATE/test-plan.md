# Test Plan: {{CR_ID}}

> 由 Test Agent 产出。测试策略与用例清单。

## 测试策略

### 测试层次
| 层次 | 覆盖范围 | 工具 | 目标覆盖率 |
|---|---|---|---|
| 单元测试 | Service 层方法 | xUnit / JUnit / pytest | > 80% |
| 集成测试 | API 端到端 | TestServer / Postman | 关键路径 100% |
| 契约测试 | 外部 API 对接 | 录制/回放 | 请求/响应格式 |

### 测试环境
- **单测**：内存数据库 / Mock
- **集成测试**：测试数据库（隔离）
- **性能测试**：预发布环境

## 单元测试用例

### 模块：{{ServiceName}}

#### 用例 1：正常流程
- **测试方法**：`{{MethodName}}_ValidInput_ReturnsSuccess`
- **Given**：{{前置条件}}
- **When**：调用 `{{MethodName}}({{params}})`
- **Then**：返回成功，结果符合预期

#### 用例 2：参数校验
- **测试方法**：`{{MethodName}}_InvalidInput_ThrowsException`
- **Given**：{{无效输入}}
- **When**：调用 `{{MethodName}}({{params}})`
- **Then**：抛出 `ValidationException`

#### 用例 3：边界条件
- **测试方法**：`{{MethodName}}_BoundaryCase_HandlesCorrectly`
- **Given**：{{边界输入}}
- **When**：调用 `{{MethodName}}({{params}})`
- **Then**：{{预期行为}}

## 集成测试用例

### API：POST /api/{{endpoint}}

#### 用例 1：端到端正常流程
- **Given**：数据库已准备测试数据
- **When**：发送 POST 请求，Body = {{json}}
- **Then**：HTTP 200，响应格式正确，数据库已更新

#### 用例 2：鉴权失败
- **Given**：无效 token
- **When**：发送 POST 请求
- **Then**：HTTP 401

#### 用例 3：并发场景
- **Given**：同时发起 N 个请求
- **When**：并发调用同一接口
- **Then**：无数据竞争，结果一致

## 契约测试（外部 API）

### 第三方服务 API
- [ ] {{API 名称}} 请求格式验证
- [ ] {{API 名称}} 响应解析验证
- [ ] 错误码处理（429/5xx）

### 内部服务 API
- [ ] 服务间接口契约验证
- [ ] 版本兼容性测试

## 性能测试

| 场景 | 指标 | 目标 | 测试方法 |
|---|---|---|---|
| {{接口}} | 响应时间 | P95 < {{X}} ms | 压测工具 |
| {{接口}} | 吞吐量 | > {{Y}} QPS | 压测工具 |

## 回归测试

- [ ] 运行全部现有测试
- [ ] 确认无测试失败
- [ ] 覆盖率不降低

## 测试数据准备

### 数据库
```sql
-- 测试数据准备
INSERT INTO {{table_name}} ({{columns}}) VALUES ({{values}});
```

### 外部依赖 Mock
```
// Mock 配置
{{mock_setup}}
```

## 测试执行计划

| 阶段 | 测试类型 | 负责人 | 状态 |
|---|---|---|---|
| 开发中 | 单元测试 | Dev | in-progress |
| 开发完成 | 集成测试 | Test Agent | pending |
| 提测前 | 回归测试 | CI | pending |
| 上线前 | 性能测试 | QA | pending |

## 测试阻断标准

以下情况阻断交付：
- 单元测试覆盖率 < 80%
- 关键路径集成测试失败
- 回归测试失败
- 性能指标未达标（P0 需求）

## 测试报告

执行完成后更新：
- 总用例数：{{N}}
- 通过：{{M}}
- 失败：{{K}}
- 覆盖率：{{X}}%
- 性能指标：{{达标 / 未达标}}
