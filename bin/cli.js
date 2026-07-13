#!/usr/bin/env node
'use strict';

/*
 * DeliverHQ 安装器（npx deliverhq）—— 多 Agent 通用
 *
 * 子命令：
 *   init [--target <agent>] [--global] [--local] [--force] [--yes]
 *   init-project [--profile fullstack-web] [--path <项目目录>] [--force]
 *   doctor [--path <skill目录>]
 *   --help
 *   --version
 *
 * 支持的 --target：
 *   claude   文件夹 skill → .claude/skills/deliverhq/        （默认）
 *   hermes   文件夹 skill → ~/.hermes/skills/deliverhq/
 *   codex    核心 → .deliverhq/ + 注入指针到 AGENTS.md
 *   gemini   核心 → .deliverhq/ + 注入指针到 GEMINI.md
 *   generic  核心 → .deliverhq/ + 生成 DELIVERHQ.md 指针（任意 agent）
 *
 * 设计：纯 Node 内置模块（零依赖）。本工具只负责"搬文件 + 注入入口 + 环境检测"。
 *       DeliverHQ 的门禁是 agent 无关的 Python 脚本，由各 agent 在对话中按需调用。
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFileSync } = require('child_process');
const readline = require('readline');

const PKG_ROOT = path.resolve(__dirname, '..');
const SKILL_SRC = path.join(PKG_ROOT, 'skill');
const PACKAGE_JSON = require(path.join(PKG_ROOT, 'package.json'));
const C = {
  g: (s) => `\x1b[92m${s}\x1b[0m`,
  y: (s) => `\x1b[93m${s}\x1b[0m`,
  r: (s) => `\x1b[91m${s}\x1b[0m`,
  b: (s) => `\x1b[94m${s}\x1b[0m`,
};

const POINTER_BEGIN = '<!-- BEGIN DELIVERHQ -->';
const POINTER_END = '<!-- END DELIVERHQ -->';
const SELFTEST_MAX_BUFFER = 32 * 1024 * 1024;

// Windows 编码修复：强制子进程使用 UTF-8（同 skill_orchestrator.py 的 SUBPROCESS_ENV）
const SUBPROCESS_ENV = {
  ...process.env,
  PYTHONUTF8: '1',
  PYTHONIOENCODING: 'utf-8',
};

// Agent 注册表。kind: 'folder'（带 skills 目录的 agent）| 'flat'（扁平指令文件的 agent）
const TARGETS = {
  claude: {
    kind: 'folder',
    projectDir: (cwd) => path.join(cwd, '.claude', 'skills', 'deliverhq'),
    globalDir: () => path.join(os.homedir(), '.claude', 'skills', 'deliverhq'),
    note: '重启 Claude Code，靠 SKILL.md frontmatter 自动发现',
  },
  hermes: {
    kind: 'folder',
    projectDir: (cwd) => path.join(cwd, '.hermes', 'skills', 'deliverhq'),
    globalDir: () => path.join(os.homedir(), '.hermes', 'skills', 'deliverhq'),
    note: '重启 Hermes，靠 SKILL.md frontmatter 自动发现',
  },
  codex: {
    kind: 'flat',
    instructionFile: 'AGENTS.md',
    note: '已把核心放入 .deliverhq/，并向 AGENTS.md 注入指针',
  },
  gemini: {
    kind: 'flat',
    instructionFile: 'GEMINI.md',
    note: '已把核心放入 .deliverhq/，并向 GEMINI.md 注入指针',
  },
  generic: {
    kind: 'flat',
    instructionFile: 'DELIVERHQ.md',
    note: '已把核心放入 .deliverhq/，并生成 DELIVERHQ.md 指针（让你的 agent 读取它）',
  },
};

function parseArgs(argv) {
  const VALUE_FLAGS = new Set(['path', 'home', 'target', 'profile']);
  const out = { _: [], flags: {} };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const eq = a.indexOf('=');
      if (eq !== -1) {
        out.flags[a.slice(2, eq)] = a.slice(eq + 1);
      } else {
        const key = a.slice(2);
        if (VALUE_FLAGS.has(key) && i + 1 < argv.length && !argv[i + 1].startsWith('--')) {
          out.flags[key] = argv[++i];
        } else {
          out.flags[key] = true;
        }
      }
    } else {
      out._.push(a);
    }
  }
  return out;
}

function ask(question) {
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    rl.question(question, (ans) => { rl.close(); resolve(ans.trim()); });
  });
}

function copyDir(src, dst) {
  const SKIP_DIRS = new Set(['__pycache__', 'workspace', 'outputs', 'artifacts', '.baseline']);
  fs.mkdirSync(dst, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name)) continue; // evidence 保留（含 fixture）
      copyDir(path.join(src, entry.name), path.join(dst, entry.name));
    } else if (entry.isFile()) {
      if (entry.name.endsWith('.pyc') || entry.name.endsWith('.backup')) continue;
      fs.copyFileSync(path.join(src, entry.name), path.join(dst, entry.name));
    }
  }
}

function detectPython() {
  for (const cmd of ['python3', 'python', 'py']) {
    try {
      const out = execFileSync(cmd, ['--version'], { stdio: ['ignore', 'pipe', 'pipe'] })
        .toString().trim();
      return { cmd, version: out };
    } catch (_) { /* next */ }
  }
  return null;
}

