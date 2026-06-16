#!/usr/bin/env node
'use strict';

/*
 * DeliverHQ skill 安装器（npx deliverhq）
 *
 * 子命令：
 *   init [--global] [--force] [--yes]   把 skill 装到 .claude/skills/deliverhq/
 *   doctor [--path <skill目录>]          检测 Python/PyYAML 环境 + 跑 selftest
 *   --help
 *
 * 设计：纯 Node 内置模块（零依赖，npx 才能零安装直接跑）。
 * 注意：本工具只负责"搬文件 + 环境检测"。skill 真正的执行体是 Python gate，
 *       由 Claude 在对话里按需调用——npx 不运行 DeliverHQ 流程本身。
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFileSync } = require('child_process');
const readline = require('readline');

const PKG_ROOT = path.resolve(__dirname, '..');
const SKILL_SRC = path.join(PKG_ROOT, 'skill');
const C = {
  g: (s) => `\x1b[92m${s}\x1b[0m`,
  y: (s) => `\x1b[93m${s}\x1b[0m`,
  r: (s) => `\x1b[91m${s}\x1b[0m`,
  b: (s) => `\x1b[94m${s}\x1b[0m`,
};

function parseArgs(argv) {
  // 需要取值的 flag（支持 `--path 值` 空格形式；其余按布尔）
  const VALUE_FLAGS = new Set(['path']);
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

// 递归复制目录（跳过缓存/运行时产物，双保险）
function copyDir(src, dst) {
  const SKIP_DIRS = new Set(['__pycache__', 'evidence', 'workspace', 'outputs', 'artifacts', '.baseline']);
  fs.mkdirSync(dst, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      // evidence 例外：保留 CR-EXAMPLE 下的 fixture（changed-files.json 等），只跳运行时产物名
      if (SKIP_DIRS.has(entry.name) && entry.name !== 'evidence') continue;
      copyDir(path.join(src, entry.name), path.join(dst, entry.name));
    } else if (entry.isFile()) {
      if (entry.name.endsWith('.pyc')) continue;
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
    } catch (_) { /* try next */ }
  }
  return null;
}

function checkPyYAML(pyCmd) {
  try {
    execFileSync(pyCmd, ['-c', 'import yaml'], { stdio: 'ignore' });
    return true;
  } catch (_) { return false; }
}

function resolveTargetBase(flags) {
  if (flags.global) return path.join(os.homedir(), '.claude', 'skills');
  return path.join(process.cwd(), '.claude', 'skills');
}

async function cmdInit(flags) {
  console.log(C.b('=== DeliverHQ skill 安装 ==='));

  // 1. 选择位置（--global / --yes 跳过询问）
  let base;
  if (flags.global) {
    base = path.join(os.homedir(), '.claude', 'skills');
  } else if (flags.local || flags.yes) {
    base = path.join(process.cwd(), '.claude', 'skills');
  } else {
    const ans = await ask(
      '安装到哪里?\n' +
      `  1) 项目级  ${path.join(process.cwd(), '.claude/skills/deliverhq')}\n` +
      `  2) 全局    ${path.join(os.homedir(), '.claude/skills/deliverhq')}\n` +
      '选择 [1]: ');
    base = ans === '2'
      ? path.join(os.homedir(), '.claude', 'skills')
      : path.join(process.cwd(), '.claude', 'skills');
  }

  const target = path.join(base, 'deliverhq');

  // 2. 已存在处理
  if (fs.existsSync(target) && !flags.force) {
    console.log(C.y(`⚠ 目标已存在: ${target}`));
    console.log('  用 --force 覆盖，或先手动删除。');
    process.exit(1);
  }

  // 3. 复制
  console.log(`复制 skill → ${target}`);
  if (fs.existsSync(target)) fs.rmSync(target, { recursive: true, force: true });
  copyDir(SKILL_SRC, target);

  // 4. 环境检测（不阻断安装，但明确提示）
  console.log(C.b('\n[环境检测]'));
  const py = detectPython();
  if (!py) {
    console.log(C.r('  ✗ 未找到 Python (python3/python/py)'));
    console.log('    DeliverHQ 的门禁是 Python 脚本，需安装 Python 3.6+：https://python.org');
  } else {
    console.log(C.g(`  ✓ ${py.version} (${py.cmd})`));
    if (!checkPyYAML(py.cmd)) {
      console.log(C.r('  ✗ 缺少 PyYAML'));
      console.log(`    请安装：${py.cmd} -m pip install PyYAML`);
    } else {
      console.log(C.g('  ✓ PyYAML 已安装'));
    }
  }

  console.log(C.g(`\n✅ 安装完成: ${target}`));
  console.log('\n下一步：');
  console.log(`  1. 验证健康度:  npx deliverhq doctor --path "${target}"`);
  console.log('  2. 重启 Claude Code，skill 会被自动发现（靠 SKILL.md frontmatter）');
  console.log('  3. 用法见 skill 内 README.md / SKILL.md');
}

