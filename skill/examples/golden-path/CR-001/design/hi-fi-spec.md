# 高保真设计规格：用户登录日志功能

## 1. 架构设计

### 1.1 分层架构

```
Controller Layer (API)
    ↓
Service Layer (Business Logic)
    ↓
Repository Layer (Data Access)
    ↓
Database (PostgreSQL)
```

### 1.2 核心模块

- **LoginLogService**: 业务逻辑层
- **LoginLogRepository**: 数据访问层
- **LoginLogController**: API 控制器
- **LoginLogCleanupJob**: 定时清理任务

---

## 2. 数据库设计

### 2.1 表结构

```sql
CREATE TABLE login_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id VARCHAR(255) NOT NULL,
  username VARCHAR(255) NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ip_address VARCHAR(45) NOT NULL,
  user_agent TEXT NOT NULL,
  device_type VARCHAR(20) NOT NULL,
  status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'failure')),
  failure_reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_login_logs_user_time ON login_logs(user_id, timestamp DESC);
CREATE INDEX idx_login_logs_timestamp ON login_logs(timestamp);
CREATE INDEX idx_login_logs_status ON login_logs(status);
```

---

## 3. API 设计

### 3.1 查询登录历史

**端点**: `GET /api/admin/login-logs`

**中间件**: 
- AuthMiddleware (验证 Token)
- AdminMiddleware (验证管理员权限)

**处理流程**:
```
1. 验证管理员权限
2. 解析查询参数
3. 调用 LoginLogService.query()
4. 返回分页结果
```

---

## 4. 性能优化

### 4.1 异步记录

使用消息队列（或异步任务）记录日志，避免阻塞登录流程。

### 4.2 索引优化

复合索引 `(user_id, timestamp DESC)` 加速用户历史查询。

### 4.3 分页限制

最大 pageSize=100，防止单次查询过多数据。

---

## 5. 安全设计

### 5.1 权限控制

仅管理员可访问日志接口，通过中间件强制验证。

### 5.2 敏感信息保护

不记录密码明文，仅记录失败原因的抽象描述。

---

## 6. 监控和告警

### 6.1 关键指标

- 日志写入失败率
- 日志查询响应时间
- 定时清理执行状态

### 6.2 告警规则

- 日志写入失败率 > 1%
- 定时清理连续失败 2 次

---

**设计确认**: ✅ 已通过 DesignGate  
**下一步**: 进入实现阶段
