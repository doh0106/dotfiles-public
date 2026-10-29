const state = { ghostty: [], iterm: [], catalog: { ghostty: [], iterm: [] } };
const $ = (selector) => document.querySelector(selector);

function status(message, type = '') {
  const element = $('#status');
  element.textContent = message;
  element.className = type;
}

function validColor(value, fallback) {
  return /^#[0-9a-f]{6}$/i.test(value || '') ? value : fallback;
}

function updatePreview(rule, kind) {
  const path = rule.querySelector('.path').value || '~/project';
  rule.querySelectorAll('.path-preview').forEach((element) => { element.textContent = path.startsWith('~') ? path : `~/${path}`; });
  if (kind === 'ghostty') {
    const background = validColor(rule.querySelector('.background').value, '#1b222c');
    const foreground = validColor(rule.querySelector('.foreground').value, '#d4dee9');
    const preview = rule.querySelector('.terminal-preview');
    preview.style.background = background;
    preview.style.color = foreground;
  } else {
    const color = validColor(rule.querySelector('.color').value, '#2980b9');
    rule.querySelector('.dot').style.background = color;
    rule.querySelector('.iterm-preview').style.borderTop = `3px solid ${color}`;
  }
}

function colorControls(rule, kind) {
  const pairs = kind === 'ghostty'
    ? [['.background', '.background-picker'], ['.foreground', '.foreground-picker']]
    : [['.color', '.tab-picker']];
  pairs.forEach(([hexSelector, pickerSelector]) => {
    const hex = rule.querySelector(hexSelector);
    const picker = rule.querySelector(pickerSelector);
    picker.value = validColor(hex.value, picker.value);
    picker.addEventListener('input', () => { hex.value = picker.value.toUpperCase(); updatePreview(rule, kind); });
    hex.addEventListener('input', () => { if (/^#[0-9a-f]{6}$/i.test(hex.value)) picker.value = hex.value; updatePreview(rule, kind); });
  });
}

function addSwatches(rule, kind) {
  const destination = rule.querySelector('.swatches');
  for (const preset of state.catalog[kind]) {
    const button = document.createElement('button');
    button.className = 'swatch';
    const color = kind === 'ghostty' ? preset.background : preset.color;
    button.innerHTML = `<span class="sample" style="background:${color}"></span>${preset.name}`;
    button.addEventListener('click', () => {
      if (kind === 'ghostty') {
        rule.querySelector('.background').value = preset.background.toUpperCase();
        rule.querySelector('.foreground').value = preset.foreground.toUpperCase();
        rule.querySelector('.background-picker').value = preset.background;
        rule.querySelector('.foreground-picker').value = preset.foreground;
      } else {
        rule.querySelector('.color').value = preset.color.toUpperCase();
        rule.querySelector('.tab-picker').value = preset.color;
      }
      updatePreview(rule, kind);
    });
    destination.append(button);
  }
}

function addRule(kind, data = {}) {
  const template = $(`#${kind}-template`);
  const rule = template.content.firstElementChild.cloneNode(true);
  rule.querySelector('.path').value = data.path || '';
  if (kind === 'ghostty') {
    rule.querySelector('.background').value = (data.background || '#1b222c').toUpperCase();
    rule.querySelector('.foreground').value = (data.foreground || '#d4dee9').toUpperCase();
  } else rule.querySelector('.color').value = (data.color || '#2980b9').toUpperCase();
  rule.querySelector('.remove').addEventListener('click', () => rule.remove());
  rule.querySelector('.folder').addEventListener('click', async () => {
    try {
      status('macOS 폴더 선택 창을 여는 중…');
      const response = await fetch('/api/pick-folder', { method: 'POST' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error);
      rule.querySelector('.path').value = result.path;
      updatePreview(rule, kind);
      status('');
    } catch (error) { status(error.message, 'error'); }
  });
  rule.querySelector('.path').addEventListener('input', () => updatePreview(rule, kind));
  colorControls(rule, kind);
  addSwatches(rule, kind);
  updatePreview(rule, kind);
  $(`#${kind}-rules`).append(rule);
}

function collect(kind) {
  return [...$(`#${kind}-rules`).children].map((rule) => kind === 'ghostty'
    ? { path: rule.querySelector('.path').value, background: rule.querySelector('.background').value, foreground: rule.querySelector('.foreground').value }
    : { path: rule.querySelector('.path').value, color: rule.querySelector('.color').value });
}

async function load() {
  const response = await fetch('/api/config');
  const result = await response.json();
  if (!response.ok) throw new Error(result.error);
  state.catalog = result.catalog;
  for (const message of [...result.ghostty.errors, ...result.iterm.errors]) status(message, 'error');
  result.ghostty.rules.forEach((rule) => addRule('ghostty', rule));
  result.iterm.rules.forEach((rule) => addRule('iterm', rule));
}

async function save() {
  try {
    status('저장 중…');
    const response = await fetch('/api/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ghostty: collect('ghostty'), iterm: collect('iterm') }) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
    status('저장됨. 새 zsh를 열거나 source ~/.zshrc 후 테스트하세요.', 'success');
  } catch (error) { status(error.message, 'error'); }
}

document.querySelectorAll('.tab').forEach((tab) => tab.addEventListener('click', () => {
  document.querySelectorAll('.tab, .panel').forEach((element) => element.classList.remove('active'));
  tab.classList.add('active');
  $(`#${tab.dataset.tab}`).classList.add('active');
}));
document.querySelectorAll('[data-add]').forEach((button) => button.addEventListener('click', () => addRule(button.dataset.add)));
$('#save').addEventListener('click', save);
load().catch((error) => status(error.message, 'error'));
