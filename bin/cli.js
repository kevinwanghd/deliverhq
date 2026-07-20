#!/usr/bin/env node
'use strict';

/*
 * DeliverHQ 安装器（npx deliverhq）—— 多 Agent 通用
 *
 * 子命令：
 *   init [--target <agent>] [--profile full|product] [--global] [--local] [--force] [--yes]
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

const INSTALL_PROFILES = {
  full: {
    description: '完整交付治理包（默认，研发/测试/治理全能力）',
    copyAll: true,
  },
  product: {
    description: '产品经理 PRD 包（只含 PRD、派生规格模板和 PRD 校验/同步前置能力）',
    dirs: [
      '_archived',
      'change-requests',
      'docs',
      'delivery',
      'scripts',
    ],
    files: [
      'product/README.md',
      'VERSION.yml',
      'dir-graph.yaml',
      'docs/PRD.md',
      'scripts/check_skeleton.py',
      'scripts/dir_graph_lint.py',
      'scripts/health_check.py',
      'scripts/prd_validate.py',
      'scripts/prd_sync.py',
      'scripts/runtime_support.py',
    ],
    mappings: [
      ['product/AGENTS.md', 'AGENTS.md'],
      ['product/COMMANDS.yml', 'COMMANDS.yml'],
      ['product/SKILL.md', 'SKILL.md'],
      ['product/README.md', 'README.md'],
    ],
  },
};

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
  const VALUE_FLAGS = new Set(['path', 'home', 'target', 'profile', 'prd', 'out']);
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

function normalizeInstallProfile(raw) {
  const profile = (raw || 'full').toLowerCase();
  if (!INSTALL_PROFILES[profile]) {
    console.log(C.r(`未知安装 profile: ${profile}`));
    console.log('可选: ' + Object.keys(INSTALL_PROFILES).join(', '));
    process.exit(1);
  }
  return profile;
}

function writeInstallProfile(dst, profileName) {
  const profile = INSTALL_PROFILES[profileName];
  const body = [
    'schema: deliverhq-install-profile',
    'schema_version: 1',
    `profile: ${profileName}`,
    `description: ${profile.description}`,
    '',
  ].join('\n');
  fs.writeFileSync(path.join(dst, 'INSTALL-PROFILE.yml'), body, 'utf8');
}

function copyFileWithParents(srcRoot, dstRoot, relPath) {
  const src = path.join(srcRoot, relPath);
  const dst = path.join(dstRoot, relPath);
  if (!fs.existsSync(src)) {
    throw new Error(`install profile references missing file: ${relPath}`);
  }
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.copyFileSync(src, dst);
}

function copyInstallProfile(profileName, dst) {
  const profile = INSTALL_PROFILES[profileName];
  if (profile.copyAll) {
    copyDir(SKILL_SRC, dst);
    writeInstallProfile(dst, profileName);
    return;
  }
  fs.mkdirSync(dst, { recursive: true });
  for (const relDir of profile.dirs || []) {
    fs.mkdirSync(path.join(dst, relDir), { recursive: true });
  }
  for (const relFile of profile.files || []) {
    copyFileWithParents(SKILL_SRC, dst, relFile);
  }
  for (const [source, target] of profile.mappings || []) {
    const src = path.join(SKILL_SRC, source);
    const targetPath = path.join(dst, target);
    if (!fs.existsSync(src)) {
      throw new Error(`install profile references missing file: ${source}`);
    }
    fs.mkdirSync(path.dirname(targetPath), { recursive: true });
    fs.copyFileSync(src, targetPath);
  }
  writeInstallProfile(dst, profileName);
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
    `python3 ${coreRelDir}/scripts/health_check.py ${coreRelDir}   # 健康自检`,
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
  const profile = normalizeInstallProfile(flags.profile);

  // 选 target
  let target = (flags.target || 'claude').toLowerCase();
  if (!TARGETS[target]) {
    console.log(C.r(`未知 target: ${target}`));
    console.log('可选: ' + Object.keys(TARGETS).join(', '));
    process.exit(1);
  }
  const t = TARGETS[target];
  console.log(`目标 agent: ${C.b(target)} (${t.kind === 'folder' ? '文件夹 skill' : '扁平指令 + 指针'})`);
  console.log(`安装 profile: ${C.b(profile)} - ${INSTALL_PROFILES[profile].description}`);

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
    copyInstallProfile(profile, installedDir);
  } else {
    // 扁平型：核心固定放项目 .deliverhq/，指针注入指令文件
    installedDir = path.join(process.cwd(), '.deliverhq');
    if (fs.existsSync(installedDir) && !flags.force) {
      console.log(C.y(`⚠ 已存在: ${installedDir}（用 --force 覆盖）`));
      process.exit(1);
    }
    if (fs.existsSync(installedDir)) fs.rmSync(installedDir, { recursive: true, force: true });
    console.log(`复制核心 → ${installedDir}`);
    copyInstallProfile(profile, installedDir);

    const instrPath = path.join(process.cwd(), t.instructionFile);
    console.log(`注入指针 → ${instrPath}`);
    injectPointer(instrPath, '.deliverhq');
  }

  reportEnv();

  console.log(C.g(`\n✅ 安装完成（target=${target}, profile=${profile}）`));
  console.log('  ' + t.note);
  console.log('\n下一步：');
  console.log(`  验证健康度:  npx deliverhq doctor --path "${installedDir}"`);
}

async function chooseProfile(flags) {
  // 显式 --profile 或非交互（--yes）时不追问
  if (typeof flags.profile === 'string' && flags.profile) return flags.profile;
  if (flags['governance-only']) return 'governance-only';
  if (flags.yes) return 'fullstack-web';
  console.log('选择初始化范围：');
  console.log('  1) 仅治理层        只在项目根建 DeliverHQ/，不碰业务目录结构（库/CLI/移动端/已有结构的项目）');
  console.log('  2) 全栈 Web 骨架    额外生成 apps/ packages/ 等 monorepo 业务骨架');
  const ans = await ask('请选择 [1/2]（默认 1）: ');
  return ans === '2' ? 'fullstack-web' : 'governance-only';
}

async function cmdInitProject(flags) {
  console.log(C.b('=== DeliverHQ init-project ==='));
  const profile = await chooseProfile(flags);
  const targetPath = flags.path ? path.resolve(flags.path) : process.cwd();
  const py = detectPythonWithPyYAML();
  if (!py || !py.hasYaml) {
    const cmd = py ? py.cmd : 'python';
    console.log(C.r(`✗ 需要带 PyYAML 的 Python：${cmd} -m pip install PyYAML`));
    process.exit(1);
  }
  console.log(`profile: ${C.b(profile)}${profile === 'governance-only' ? '（仅治理层，不生成业务目录）' : ''}`);
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
    skillDir = candidates.find((p) => fs.existsSync(path.join(p, 'scripts', 'health_check.py')));
  }
  if (!skillDir || !fs.existsSync(path.join(skillDir, 'scripts', 'health_check.py'))) return null;
  return { skillDir, isFallback: path.resolve(skillDir) === path.resolve(SKILL_SRC) && !flags.path };
}

function requirePythonWithPyYAML() {
  const py = detectPythonWithPyYAML();
  if (!py) { console.log(C.r('✗ 未找到 Python，无法运行 health_check')); process.exit(1); }
  console.log(C.g(`✓ ${py.version} (${py.cmd})`));
  if (!py.hasYaml) {
    console.log(C.r(`✗ 缺少 PyYAML：${py.cmd} -m pip install PyYAML`)); process.exit(1);
  }
  console.log(C.g('✓ PyYAML 已安装'));
  return py;
}

function runHealthCheck(py, skillDir) {
  const args = [path.join(skillDir, 'scripts', 'health_check.py'), skillDir];
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
    console.log(C.g(`✅ health_check 通过: ${match[1]}/${match[2]}`));
    return;
  }
  console.log(C.g('✅ health_check 通过'));
}

function printSelftestFailures(out) {
  const fails = out.split('\n').filter((l) => l.includes('❌'));
  const visible = fails.slice(0, 12);
  console.log(C.r('❌ health_check 未通过：'));
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

  console.log(C.b('\n[运行 health_check]'));
  const result = runHealthCheck(py, resolved.skillDir);
  if (flags.verbose && result.out.trim()) console.log(result.out.trim());
  if (result.ok) {
    if (!flags.verbose) printSelftestSummary(result.out);
    return;
  }
  if (!flags.verbose) printSelftestFailures(result.out);
  process.exit(1);
}

function cmdSelftest(flags) {
  // 兼容旧命令：selftest 现别名到随包发布的 health_check（全量 selftest 已下沉到 dev/）。
  console.log(C.b('=== DeliverHQ health_check ==='));
  const resolved = resolveSkillDir(flags);
  if (!resolved) {
    console.log(C.r('✗ 找不到已安装的 DeliverHQ（用 --path 指定，或先 init）'));
    process.exit(1);
  }
  printSkillDir(resolved);

  const py = requirePythonWithPyYAML();
  const result = runHealthCheck(py, resolved.skillDir);
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

function cmdPrdSync(flags) {
  console.log(C.b('=== DeliverHQ prd-sync ==='));
  const resolved = resolveSkillDir(flags);
  if (!resolved) {
    console.log(C.r('❌ 找不到已安装的 DeliverHQ（用 --path 指定，或先 init）'));
    process.exit(1);
  }
  printSkillDir(resolved);

  const py = requirePythonWithPyYAML();
  const script = path.join(resolved.skillDir, 'scripts', 'prd_sync.py');
  if (!fs.existsSync(script)) {
    console.log(C.r(`❌ 缺少 PRD 同步脚本: ${script}`));
    process.exit(1);
  }

  const args = [script];
  if (flags.prd) args.push('--prd', path.resolve(flags.prd));
  if (flags.out) args.push('--out', path.resolve(flags.out));
  if (flags.strict) args.push('--strict');
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
    console.log(C.r('❌ prd-sync 失败'));
    if (out.trim()) console.log(out.trim());
    process.exit(e.status || 1);
  }
}

function cmdPrdValidate(flags) {
  console.log(C.b('=== DeliverHQ prd-validate ==='));
  const resolved = resolveSkillDir(flags);
  if (!resolved) {
    console.log(C.r('❌ 找不到已安装的 DeliverHQ（用 --path 指定，或先 init）'));
    process.exit(1);
  }
  const py = requirePythonWithPyYAML();
  const script = path.join(resolved.skillDir, 'scripts', 'prd_validate.py');
  if (!fs.existsSync(script)) {
    console.log(C.r(`❌ 缺少 PRD 校验脚本: ${script}`));
    process.exit(1);
  }
  const args = [script, flags.prd ? path.resolve(flags.prd) : path.join(resolved.skillDir, 'docs', 'PRD.md')];
  if (flags.strict) args.push('--strict');
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
    console.log(C.r('❌ prd-validate 失败'));
    if (out.trim()) console.log(out.trim());
    process.exit(e.status || 1);
  }
}

function cmdGo(argv, flags) {
  const projectRoot = path.resolve(flags.path || process.cwd());
  const coreCandidates = [
    path.join(projectRoot, 'DeliverHQ'),
    path.join(projectRoot, '.deliverhq'),
    path.join(projectRoot, '.claude', 'skills', 'deliverhq'),
    path.join(projectRoot, '.hermes', 'skills', 'deliverhq'),
    SKILL_SRC,
  ];
  const skillDir = coreCandidates.find((candidate) =>
    fs.existsSync(path.join(candidate, 'scripts', 'deliver.py'))
  );
  if (!skillDir) {
    console.log(C.r('✗ 找不到 DeliverHQ 核心；请先 init 或用包含 DeliverHQ 的项目路径运行'));
    process.exit(1);
  }

  const homeCandidates = [
    path.join(projectRoot, 'DeliverHQ'),
  ];
  const home = homeCandidates.find((candidate) =>
    fs.existsSync(path.join(candidate, 'change-requests'))
  );
  if (!home) {
    const error = {
      error: 'deliverhq_home_not_found',
      project_root: projectRoot,
      recovery_action: `在 ${projectRoot} 初始化 DeliverHQ/ 治理目录后重试`,
    };
    if (flags.json) console.log(JSON.stringify(error, null, 2));
    else {
      console.log(C.r(`✗ 项目内缺少唯一治理目录: ${path.join(projectRoot, 'DeliverHQ')}`));
      console.log(`  修复: ${error.recovery_action}`);
    }
    process.exit(1);
  }

  if (!flags.json) {
    console.log(C.b('=== DeliverHQ go ==='));
    console.log(`项目目录: ${projectRoot}`);
    console.log(`核心目录: ${skillDir}`);
  }

  const py = flags.json ? detectPythonWithPyYAML() : requirePythonWithPyYAML();
  if (!py || !py.hasYaml) {
    const error = { error: 'python_runtime_unavailable', recovery_action: '安装 Python 3.10+ 与 PyYAML' };
    if (flags.json) console.log(JSON.stringify(error, null, 2));
    else console.log(C.r(`✗ ${error.recovery_action}`));
    process.exit(1);
  }
  const script = path.join(skillDir, 'scripts', 'deliver.py');
  const prompt = argv.join(' ').trim();
  const args = [script, 'go'];
  if (prompt) args.push(prompt);
  args.push('--project-root', projectRoot);
  if (home) args.push('--home', home);
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
    console.log(C.r('✗ go 失败'));
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
  console.log(`DeliverHQ v${PACKAGE_JSON.version} — AI 交付防翻车治理框架（多 Agent 安装器）

用法:
  npx deliverhq init [--target <agent>] [--profile <full|product>] [--global|--local] [--force] [--yes]

  --target 支持的 agent:
    claude   文件夹 skill → .claude/skills/deliverhq/   （默认）
    hermes   文件夹 skill → ~/.hermes/skills/deliverhq/
    codex    核心 → .deliverhq/ + 注入指针到 AGENTS.md
    gemini   核心 → .deliverhq/ + 注入指针到 GEMINI.md
    generic  核心 → .deliverhq/ + 生成 DELIVERHQ.md（任意 agent 通用）

  --global / --local   仅文件夹型：全局或项目级（默认问；--yes 取项目级）
  --profile            安装范围：full（默认完整治理包）或 product（产品经理 PRD 包）
  --force              覆盖已存在的安装
  --yes                非交互

  npx deliverhq init-project [--profile <名称>] [--governance-only] [--path <项目目录>] [--force] [--yes]
      初始化项目治理空间。无 --profile/--yes 时交互选择范围：
        · governance-only（默认）— 只建 DeliverHQ/，不碰业务目录结构（库/CLI/移动端/已有结构）
        · fullstack-web        — 额外生成 apps/ packages/ 等 monorepo 业务骨架
      --governance-only 等价于 --profile governance-only；--yes 非交互时默认 fullstack-web

  npx deliverhq doctor [--path <核心目录>] [--verbose]
      检测 Python/PyYAML + 运行 health_check（默认摘要输出，--verbose 显示完整输出）

  npx deliverhq selftest [--path <核心目录>]
      运行 health_check 并完整透传输出（selftest 的兼容别名）

  npx deliverhq route "user request" [--path <core dir>] [--json]
      Light entry: route natural language to quick/standard/strict/legacy

  npx deliverhq prd-validate [--path <core dir>] [--prd <PRD.md>] [--strict] [--json]
      Validate a completed PRD before handoff

  npx deliverhq prd-sync [--path <core dir>] [--prd <PRD.md>] [--out <dir>] [--strict] [--json]
      Sync PRD.md into docs/agent/ manifest, task map, and acceptance spec

  npx deliverhq go "user request" [--path <project dir>] [--json]
      Read-only unified entry: resolve active CR, target verb, and artifact preflight

  npx deliverhq bootstrap [--path <repo>] [--home <DeliverHQ dir>] [--json] [--apply]
      Read-only brownfield discovery; --apply creates reviewable candidate artifacts

  npx deliverhq --version
      输出 npm 包版本

示例:
  npx deliverhq init                      # Claude Code，问位置
  npx deliverhq init --target codex --profile product  # 产品经理只安装 PRD 相关能力
  npx deliverhq init --target hermes --global
  npx deliverhq init --target codex       # 写 .deliverhq/ + AGENTS.md 指针
  npx deliverhq init --target generic     # 任意 agent
  npx deliverhq init-project --governance-only   # 仅治理层（不生成业务目录）
  npx deliverhq init-project --profile fullstack-web
  npx deliverhq route "refactor payment callback" --json
  npx deliverhq prd-sync --path .deliverhq --json
  npx deliverhq go "继续" --path . --json
  npx deliverhq bootstrap --path . --json
  npx deliverhq doctor --path .claude/skills/deliverhq

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
  if (cmd === 'prd-validate') return cmdPrdValidate(flags);
  if (cmd === 'prd-sync') return cmdPrdSync(flags);
  if (cmd === 'go') return cmdGo(_.slice(1), flags);
  if (cmd === 'bootstrap') return cmdBootstrap(flags);
  if (!cmd) { help(); return; }
  console.log(C.r(`未知命令: ${cmd}`));
  help();
  process.exit(1);
}

main().catch((e) => { console.error(C.r('错误: ' + e.message)); process.exit(1); });