function checkPyYAML(pyCmd) {
  try { execFileSync(pyCmd, ['-c', 'import yaml'], { stdio: 'ignore' }); return true; }
  catch (_) { return false; }
}

function detectPythonWithPyYAML() {
  const candidates = [];
  for (const cmd of ['python3', 'python', 'py']) {
    try {
      const out = execFileSync(cmd, ['--version'], { stdio: ['ignore', 'pipe', 'pipe'] })
        .toString().trim();
      candidates.push({ cmd, version: out, hasYaml: checkPyYAML(cmd) });
    } catch (_) { /* next */ }
  }
  return candidates.find((item) => item.hasYaml) || candidates[0] || null;
}

function reportEnv() {
  console.log(C.b('\n[环境检测]'));
  const py = detectPythonWithPyYAML();
  if (!py) {
    console.log(C.r('  ✗ 未找到 Python (python3/python/py)'));
    console.log('    DeliverHQ 门禁是 Python 脚本，需 Python 3.10+：https://python.org');
    return;
  }
  console.log(C.g(`  ✓ ${py.version} (${py.cmd})`));
  if (!checkPyYAML(py.cmd)) {
    console.log(C.r('  ✗ 缺少 PyYAML'));
    console.log(`    请安装：${py.cmd} -m pip install PyYAML`);
  } else {
    console.log(C.g('  ✓ PyYAML 已安装'));
  }
}

// 扁平型 agent：向其指令文件注入/更新 DeliverHQ 指针段（幂等，带 BEGIN/END 标记）
function injectPointer(instructionPath, coreRelDir) {
  const block = [
    POINTER_BEGIN,
    '## DeliverHQ — AI 交付治理框架',
    '',
    `本项目已安装 DeliverHQ 治理框架，核心位于 \`${coreRelDir}/\`。`,
    '当进行正式多阶段交付、需要"文档不完备不开发"、扫描老项目技术债、',
    '或需要可执行门禁（信证据不信声明）时，先阅读：',
    '',
    `- \`${coreRelDir}/SKILL.md\` — 入口与"何时使用"`,
    `- \`${coreRelDir}/AGENTS.md\` — Agent 行为规则与门禁链`,
    '',
    '门禁是 Python 脚本（需 Python 3.10+ 与 PyYAML），用 shell 调用，例如：',
    '',
    '```bash',
    `python3 ${coreRelDir}/scripts/selftest.py ${coreRelDir}   # 自检`,
    `python3 ${coreRelDir}/scripts/specgate.py <acceptance-spec.md>`,
    '```',
    POINTER_END,
  ].join('\n');

  let content = '';
  if (fs.existsSync(instructionPath)) content = fs.readFileSync(instructionPath, 'utf8');

  if (content.includes(POINTER_BEGIN) && content.includes(POINTER_END)) {
    // 替换已有段（幂等升级）
    const re = new RegExp(`${POINTER_BEGIN}[\\s\\S]*?${POINTER_END}`);
    content = content.replace(re, block);
  } else {
    content = (content.trim() ? content.trimEnd() + '\n\n' : '') + block + '\n';
  }
  fs.writeFileSync(instructionPath, content, 'utf8');
}

