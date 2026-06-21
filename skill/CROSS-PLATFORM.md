# DeliverHQ 跨平台兼容性说明

> **v5.7.0 已验证跨平台运行**：核心框架在 Windows、macOS、Linux 上均可使用。

## 一、框架层面保证（已处理）

| 类别 | 处理方式 | 状态 |
|------|---------|------|
| 路径分隔符 | 30/33 脚本使用 `pathlib.Path`（自动适配 `/` vs `\`） | ✅ 安全 |
| Python 可执行文件 | 全部使用 `sys.executable`（不硬编码 `python`/`python3`） | ✅ 安全 |
| 换行符 | 文本文件用 Python 默认模式（自动转换 `\n` ↔ `\r\n`）、`.splitlines()` 自动处理所有平台 | ✅ 安全 |
| Git 命令 | 调用 `git` 时依赖系统 PATH，不硬编码路径 | ✅ 安全（见约束） |
| 终端编码 | `runtime_support.configure_console()` 强制 UTF-8（Windows `chcp 65001` 等价） | ✅ 已适配 |
| 文件权限 | 不使用 Unix 特定的 `chmod`/`chown` | ✅ 无依赖 |

## 二、外部依赖约束

### 必需工具（需在系统 PATH）

| 工具 | 用途 | Windows 安装 | macOS/Linux 安装 |
|------|------|-------------|----------------|
| **Python 3.6+** | 运行框架 | [python.org](https://python.org) 或 Microsoft Store | 通常预装 |
| **Git** | PermissionGate / 变更追踪 | [git-scm.com](https://git-scm.com) | `brew install git` / `apt install git` |

安装后验证：
```bash
python --version   # 或 python3
git --version
```

### Python 依赖

```bash
pip install PyYAML   # 必需（YAML 解析）
# 或 pip install -r requirements.txt（如果存在）
```

## 三、用户责任：验证命令的跨平台兼容性

以下场景中，**用户提供的命令字符串会通过 `shell=True` 执行**，框架不做转换：

1. **`verification-manifest.yml` 中的命令**（build / test / lint）
2. **`loop_mode.py` 的 `check_command`**

### 跨平台命令编写建议

#### ✅ 推荐（跨平台安全）

```yaml
# 使用 Python 脚本（跨平台一致）
build:
  command: "python -m build"
test:
  unit:
    command: "python -m pytest tests/"
```

```yaml
# 使用跨平台工具
lint:
  command: "pylint src/"
```

#### ⚠️ 需注意（平台差异）

| 操作 | Unix (sh/bash) | Windows (cmd.exe) | 跨平台方案 |
|------|---------------|------------------|----------|
| 多命令 | `cmd1 && cmd2` | `cmd1 && cmd2` | ✅ 两者都支持 `&&` |
| 管道 | `cmd \| grep` | `cmd \| findstr` | ⚠️ 用 Python 脚本 |
| 环境变量 | `$VAR` | `%VAR%` | ⚠️ 用 Python 脚本 |
| 路径 | `src/main.py` | `src\main.py` | ✅ 两者都接受 `/`（推荐） |
| 删除文件 | `rm -f file` | `del /f file` | ⚠️ 用 Python 脚本 |

#### ❌ 避免（不跨平台）

```yaml
# ❌ Unix shell 特性
test:
  command: "source venv/bin/activate && pytest"   # Windows 无 source

# ❌ Unix 工具
lint:
  command: "grep -r 'TODO' src/"   # Windows 需 findstr 或 Select-String
```

### 推荐模式：用 Python 脚本封装

```yaml
# verification-manifest.yml
build:
  command: "python scripts/ci_build.py"   # 跨平台
test:
  command: "python scripts/ci_test.py"
```

```python
# scripts/ci_build.py
import subprocess, sys
result = subprocess.run([sys.executable, "-m", "build"], check=True)
# 复杂逻辑用 Python 实现，跨平台零改动
```

## 四、已知平台特定行为

### Windows

- **PermissionGate** 在非 git 目录会降级为 PASS WITH WARNING（这是跨平台一致行为）
- **Worktree** 需要 Git 2.5+（Windows Git for Windows 自带）
- **终端颜色**：需要 Windows 10+ 或启用 ANSI 转义序列

### macOS

- 预装 Python 可能是 2.7（需手动安装 Python 3）
- 使用 `brew install git` 获取最新 Git

### Linux

- 通常预装 Python 3 和 Git
- 部分发行版需要 `python3-yaml` 包（`apt install python3-yaml`）

## 五、测试跨平台可用性

```bash
# 1. 解压包
tar xzf deliverhq-v5.7.0.tar.gz   # 或 7z x deliverhq-v5.7.0.7z
cd DeliverHQ

# 2. 运行自检（会测试核心路径/命令）
python scripts/selftest.py
# 期望输出：通过: 17/17 ✅ DeliverHQ 框架健康，可正常使用

# 3. 门禁契约（测试 Gate 正反例）
python scripts/gate_contract_check.py
```

如果 selftest 17/17 通过，说明框架在该平台可用。

## 六、常见问题

**Q: Windows 上 `python` 命令找不到？**  
A: 安装时勾选"Add Python to PATH"，或用 `py` 命令（Python Launcher）：`py scripts/selftest.py`

**Q: Git 报错 "not a git repository"？**  
A: 正常。DeliverHQ 解压后不在 git 仓库内，PermissionGate 会自动降级为 PASS WITH WARNING。若需启用权限边界检查，请在目标项目的 git 仓库内运行。

**Q: 如何确保我的 verification 命令跨平台？**  
A: 优先用 Python 模块（`python -m pytest`）或封装成 `.py` 脚本。避免 shell 特定语法（source / export / grep）。

---

**总结**：DeliverHQ v5.7.0 框架本身已跨平台适配。用户只需确保 Python + Git 在 PATH，并让自定义验证命令遵循跨平台规范。
