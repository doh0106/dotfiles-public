import { createServer } from 'node:http';
import { readFile, rename, writeFile, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, extname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const toolDir = dirname(fileURLToPath(import.meta.url));
const repoDir = resolve(toolDir, '../..');
const uiDir = resolve(toolDir, 'ui');
const homeDir = homedir();
const configDir = resolve(homeDir, '.config/dotfiles');
const targets = {
  ghostty: process.env.DOTFILES_GHOSTTY_COLORS || resolve(configDir, 'terminal/ghostty.conf'),
  iterm: process.env.DOTFILES_ITERM_COLORS || resolve(configDir, 'terminal/iterm.conf'),
};
for (const [kind, target] of Object.entries(targets)) {
  if (!existsSync(target)) {
    await mkdir(dirname(target), { recursive: true });
    const template = kind === 'ghostty' ? 'ghostty/project-colors.conf' : 'iterm2/tab-colors.conf';
    await writeFile(target, await readFile(resolve(repoDir, 'links/terminal', template)), { flag: 'wx' });
  }
}
const catalog = {
  ghostty: [
    { name: 'Crimson', background: '#321f26', foreground: '#ffe2e6' },
    { name: 'Ocean', background: '#172a36', foreground: '#d6edf8' },
    { name: 'Forest', background: '#1d2b22', foreground: '#d7f0de' },
    { name: 'Violet', background: '#252130', foreground: '#e6ddf5' },
    { name: 'Solar', background: '#302817', foreground: '#f7e8bc' },
    { name: 'Slate', background: '#1b222c', foreground: '#d4dee9' },
    { name: 'Dracula', background: '#282a36', foreground: '#f8f8f2' },
    { name: 'Nord', background: '#2e3440', foreground: '#d8dee9' },
    { name: 'Tokyo Night', background: '#1a1b26', foreground: '#c0caf5' },
    { name: 'Moss', background: '#27301f', foreground: '#e1efcb' },
    { name: 'Rose', background: '#302027', foreground: '#f5dce6' },
    { name: 'Ember', background: '#2c2421', foreground: '#eadfd2' },
    { name: 'Cobalt', background: '#1d2338', foreground: '#dce5ff' },
    { name: 'Carbon', background: '#202124', foreground: '#e8eaed' },
    { name: 'Paper Blue', background: '#eaf4ff', foreground: '#102a43' },
    { name: 'Paper Peach', background: '#fff7ed', foreground: '#7c2d12' },
    { name: 'Paper Mint', background: '#ecfdf5', foreground: '#064e3b' },
    { name: 'Paper Lilac', background: '#f5f3ff', foreground: '#2e1065' },
    { name: 'One Light', background: '#fafafa', foreground: '#383a42' },
    { name: 'Solarized Light HC', background: '#fdf6e3', foreground: '#002b36' },
    { name: 'Gruvbox Light Hard', background: '#f9f5d7', foreground: '#1d2021' },
    { name: 'Catppuccin Latte', background: '#eff1f5', foreground: '#4c4f69' },
  ],
  iterm: [
    { name: 'Red', color: '#d94343' },
    { name: 'Orange', color: '#e67e22' },
    { name: 'Yellow', color: '#f1c40f' },
    { name: 'Green', color: '#27ae60' },
    { name: 'Blue', color: '#2980b9' },
    { name: 'Indigo', color: '#5b5bd6' },
    { name: 'Purple', color: '#8e44ad' },
  ],
};

function json(response, status, value) {
  response.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  response.end(JSON.stringify(value));
}

function contentType(path) {
  return { '.css': 'text/css; charset=utf-8', '.js': 'application/javascript; charset=utf-8', '.html': 'text/html; charset=utf-8' }[extname(path)] || 'application/octet-stream';
}

function relativeHomePath(path) {
  return path === homeDir ? '~' : path.startsWith(`${homeDir}/`) ? path.slice(homeDir.length + 1) : path;
}

function normalizePath(path) {
  if (typeof path !== 'string') throw new Error('경로는 문자열이어야 합니다.');
  const trimmed = path.trim();
  if (!trimmed || /[\r\n]/.test(trimmed)) throw new Error('경로에는 빈 값이나 줄바꿈을 사용할 수 없습니다.');
  return relativeHomePath(trimmed);
}

function splitRule(kind, line) {
  const expectedColors = kind === 'ghostty' ? 2 : 1;
  const parts = [];
  let remainder = line;
  for (let index = 0; index < expectedColors; index += 1) {
    const separator = remainder.lastIndexOf('|');
    if (separator < 0) return null;
    parts.unshift(remainder.slice(separator + 1).trim());
    remainder = remainder.slice(0, separator);
  }
  return [remainder.trim(), ...parts];
}

function color(value, label) {
  if (typeof value !== 'string' || !/^#[0-9a-fA-F]{6}$/.test(value)) throw new Error(`${label}은 #RRGGBB 형식이어야 합니다.`);
  return value.toLowerCase();
}

async function readRules(kind) {
  const source = await readFile(targets[kind], 'utf8');
  const rules = [];
  const comments = [];
  const errors = [];
  source.split(/\r?\n/).forEach((line, index) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    if (trimmed.startsWith('#')) {
      comments.push(line);
      return;
    }
    const parts = splitRule(kind, line);
    if (!parts) {
      errors.push(`${index + 1}행: 규칙 형식이 아닙니다.`);
      return;
    }
    try {
      const path = normalizePath(parts[0]);
      rules.push(kind === 'ghostty'
        ? { path, background: color(parts[1], '배경색'), foreground: color(parts[2], '전경색') }
        : { path, color: color(parts[1], '탭 색') });
    } catch (error) {
      errors.push(`${index + 1}행: ${error.message}`);
    }
  });
  return { rules, comments, errors };
}

function validateRules(kind, rules) {
  if (!Array.isArray(rules)) throw new Error('규칙 목록 형식이 올바르지 않습니다.');
  const paths = new Set();
  return rules.map((rule) => {
    const path = normalizePath(rule.path);
    if (paths.has(path)) throw new Error(`중복된 경로 규칙입니다: ${path}`);
    paths.add(path);
    return kind === 'ghostty'
      ? { path, background: color(rule.background, '배경색'), foreground: color(rule.foreground, '전경색') }
      : { path, color: color(rule.color, '탭 색') };
  });
}

function renderRules(kind, comments, rules) {
  const lines = [...comments, ''];
  for (const rule of rules) {
    lines.push(kind === 'ghostty'
      ? `${rule.path}|${rule.background}|${rule.foreground}`
      : `${rule.path}|${rule.color}`);
  }
  return `${lines.join('\n')}\n`;
}

async function saveRules(kind, rules) {
  const current = await readRules(kind);
  if (current.errors.length) throw new Error(`${kind} 설정에 형식 오류가 있어 저장할 수 없습니다: ${current.errors.join(' ')}`);
  const validated = validateRules(kind, rules);
  const target = targets[kind];
  const temporary = `${target}.tmp-${process.pid}`;
  await writeFile(temporary, renderRules(kind, current.comments, validated), 'utf8');
  await rename(temporary, target);
  return validated;
}

function chooseFolder() {
  return new Promise((resolvePromise, reject) => {
    const script = 'POSIX path of (choose folder with prompt "프로젝트 색상을 적용할 폴더를 선택하세요")';
    const process = spawn('osascript', ['-e', script]);
    let output = '';
    let error = '';
    process.stdout.on('data', (chunk) => { output += chunk; });
    process.stderr.on('data', (chunk) => { error += chunk; });
    process.on('error', reject);
    process.on('close', (code) => {
      if (code === 0) resolvePromise(relativeHomePath(output.trim().replace(/\/$/, '')));
      else reject(new Error(error.trim() || '폴더 선택을 취소했습니다.'));
    });
  });
}

async function requestBody(request) {
  let body = '';
  for await (const chunk of request) {
    body += chunk;
    if (body.length > 1_000_000) throw new Error('요청이 너무 큽니다.');
  }
  return JSON.parse(body || '{}');
}

const server = createServer(async (request, response) => {
  try {
    const expectedHost = `127.0.0.1:${server.address().port}`;
    if (request.headers.host !== expectedHost) return json(response, 403, { error: 'Invalid host' });
    if (request.method === 'POST' && request.headers.origin !== `http://${expectedHost}`) {
      return json(response, 403, { error: 'Invalid origin' });
    }
    const url = new URL(request.url, `http://${expectedHost}`);
    if (request.method === 'GET' && url.pathname === '/api/config') {
      const [ghostty, iterm] = await Promise.all([readRules('ghostty'), readRules('iterm')]);
      return json(response, 200, { ghostty, iterm, catalog, homeDir });
    }
    if (request.method === 'POST' && url.pathname === '/api/pick-folder') {
      return json(response, 200, { path: await chooseFolder() });
    }
    if (request.method === 'POST' && url.pathname === '/api/save') {
      const body = await requestBody(request);
      const [ghostty, iterm] = await Promise.all([saveRules('ghostty', body.ghostty), saveRules('iterm', body.iterm)]);
      return json(response, 200, { ghostty, iterm });
    }
    if (request.method === 'GET') {
      const requested = url.pathname === '/' ? 'index.html' : url.pathname.slice(1);
      const file = resolve(uiDir, requested);
      if (!file.startsWith(`${uiDir}/`) || !existsSync(file)) return json(response, 404, { error: '찾을 수 없습니다.' });
      response.writeHead(200, { 'Content-Type': contentType(file), 'Cache-Control': 'no-store' });
      response.end(await readFile(file));
      return;
    }
    return json(response, 405, { error: '지원하지 않는 요청입니다.' });
  } catch (error) {
    return json(response, 400, { error: error.message || '요청을 처리하지 못했습니다.' });
  }
});

server.listen(0, '127.0.0.1', () => {
  const { port } = server.address();
  const url = `http://127.0.0.1:${port}`;
  console.log(`Terminal colors UI: ${url}`);
  console.log('종료하려면 Ctrl-C를 누르세요.');
  if (process.env.DOTFILES_NO_BROWSER !== '1') {
    const opener = spawn(process.platform === 'darwin' ? 'open' : 'xdg-open', [url], { detached: true, stdio: 'ignore' });
    opener.on('error', () => console.log('Open the URL above in your browser.'));
    opener.unref();
  }
});

function close() {
  server.close(() => process.exit(0));
}
process.on('SIGINT', close);
process.on('SIGTERM', close);