async function chooseScope(flags) {
  if (flags.global) return 'global';
  if (flags.local || flags.yes) return 'local';
  const ans = await ask('安装到 1) 项目级  2) 全局 ?  [1]: ');
  return ans === '2' ? 'global' : 'local';
}

async function cmdInit(flags) {
  console.log(C.b('=== DeliverHQ 安装 ==='));

  // 选 target
  let target = (flags.target || 'claude').toLowerCase();
  if (!TARGETS[target]) {
    console.log(C.r(`未知 target: ${target}`));
    console.log('可选: ' + Object.keys(TARGETS).join(', '));
    process.exit(1);
  }
  const t = TARGETS[target];
  console.log(`目标 agent: ${C.b(target)} (${t.kind === 'folder' ? '文件夹 skill' : '扁平指令 + 指针'})`);

  let installedDir;

  if (t.kind === 'folder') {
    const scope = await chooseScope(flags);
    installedDir = scope === 'global' ? t.globalDir() : t.projectDir(process.cwd());
    if (fs.existsSync(installedDir) && !flags.force) {
      console.log(C.y(`⚠ 已存在: ${installedDir}（用 --force 覆盖）`));
      process.exit(1);
    }
    if (fs.existsSync(installedDir)) fs.rmSync(installedDir, { recursive: true, force: true });
    console.log(`复制核心 → ${installedDir}`);
    copyDir(SKILL_SRC, installedDir);
  } else {
    // 扁平型：核心固定放项目 .deliverhq/，指针注入指令文件
    installedDir = path.join(process.cwd(), '.deliverhq');
    if (fs.existsSync(installedDir) && !flags.force) {
      console.log(C.y(`⚠ 已存在: ${installedDir}（用 --force 覆盖）`));
      process.exit(1);
    }
    if (fs.existsSync(installedDir)) fs.rmSync(installedDir, { recursive: true, force: true });
    console.log(`复制核心 → ${installedDir}`);
    copyDir(SKILL_SRC, installedDir);

    const instrPath = path.join(process.cwd(), t.instructionFile);
    console.log(`注入指针 → ${instrPath}`);
    injectPointer(instrPath, '.deliverhq');
  }

  reportEnv();

  console.log(C.g(`\n✅ 安装完成（target=${target}）`));
  console.log('  ' + t.note);
  console.log('\n下一步：');
  console.log(`  验证健康度:  npx deliverhq doctor --path "${installedDir}"`);
}

