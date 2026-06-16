# Deployment Checklist: CR-EXAMPLE

## 部署信息
- 部署环境：staging
- 负责人：Tech Lead
- 版本：a1b2c3d

## 回滚计划
### 回滚触发条件
- 冒烟测试失败
- 关键错误率上升

### 回滚步骤
1. 回滚到上一稳定版本
2. 重启服务
3. 重新执行健康检查

### 回滚验证
- 核心接口可用
- 监控恢复正常

## 部署后验证
- 冒烟测试：`python -c "print('smoke ok')"`
- 监控指标：错误率、延迟、可用性
