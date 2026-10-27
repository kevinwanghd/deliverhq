# 架构决策记录

> 记录技术选型、架构变更的决策及理由

| 日期 | 决策内容 | 理由 | 影响范围 |
|---|---|---|---|
| 2026-10-27 | 受保护路径审批路径对齐：lane_advisor 识别 protected_paths 并直接判 high-risk；protected_paths 清掉本仓库不存在的模板条目并写明批准路径 | PermissionGate 只在 lane=high-risk 且该 CR 的 exceptions.yml 有 gate_override{gate: PermissionGate, approved_by 非空} 时放行，但建议器此前完全不知道 protected_paths，会给出 standard lane 的建议——开发者照建议走必然在 PermissionGate 被 BLOCK；CR-FLOW-LANES.md 早已声明「修改 protected_paths → 自动判定为 High-Risk」，是实现缺失而非规则缺失 | skill/scripts/lane_advisor.py、skill/dir-graph.yaml、skill/docs/decisions.md |
| 2026-10-27 | 批准 PR #66 改动受保护路径 package.json / requirements.txt（engines 由 >=14 对齐到 >=20、新增依赖清单与锁文件） | 依赖清单维护是例行工作，原 engines >=14 覆盖已停止安全维护的 Node 14 且宽于 CI 实际验证面（CI 两处均用 node-version 20）；仓库内无任何依赖清单导致依赖不可复现，且 CI 的 python-test job 因找不到标记文件长期整段跳过。审批人：仓库所有者 | package.json、requirements.txt、package-lock.json、.github/workflows/governance.yml |

---

**使用说明**：
- 每次重大技术决策（技术选型、架构调整）时添加一行
- "理由"列记录为什么选择这个方案（权衡了哪些因素）
- "影响范围"列记录哪些模块/服务受影响
- Writeback Agent 会自动从 CR 中提取决策并更新此表

**示例**：
```markdown
| 2026-06-12 | 选择文档数据库存储日志 | 日志数据无复杂关联，文档数据库写入性能更高 | LoginLogService |
| 2026-06-10 | 引入 Redis 缓存用户权限 | 减少数据库查询，权限检查从 50ms 降到 5ms | AuthService |
```

**模板版本**: v4.5  
**更新日期**: 2026-06-12
