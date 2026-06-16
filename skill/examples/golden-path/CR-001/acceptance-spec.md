# Acceptance Spec: 用户登录日志功能

**作者**: Dev Team  
**审核人**: Tech Lead  
**版本**: v1.0  
**状态**: Approved

---

## 1. Data Spec（数据规格）

### 1.1 核心实体

**LoginLog（登录日志）**:
```typescript
interface LoginLog {
  id: string;              // 日志 ID（UUID）
  userId: string;          // 用户 ID
  username: string;        // 用户名（冗余，便于查询）
  timestamp: Date;         // 登录时间（ISO 8601）
  ipAddress: string;       // IP 地址（IPv4/IPv6）
  userAgent: string;       // User-Agent 字符串
  deviceType: string;      // 设备类型：desktop | mobile | tablet
  status: LoginStatus;     // 登录状态：success | failure
  failureReason?: string;  // 失败原因（仅 failure 时）
  createdAt: Date;         // 记录创建时间
}

enum LoginStatus {
  SUCCESS = "success",
  FAILURE = "failure"
}
```

### 1.2 存储规格

- **存储方式**: 关系型数据库（PostgreSQL）
- **表名**: `login_logs`
- **索引**:
  - 主键: `id`
  - 复合索引: `(userId, timestamp DESC)` — 用户历史查询
  - 索引: `timestamp` — 时间范围查询
  - 索引: `status` — 状态过滤

### 1.3 数据保留策略

- **保留期**: 90 天
- **清理机制**: 定时任务每天凌晨 2:00 删除 90 天前的记录
- **归档**: 不归档（业务要求只保留 90 天）

---

## 2. Interface Spec（接口规格）

### 2.1 记录登录日志（内部接口）

**函数签名**:
```typescript
async function logLogin(params: {
  userId: string;
  username: string;
  ipAddress: string;
  userAgent: string;
  status: LoginStatus;
  failureReason?: string;
}): Promise<LoginLog>
```

**调用时机**:
- 登录成功: `AuthService.login()` 成功后
- 登录失败: `AuthService.login()` 捕获异常后

**性能要求**: < 100ms（异步记录，不阻塞登录流程）

### 2.2 查询登录历史（管理接口）

**端点**: `GET /api/admin/login-logs`

**请求参数**:
```typescript
{
  userId?: string;           // 用户 ID（可选）
  startDate?: string;        // 开始时间（ISO 8601）
  endDate?: string;          // 结束时间（ISO 8601）
  status?: LoginStatus;      // 状态过滤（可选）
  page: number;              // 页码（默认 1）
  pageSize: number;          // 每页条数（默认 20，最大 100）
}
```

**响应**:
```typescript
{
  total: number;             // 总记录数
  page: number;              // 当前页码
  pageSize: number;          // 每页条数
  data: LoginLog[];          // 日志列表
}
```

**权限要求**: 仅管理员角色可访问

**性能要求**: < 500ms（带索引查询）

---

## 3. Behavior Spec（行为规格）

### 场景 1: 用户登录成功

**前置条件**: 
- 用户存在
- 密码正确

**操作步骤**:
1. 用户提交登录请求（用户名 + 密码）
2. 系统验证成功
3. 系统返回登录 Token
4. **系统异步记录登录日志**（status=success）

**预期结果**:
- 日志记录包含：userId, username, timestamp, ipAddress, userAgent, deviceType, status=success
- 日志在 100ms 内写入数据库
- 用户登录流程不受日志记录影响

**P0 测试**: ✅ 必须覆盖

---

### 场景 2: 用户登录失败（密码错误）

**前置条件**: 
- 用户存在
- 密码错误

**操作步骤**:
1. 用户提交登录请求（用户名 + 错误密码）
2. 系统验证失败
3. 系统返回错误信息
4. **系统异步记录登录日志**（status=failure, failureReason="Invalid password"）

**预期结果**:
- 日志记录包含：userId, username, timestamp, ipAddress, userAgent, deviceType, status=failure, failureReason
- 不暴露失败原因给前端（仅记录日志）

**P0 测试**: ✅ 必须覆盖

---

### 场景 3: 管理员查询登录历史

**前置条件**: 
- 管理员已登录
- 目标用户有登录记录

**操作步骤**:
1. 管理员访问 `/api/admin/login-logs?userId=<uid>&page=1&pageSize=20`
2. 系统验证管理员权限
3. 系统返回该用户的登录历史

**预期结果**:
- 返回分页数据，按时间倒序
- 包含成功和失败的记录
- 响应时间 < 500ms

**P0 测试**: ✅ 必须覆盖

---

### 场景 4: 定时清理过期日志

**前置条件**: 
- 存在 90 天前的日志记录

**操作步骤**:
1. 定时任务在凌晨 2:00 触发
2. 系统删除 `timestamp < (now - 90 days)` 的记录

**预期结果**:
- 90 天前的记录被删除
- 90 天内的记录保留
- 操作完成后记录清理日志

**P0 测试**: ✅ 必须覆盖

---

## 4. 非功能性需求

### 4.1 性能

- 登录日志记录: < 100ms（异步）
- 日志查询: < 500ms
- 定时清理: < 10 秒（预估 100 万条记录）

### 4.2 安全

- 日志接口仅管理员可访问
- 不在日志中记录密码明文
- IP 地址脱敏展示（可选）

### 4.3 可观测性

- 日志记录失败时告警
- 定时清理失败时告警
- 记录清理数量到监控系统

---

## 5. Open Questions

所有问题已解决：

- ~~Q1: 是否需要记录登出日志？~~ → **Resolved**: 暂不需要，仅记录登录
- ~~Q2: 失败原因是否暴露给用户？~~ → **Resolved**: 不暴露，仅内部日志
- ~~Q3: 是否需要导出功能？~~ → **Resolved**: v1.0 暂不需要，后续迭代

---

## 6. 依赖和风险

### 依赖
- PostgreSQL 数据库
- 定时任务框架（cron / scheduled job）

### 风险
- **高并发下日志写入性能**: 使用异步队列缓解
- **日志表增长过快**: 90 天清理策略 + 索引优化

---

**规格确认**: ✅ 已通过 SpecGate  
**下一步**: 进入设计阶段
