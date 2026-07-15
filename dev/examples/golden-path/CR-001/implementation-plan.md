# 实现计划：用户登录日志功能

## 1. 实现步骤

### Step 1: 数据库迁移
- 创建 `login_logs` 表
- 创建索引
- **预估时间**: 1 小时

### Step 2: Repository 层
- 实现 `LoginLogRepository.create()`
- 实现 `LoginLogRepository.query()`
- **预估时间**: 2 小时

### Step 3: Service 层
- 实现 `LoginLogService.log()`
- 实现 `LoginLogService.query()`
- **预估时间**: 2 小时

### Step 4: Controller 层
- 实现 `GET /api/admin/login-logs`
- 添加权限中间件
- **预估时间**: 2 小时

### Step 5: 集成到登录流程
- 在 `AuthService.login()` 成功后调用日志记录
- 在 `AuthService.login()` 失败后调用日志记录
- **预估时间**: 1 小时

### Step 6: 定时清理任务
- 实现 `LoginLogCleanupJob`
- 配置 cron 表达式
- **预估时间**: 2 小时

### Step 7: 测试
- 单元测试（覆盖率 100%）
- 集成测试
- **预估时间**: 4 小时

---

## 2. 文件清单

**新增文件**:
- `src/repositories/LoginLogRepository.ts`
- `src/services/LoginLogService.ts`
- `src/controllers/LoginLogController.ts`
- `src/jobs/LoginLogCleanupJob.ts`
- `migrations/YYYYMMDD_create_login_logs.sql`
- `tests/unit/LoginLogService.test.ts`
- `tests/integration/login-logs.test.ts`

**修改文件**:
- `src/services/AuthService.ts` (集成日志记录)
- `src/routes/admin.ts` (添加日志查询端点)

---

## 3. 测试策略

### P0 测试用例

1. ✅ 登录成功时记录日志
2. ✅ 登录失败时记录日志
3. ✅ 管理员可查询登录历史
4. ✅ 非管理员无法访问日志接口
5. ✅ 定时清理删除 90 天前的日志

---

## 4. 风险和依赖

**依赖**:
- PostgreSQL 已部署
- 定时任务框架已配置

**风险**:
- 异步日志记录失败：添加重试机制
- 高并发下性能：使用连接池 + 索引优化

---

**实现计划确认**: ✅  
**下一步**: 开始编码