function cmdInitProject(flags) {
  console.log(C.b('=== DeliverHQ init-project ==='));
  const profile = flags.profile || 'fullstack-web';
  const targetPath = flags.path ? path.resolve(flags.path) : process.cwd();
  const py = detectPythonWithPyYAML();
  if (!py || !py.hasYaml) {
    const cmd = py ? py.cmd : 'python';
    console.log(C.r(`✗ 需要带 PyYAML 的 Python：${cmd} -m pip install PyYAML`));
    process.exit(1);
  }
  try {
    const deliverhqDir = path.join(targetPath, 'DeliverHQ');
    if (fs.existsSync(deliverhqDir) && flags.force) {
      fs.rmSync(deliverhqDir, { recursive: true, force: true });
    }
    if (!fs.existsSync(deliverhqDir)) {
      console.log(`复制 DeliverHQ 核心 → ${deliverhqDir}`);
      copyDir(SKILL_SRC, deliverhqDir);
    }
    const args = [path.join(deliverhqDir, 'scripts', 'init_project_structure.py'), targetPath, '--profile', profile];
    if (flags.force) args.push('--force');
    const out = execFileSync(py.cmd, args, { stdio: ['ignore', 'pipe', 'pipe'], env: SUBPROCESS_ENV }).toString();
    console.log(out.trim());
    console.log(C.g('\n✅ 项目结构初始化完成'));
    console.log(`  运行结构检查: ${py.cmd} ${path.join(targetPath, 'DeliverHQ', 'scripts', 'structuregate.py')} ${targetPath}`);
  } catch (e) {
    const out = (e.stdout ? e.stdout.toString() : '') + (e.stderr ? e.stderr.toString() : '');
    console.log(C.r('❌ init-project 失败'));
    if (out.trim()) console.log(out.trim());
    process.exit(1);
  }
}

function resolveSkillDir(flags) {
  let skillDir = flags.path;
  if (!skillDir) {
    const cwd = process.cwd();
    const home = os.homedir();
    const candidates = [
      path.join(cwd, '.claude', 'skills', 'deliverhq'),
      path.join(cwd, '.hermes', 'skills', 'deliverhq'),
      path.join(cwd, '.deliverhq'),
      path.join(home, '.claude', 'skills', 'deliverhq'),
      path.join(home, '.hermes', 'skills', 'deliverhq'),
      SKILL_SRC,
    ];
    skillDir = candidates.find((p) => fs.existsSync(path.join(p, 'scripts', 'selftest.py')));
  }
  if (!skillDir || !fs.existsSync(path.join(skillDir, 'scripts', 'selftest.py'))) return null;
  return { skillDir, isFallback: path.resolve(skillDir) === path.resolve(SKILL_SRC) && !flags.path };
}

function requirePythonWithPyYAML() {
  const py = detectPythonWithPyYAML();
  if (!py) { console.log(C.r('✗ 未找到 Python，无法运行 selftest')); process.exit(1); }
  console.log(C.g(`✓ ${py.version} (${py.cmd})`));
  if (!py.hasYaml) {
    console.log(C.r(`✗ 缺少 PyYAML：${py.cmd} -m pip install PyYAML`)); process.exit(1);
  }
  console.log(C.g('✓ PyYAML 已安装'));
  return py;
}

function runSelftest(py, skillDir, extraArgs) {
  const args = [path.join(skillDir, 'scripts', 'selftest.py'), skillDir].concat(extraArgs || []);
  try {
    return {
      ok: true,
      out: execFileSync(py.cmd, args, { stdio: ['ignore', 'pipe', 'pipe'], maxBuffer: SELFTEST_MAX_BUFFER, env: SUBPROCESS_ENV }).toString(),
    };
  } catch (e) {
    return {
      ok: false,
      out: (e.stdout ? e.stdout.toString() : '') + (e.stderr ? e.stderr.toString() : ''),
    };
  }
}

function printSkillDir(resolved) {
  console.log(`核心目录: ${resolved.skillDir}`);
  if (resolved.isFallback) {
    console.log(C.y('⚠ 未找到已安装目录，使用 npm 包内核心进行自检'));
  }
}

function printSelftestSummary(out) {
  const lines = out.split('\n');
  const line = lines.find((l) => /通过[:：]/.test(l)) || '';
  const match = line.match(/通过[:：]\s*(\d+)\s*\/\s*(\d+)/);
  if (match) {
    console.log(C.g(`✅ selftest 通过: ${match[1]}/${match[2]}`));
    return;
  }
  const routingLine = lines.find((l) => l.includes('routing_eval PASS')) || '';
  if (routingLine) {
    console.log(C.g('✅ routing_eval PASS'));
    return;
  }
  console.log(C.g('✅ selftest 通过'));
}

