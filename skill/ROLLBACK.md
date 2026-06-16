# 回滚指南（Rollback Guide）

> 当已交付的 Change Request 出现问题需要回滚时，参考本指南执行安全回滚。

## 回滚场景

### 场景 1：生产环境发现严重 Bug
- **症状**：已上线功能导致数据错误、性能下降、服务中断
- **决策标准**：影响核心业务流程、无法通过热修复解决、影响多个用户
- **回滚范围**：代码 + 数据库 schema + 配置文件

### 场景 2：功能与需求不符
- **症状**：上线后发现理解偏差，实现与需求方期望不一致
- **决策标准**：需求方明确拒绝验收、需大幅返工（> 2 天工作量）
- **回滚范围**：代码 + UI（如有）

### 场景 3：性能严重劣化
- **症状**：响应时间增加 > 50%、数据库慢查询、CPU/内存占用异常
- **决策标准**：影响用户体验、触发告警阈值
- **回滚范围**：代码 + 数据库索引

## 回滚前检查清单

### 必须检查项
- [ ] **确认 CR-ID**：明确要回滚哪个 Change Request（从 `delivery/YYYY-MM/` 目录查找）
- [ ] **检查依赖关系**：查看 `traceability.yml`，确认是否有后续 CR 依赖此 CR
- [ ] **备份当前状态**：创建 Git tag（如 `before-rollback-CR-XXX`）和数据库快照
- [ ] **评估影响范围**：回滚是否影响其他功能（查看 `docs/interfaces.md` 接口依赖）
- [ ] **通知相关方**：产品经理、QA、运维团队

### 获取回滚信息
```bash
# 1. 查找已归档的 CR
ls delivery/2026-06/CR-*

# 2. 查看 CR 的 writeback-report.md
cat delivery/2026-06/CR-XXX/writeback-report.md

# 3. 查看代码变更范围（从 traceability.yml）
cat delivery/2026-06/CR-XXX/traceability.yml
```

## 回滚步骤

### Step 1: 代码回滚

#### 方法 A：Git Revert（推荐）
```bash
# 1. 从 writeback-report.md 找到相关 commit SHA
git log --oneline | grep "CR-XXX"

# 2. 创建回滚分支
git checkout -b rollback-CR-XXX

# 3. 使用 git revert（保留历史）
git revert <commit-sha-1> <commit-sha-2> ...

# 4. 验证回滚后代码编译通过
dotnet build

# 5. 提交并创建 PR
git push -u origin rollback-CR-XXX
gh pr create --title "Rollback CR-XXX: <reason>" --body "回滚原因：<详细说明>"
```

#### 方法 B：Cherry-pick 旧版本（不推荐，仅紧急情况）
```bash
# 找到 CR 实施前的 commit
git log --before="2026-06-01" --oneline

# Cherry-pick 旧版本代码
git cherry-pick <old-commit-sha>
```

### Step 2: 数据库回滚

#### 2.1 检查是否有 Schema 变更
从 `implementation-plan.md` 查看是否有数据库迁移：
```bash
cat delivery/2026-06/CR-XXX/implementation-plan.md | grep -A 10 "数据模型"
```

#### 2.2 回滚 NoSQL 集合
```javascript
// 如果新增了集合，删除集合
use my_database
db.new_collection.drop()

// 如果修改了字段，运行反向迁移脚本（需预先准备）
db.users.updateMany({}, { $unset: { newField: "" } })
```

#### 2.3 回滚 MySQL 表
```sql
-- 如果新增了表，删除表
DROP TABLE IF EXISTS login_logs;

-- 如果新增了字段，删除字段
ALTER TABLE users DROP COLUMN new_field;

-- 如果修改了数据，从备份恢复（需 DBA 协助）
-- RESTORE FROM BACKUP ...
```

### Step 3: 配置文件回滚
```bash
# 检查 CR 是否修改了配置文件
git diff <before-commit> <after-commit> -- configs/

# 手动恢复配置文件（如有变更）
git checkout <before-commit> -- configs/appsettings.Production.json
```

### Step 4: 依赖包回滚
```bash
# 检查是否新增/升级了 NuGet 包
git diff <before-commit> <after-commit> -- *.csproj

# 回滚包版本
dotnet remove package NewPackage
dotnet add package OldPackage --version 1.0.0
```

### Step 5: 验证回滚结果
- [ ] 代码编译通过：`dotnet build`
- [ ] 单元测试通过：`dotnet test`
- [ ] 集成测试通过（在测试环境）
- [ ] 手动回归测试关键路径
- [ ] 性能指标恢复正常（对比回滚前后监控数据）

### Step 6: 部署回滚
```bash
# 部署到测试环境验证
# ...

# 部署到生产环境
# ...

# 验证生产环境
curl https://api.example.com/health
```

