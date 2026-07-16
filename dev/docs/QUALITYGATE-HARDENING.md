# QualityGate 强化方案

## 当前问题

QualityGate 默认只解析 AI 生成的 quality-report.md，这是**不可信的**：
- AI 可以编造测试通过
- 没有真实验证
- 组织级使用必须基于真实执行

---

## 强化方案

### 方案 1: 要求 verification-manifest.yml（推荐）

**行为**:
- 如果 CR 没有 `verification-manifest.yml`，QualityGate **BLOCKED**
- 如果有 manifest，执行真实命令验证

**verification-manifest.yml 格式**:
```yaml
# 必需：构建验证
build:
  command: "npm run build"
  timeout: 300
  required: true

# 必需：P0 测试
tests:
  unit:
    command: "npm test -- --testPathPattern='.*\\.test\\.ts$'"
    timeout: 600
    required: true
    min_pass_rate: 100  # P0 必须 100% 通过
  
  integration:
    command: "npm run test:integration"
    timeout: 300
    required: false

# 可选：代码质量
quality:
  lint:
    command: "npm run lint"
    timeout: 60
    required: false
  
  typecheck:
    command: "npm run typecheck"
    timeout: 120
    required: false

# 可选：覆盖率
coverage:
  command: "npm run test:coverage"
  timeout: 600
  min_coverage: 80  # 最低覆盖率
  required: false
```

---

### 方案 2: 自动检测（备选）

如果 CR 没有 manifest，QualityGate 尝试自动检测：
- 检测 `package.json` → 执行 `npm test`
- 检测 `pom.xml` → 执行 `mvn test`
- 检测 `Cargo.toml` → 执行 `cargo test`
- 如果无法检测 → **BLOCKED**（不允许跳过验证）

---

## 实现优先级

### P0（必须）
1. ✅ 要求 verification-manifest.yml 存在
2. ✅ 执行 manifest 中的 build 命令
3. ✅ 执行 manifest 中的 test 命令
4. ✅ P0 测试通过率必须 100%

### P1（推荐）
5. ⚠️ 执行 lint / typecheck
6. ⚠️ 检查覆盖率阈值
7. ⚠️ 支持多种测试框架

### P2（增强）
8. 📝 自动检测构建工具
9. 📝 缓存测试结果
10. 📝 并行执行验证

---

## 修改点

### qualitygate.py 改动

```python
def main():
    # 1. 检查 verification-manifest.yml 是否存在
    manifest_path = cr_path / "verification-manifest.yml"
    if not manifest_path.exists():
        print(f"{Color.RED}❌ BLOCKED{Color.END}")
        print(f"  缺少 verification-manifest.yml")
        print(f"  QualityGate 不接受 AI 自述，必须真实验证")
        sys.exit(1)
    
    # 2. 加载 manifest
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)
    
    # 3. 执行构建
    if manifest.get('build', {}).get('required', True):
        result = subprocess.run(
            manifest['build']['command'],
            shell=True,
            timeout=manifest['build'].get('timeout', 300)
        )
        if result.returncode != 0:
            print(f"{Color.RED}❌ 构建失败{Color.END}")
            sys.exit(1)
    
    # 4. 执行测试
    for test_name, test_config in manifest.get('tests', {}).items():
        if test_config.get('required', True):
            result = subprocess.run(
                test_config['command'],
                shell=True,
                timeout=test_config.get('timeout', 600)
            )
            if result.returncode != 0:
                print(f"{Color.RED}❌ {test_name} 测试失败{Color.END}")
                sys.exit(1)
    
    # 5. 验证通过
    print(f"{Color.GREEN}✅ PASS{Color.END}")
    sys.exit(0)
```

---

## 迁移路径

### v4.9.2（当前版本）
- 保持兼容：如果没有 manifest，仅解析 quality-report.md（警告）
- 新 CR 建议创建 manifest

### v5.0（组织级 Harness）
- **强制要求**: 没有 manifest 则 BLOCKED
- 提供 manifest 生成工具

---

## 示例：CR-EXAMPLE 的 verification-manifest.yml

```yaml
# CR-EXAMPLE 验证清单
build:
  command: "echo 'Build passed (simulated)'"
  timeout: 10
  required: true

tests:
  unit:
    command: "echo 'Unit tests: 17/17 passed'"
    timeout: 10
    required: true
    min_pass_rate: 100
  
  integration:
    command: "echo 'Integration tests: 5/5 passed'"
    timeout: 10
    required: true

quality:
  lint:
    command: "echo 'ESLint: 0 errors, 0 warnings'"
    timeout: 10
    required: false

coverage:
  command: "echo 'Coverage: 100%'"
  timeout: 10
  min_coverage: 80
  required: false
```

---

## 修复 PermissionGate 同时进行

PermissionGate 也不能返回假 PASS：

```python
def main():
    if len(sys.argv) < 2:
        print("用法: python permissiongate.py <CR目录>")
        sys.exit(1)
    
    # 占位实现：默认 BLOCKED
    print("PermissionGate - 权限边界检查")
    print("⚠️  占位实现：默认 BLOCKED")
    print("❌ BLOCKED - 权限门禁未完整实现")
    print("   请等待 v5.0 完整实现")
    sys.exit(1)
```

---

**状态**: 方案设计完成  
**下一步**: 实现强化版 QualityGate + 修复 PermissionGate