function printSelftestFailures(out) {
  const fails = out.split('\n').filter((l) => l.includes('❌'));
  const visible = fails.slice(0, 12);
  console.log(C.r('❌ selftest 未通过：'));
  if (!visible.length) {
    console.log('  未捕获到 ❌ 明细，用 --verbose 查看完整输出。');
    return;
  }
  visible.forEach((l) => console.log('  ' + l.trim()));
  if (fails.length > visible.length) {
    console.log(C.y(`  ... 还有 ${fails.length - visible.length} 项，用 --verbose 查看全部`));
  }
}

function cmdDoctor(flags) {
  console.log(C.b('=== DeliverHQ doctor ==='));
  const resolved = resolveSkillDir(flags);
  if (!resolved) {
    console.log(C.r('✗ 找不到已安装的 DeliverHQ（用 --path 指定，或先 init）'));
    process.exit(1);
  }
  printSkillDir(resolved);

  const py = requirePythonWithPyYAML();

  console.log(C.b('\n[运行 selftest]'));
  const extraArgs = flags['routing-eval'] ? ['--routing-eval'] : [];
  const result = runSelftest(py, resolved.skillDir, extraArgs);
  if (flags.verbose && result.out.trim()) console.log(result.out.trim());
  if (result.ok) {
    if (!flags.verbose) printSelftestSummary(result.out);
    return;
  }
  if (!flags.verbose) printSelftestFailures(result.out);
  process.exit(1);
}

function cmdSelftest(flags) {
  console.log(C.b('=== DeliverHQ selftest ==='));
  const resolved = resolveSkillDir(flags);
  if (!resolved) {
    console.log(C.r('✗ 找不到已安装的 DeliverHQ（用 --path 指定，或先 init）'));
    process.exit(1);
  }
  printSkillDir(resolved);

  const py = requirePythonWithPyYAML();
  const extraArgs = flags['routing-eval'] ? ['--routing-eval'] : [];
  const result = runSelftest(py, resolved.skillDir, extraArgs);
  if (result.out.trim()) console.log(result.out.trim());
  if (!result.ok) process.exit(1);
}

function cmdRoute(argv, flags) {
  console.log(C.b('=== DeliverHQ route ==='));
  const resolved = resolveSkillDir(flags);
  if (!resolved) {
    console.log(C.r('✗ 找不到已安装的 DeliverHQ（用 --path 指定，或先 init）'));
    process.exit(1);
  }
  printSkillDir(resolved);

  const py = requirePythonWithPyYAML();
  const script = path.join(resolved.skillDir, 'scripts', 'deliver.py');
  if (!fs.existsSync(script)) {
    console.log(C.r(`✗ 缺少轻入口: ${script}`));
    process.exit(1);
  }

  const prompt = argv.join(' ').trim();
  const args = [script, 'route'];
  if (prompt) args.push(prompt);
  if (flags.json) args.push('--json');

  try {
    const out = execFileSync(py.cmd, args, {
      stdio: ['pipe', 'pipe', 'pipe'],
      maxBuffer: SELFTEST_MAX_BUFFER,
      env: SUBPROCESS_ENV,
    }).toString();
    if (out.trim()) console.log(out.trim());
  } catch (e) {
    const out = (e.stdout ? e.stdout.toString() : '') + (e.stderr ? e.stderr.toString() : '');
    console.log(C.r('✗ route 失败'));
    if (out.trim()) console.log(out.trim());
    process.exit(1);
  }
}