### Step 7: 更新文档
```bash
# 1. 在原 CR 目录添加回滚记录
echo "## 回滚记录\n\n- 回滚日期: $(date)\n- 回滚原因: <原因>\n- 回滚方式: git revert\n- 回滚执行人: <姓名>" >> delivery/2026-06/CR-XXX/ROLLBACK.md

# 2. 更新 docs/decisions.md 记录决策
echo "- $(date): 回滚 CR-XXX，原因：<简要说明>" >> DeliverHQ/docs/decisions.md

# 3. 更新 docs/mistake-book.md 记录教训
cat >> DeliverHQ/docs/mistake-book.md <<EOF

### 错误：CR-XXX 回滚事件
- **日期**：$(date +%Y-%m-%d)
- **问题**：<问题描述>
- **根因**：<根本原因分析>
- **改进措施**：<后续如何避免>
EOF
```

## 回滚后处理

### 1. 根因分析（RCA）
创建 `delivery/2026-06/CR-XXX/RCA.md` 文档，包含：
- **事件时间线**：发现问题 → 决策回滚 → 执行回滚 → 恢复正常
- **根本原因**：技术问题（代码 bug、性能问题）还是流程问题（需求理解偏差、测试不充分）
- **影响范围**：受影响用户数、业务损失
- **改进措施**：
  - 短期：修复 bug 并重新上线
  - 中期：完善测试用例
  - 长期：优化开发流程（如增强 Gate 检查）

### 2. 重新规划
如果功能仍需要，创建新的 CR：
```bash
cd DeliverHQ
python scripts/init_cr.py CR-XXX-v2 "修复后的功能：<功能名>" "<提出人>"
```

在 `CR-XXX-v2/request.md` 中引用原 CR 回滚教训：
```markdown
## 上一版本问题
CR-XXX 因 <原因> 回滚，本版本改进：
- 改进点 1
- 改进点 2
```

### 3. 通知与复盘
- 通知所有相关方回滚完成
- 召开复盘会议（Postmortem）
- 更新团队 Wiki/知识库

## 回滚成本评估

| 回滚时机 | 代码成本 | 数据成本 | 业务成本 |
|---|---|---|---|
| 测试环境发现 | 低（git revert） | 无 | 无 |
| 灰度发布阶段 | 低（git revert） | 低（少量用户数据） | 低（少量用户影响） |
| 全量上线 1 天内 | 中（可能有热修复） | 中（需数据修复） | 中（用户投诉） |
| 全量上线 1 周后 | 高（依赖关系复杂） | 高（数据已污染） | 高（业务依赖该功能） |

**结论**：越早发现问题，回滚成本越低。强化 Gate 检查可前移问题发现时机。

## 避免回滚的最佳实践

### 开发阶段
- [ ] 遵循 SpecGate 检查，确保需求理解准确
- [ ] 遵循 DesignGate 检查，UI 设计与需求方对齐
- [ ] 遵循 QualityGate 检查，测试覆盖率达标

### 部署阶段
- [ ] 使用灰度发布（Canary Deployment），先上线 5% 流量观察
- [ ] 设置监控告警（性能、错误率）
- [ ] 准备一键回滚脚本（自动化回滚）

### 流程改进
- [ ] Code Review 强制执行（至少 1 人 approve）
- [ ] 集成测试在 CI/CD 中自动执行
- [ ] 生产环境部署需审批（避免误操作）

## 紧急回滚（Emergency Rollback）

生产环境严重故障时（服务中断、数据丢失），跳过部分检查项，快速回滚：

```bash
# 1. 立即回滚到上一个稳定版本
git checkout <last-stable-tag>
git push origin HEAD:master --force  # 慎用！需团队共识

# 2. 重启服务
kubectl rollout undo deployment/app-name  # Kubernetes
# 或
docker-compose restart  # Docker

# 3. 验证服务恢复
curl https://api.example.com/health

# 4. 通知团队和用户
# 发送告警、更新状态页
```

**注意**：紧急回滚后必须补充完整的回滚文档和 RCA 报告。

## 检查清单总结

| 阶段 | 检查项 | 负责人 |
|---|---|---|
| 决策 | 确认回滚必要性、评估影响 | Tech Lead |
| 准备 | 备份代码、数据库、配置 | DevOps |
| 执行 | Git revert、数据库回滚、配置恢复 | Dev |
| 验证 | 编译、测试、性能监控 | QA + Dev |
| 部署 | 灰度 → 全量，监控告警 | DevOps |
| 文档 | 更新 ROLLBACK.md、decisions.md、mistake-book.md | Dev |
| 复盘 | RCA 报告、改进措施 | Tech Lead |

## 参考资料
- `DeliverHQ/docs/verification.md` — 验收标准
- `DeliverHQ/docs/mistake-book.md` — 错误案例库
- `delivery/YYYY-MM/CR-XXX/traceability.yml` — 代码追溯