function cmdDoctor(flags) {
  console.log(C.b('=== DeliverHQ doctor ==='));
  // 定位 skill 目录
  let skillDir = flags.path;
  if (!skillDir) {
    const candidates = [
      path.join(process.cwd(), '.claude', 'skills', 'deliverhq'),
      path.join(os.homedir(), '.claude', 'skills', 'deliverhq'),
      SKILL_SRC,
    ];
    skillDir = candidates.find((p) => fs.existsSync(path.join(p, 'scripts', 'selftest.py')));
  }
  if (!skillDir || !fs.existsSync(path.join(skillDir, 'scripts', 'selftest.py'))) {
    console.log(C.r('✗ 找不到已安装的 skill（用 --path 指定，或先 init）'));
    process.exit(1);
  }
  console.log(`skill 目录: ${skillDir}`);

  const py = detectPython();
  if (!py) {
    console.log(C.r('✗ 未找到 Python，无法运行 selftest'));
    process.exit(1);
  }
  console.log(C.g(`✓ ${py.version}`));
  if (!checkPyYAML(py.cmd)) {
    console.log(C.r(`✗ 缺少 PyYAML：${py.cmd} -m pip install PyYAML`));
    process.exit(1);
  }
  console.log(C.g('✓ PyYAML 已安装'));

  console.log(C.b('\n[运行 selftest]'));
  try {
    const out = execFileSync(py.cmd, [path.join(skillDir, 'scripts', 'selftest.py'), skillDir],
      { stdio: ['ignore', 'pipe', 'pipe'] }).toString();
    const line = out.split('\n').find((l) => l.includes('通过:')) || '';
    console.log(C.g('✅ selftest 通过 ' + line.trim()));
  } catch (e) {
    const out = (e.stdout ? e.stdout.toString() : '') + (e.stderr ? e.stderr.toString() : '');
    const fails = out.split('\n').filter((l) => l.includes('❌')).slice(0, 8);
    console.log(C.r('❌ selftest 未通过：'));
    fails.forEach((l) => console.log('  ' + l.trim()));
    process.exit(1);
  }
}

function help() {
  console.log(`DeliverHQ — AI 交付防翻车治理框架（Claude Agent Skill 安装器）

用法:
  npx deliverhq init [--global] [--local] [--force] [--yes]
      把 skill 装到 .claude/skills/deliverhq/
        --global  装到 ~/.claude/skills（默认项目级 ./.claude/skills）
        --local   强制项目级，不询问
        --force   覆盖已存在的安装
        --yes     非交互，用默认（项目级）

  npx deliverhq doctor [--path <skill目录>]
      检测 Python/PyYAML 环境并运行 selftest

  npx deliverhq --help

说明:
  本工具只负责"安装 + 环境检测"。DeliverHQ 的门禁是 Python 脚本，
  由 Claude 在对话中按需调用——npx 不运行 DeliverHQ 流程本身。
  运行时需要 Python 3.6+ 与 PyYAML。`);
}

async function main() {
  const { _, flags } = parseArgs(process.argv.slice(2));
  if (flags.help || flags.h || _[0] === 'help') return help();
  const cmd = _[0];
  if (cmd === 'init') return cmdInit(flags);
  if (cmd === 'doctor') return cmdDoctor(flags);
  if (!cmd) { help(); return; }
  console.log(C.r(`未知命令: ${cmd}`));
  help();
  process.exit(1);
}

main().catch((e) => { console.error(C.r('错误: ' + e.message)); process.exit(1); });