function cmdBootstrap(flags) {
  console.log(C.b('=== DeliverHQ bootstrap ==='));
  const py = requirePythonWithPyYAML();
  const script = path.join(SKILL_SRC, 'scripts', 'bootstrap_project.py');
  const args = [script, '--path', path.resolve(flags.path || process.cwd())];
  if (flags.home) args.push('--home', path.resolve(flags.home));
  if (flags.json) args.push('--json');
  if (flags.apply) args.push('--apply');
  try {
    const out = execFileSync(py.cmd, args, {
      stdio: ['ignore', 'pipe', 'pipe'],
      maxBuffer: SELFTEST_MAX_BUFFER,
      env: SUBPROCESS_ENV,
    }).toString();
    if (out.trim()) console.log(out.trim());
  } catch (e) {
    const out = (e.stdout ? e.stdout.toString() : '') + (e.stderr ? e.stderr.toString() : '');
    console.log(C.r('✗ bootstrap 失败'));
    if (out.trim()) console.log(out.trim());
    process.exit(e.status || 1);
  }
}

function help() {
  console.log(`DeliverHQ — AI 交付防翻车治理框架（多 Agent 安装器）

用法:
  npx deliverhq init [--target <agent>] [--global|--local] [--force] [--yes]

  --target 支持的 agent:
    claude   文件夹 skill → .claude/skills/deliverhq/   （默认）
    hermes   文件夹 skill → ~/.hermes/skills/deliverhq/
    codex    核心 → .deliverhq/ + 注入指针到 AGENTS.md
    gemini   核心 → .deliverhq/ + 注入指针到 GEMINI.md
    generic  核心 → .deliverhq/ + 生成 DELIVERHQ.md（任意 agent 通用）

  --global / --local   仅文件夹型：全局或项目级（默认问；--yes 取项目级）
  --force              覆盖已存在的安装
  --yes                非交互

  npx deliverhq init-project [--profile fullstack-web] [--path <项目目录>] [--force]
      初始化 AI 友好、人类易复查的项目目录结构 + DeliverHQ 治理空间

  npx deliverhq doctor [--path <核心目录>] [--verbose] [--routing-eval]
      检测 Python/PyYAML + 运行 selftest（默认摘要输出，--verbose 显示完整输出）

  npx deliverhq selftest [--path <核心目录>] [--routing-eval]
      直接运行 selftest 并完整透传输出

  npx deliverhq route "user request" [--path <core dir>] [--json]
      Light entry: route natural language to quick/standard/strict/legacy

  npx deliverhq bootstrap [--path <repo>] [--home <DeliverHQ dir>] [--json] [--apply]
      Read-only brownfield discovery; --apply creates reviewable candidate artifacts

  npx deliverhq --version
      输出 npm 包版本

示例:
  npx deliverhq init                      # Claude Code，问位置
  npx deliverhq init --target hermes --global
  npx deliverhq init --target codex       # 写 .deliverhq/ + AGENTS.md 指针
  npx deliverhq init --target generic     # 任意 agent
  npx deliverhq init-project --profile fullstack-web
  npx deliverhq route "refactor payment callback" --json
  npx deliverhq bootstrap --path . --json
  npx deliverhq selftest --path .claude/skills/deliverhq

说明:
  DeliverHQ 核心是 agent 无关的 Python 门禁脚本（需 Python 3.10+ 与 PyYAML）。
  本工具只负责按目标 agent 放置文件 + 注入入口，不运行流程本身。`);
}

async function main() {
  const { _, flags } = parseArgs(process.argv.slice(2));
  if (flags.version || flags.v || _[0] === 'version') { console.log(PACKAGE_JSON.version); return; }
  if (flags.help || flags.h || _[0] === 'help') return help();
  const cmd = _[0];
  if (cmd === 'init') return cmdInit(flags);
  if (cmd === 'init-project') return cmdInitProject(flags);
  if (cmd === 'doctor') return cmdDoctor(flags);
  if (cmd === 'selftest') return cmdSelftest(flags);
  if (cmd === 'route' || cmd === 'deliver') return cmdRoute(_.slice(1), flags);
  if (cmd === 'bootstrap') return cmdBootstrap(flags);
  if (!cmd) { help(); return; }
  console.log(C.r(`未知命令: ${cmd}`));
  help();
  process.exit(1);
}

main().catch((e) => { console.error(C.r('错误: ' + e.message)); process.exit(1); });
