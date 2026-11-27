import { ROUTES, asyncSample, measureAsync, stats, requestApi, requestJSON,
  validateSnapshot, pollRestart } from './demo-client.js';

const $ = id => document.getElementById(id);
let asyncRows = [];
let history = [];
let scenarioResult = null;
let lastSnapshot = null;
let busy = false;

function notice(message, error = false) {
  $('notice').textContent = message;
  $('notice').classList.toggle('error', error);
}

function tableRow(target, cells, bad = false) {
  target.querySelector('.empty')?.remove();
  const row = document.createElement('tr');
  for (const value of cells) {
    const cell = document.createElement('td');
    cell.textContent = String(value);
    row.append(cell);
  }
  if (bad) row.lastElementChild.classList.add('bad');
  target.append(row);
}

function setBusy(value) {
  busy = value;
  document.body.classList.toggle('busy', value);
  document.querySelectorAll('[data-action]').forEach(button => { button.disabled = value; });
  $('token').disabled = value;
  $('csv').disabled = value || !asyncRows.length;
  $('json').disabled = value || !history.length;
}

async function action(operation) {
  if (busy) return;
  const token = $('token').value;
  if (!token) { notice('Nhập DEMO_TOKEN trước khi chạy.', true); $('token').focus(); return; }
  setBusy(true);
  try {
    await operation(token);
  } catch (error) {
    const detail = error.name === 'AbortError' ? 'Quá thời gian chờ 15 giây.' : error.message;
    notice(`FAIL: ${detail} Thao tác thay đổi state không tự retry; dùng Đọc lại để kiểm tra.`, true);
  } finally {
    setBusy(false);
  }
}

function renderAsync(row, warmup = false) {
  tableRow($('async-rows'), [warmup ? 'Warm-up' : row.trial,
    row.route.endsWith('/seq') ? 'Tuần tự' : 'Đồng thời', row.status ?? '—',
    row.total_ms === null ? '—' : `${row.total_ms.toFixed(1)} ms`,
    row.error || JSON.stringify(row.body)], Boolean(row.error));
  if (!warmup) asyncRows.push(row);
  for (const [index, name] of ['seq', 'parallel'].entries()) {
    const summary = stats(asyncRows.filter(sample => sample.route === ROUTES[index]));
    $(`${name}-median`).textContent = summary.median_ms === null ? '—' : `${summary.median_ms.toFixed(1)} ms`;
    $(`${name}-count`).textContent = `${summary.valid_samples} mẫu hợp lệ · ${summary.invalid_samples} lỗi`;
  }
}

function showSnapshot(label, value, check = 'Đã đọc API') {
  validateSnapshot(value);
  lastSnapshot = value;
  $('memory').textContent = value.memory_value;
  $('durable').textContent = value.durable_value;
  $('object-id').textContent = value.object_id;
  $('instance-id').textContent = value.instance_id;
  const item = { recorded_at: new Date().toISOString(), step: label, snapshot: value, check };
  history.push(item);
  tableRow($('state-rows'), [label, value.memory_value, value.durable_value, check]);
}

const read = async token => validateSnapshot(await requestJSON(token, '/api/state'));
const post = async (token, name) => validateSnapshot(await requestJSON(token, `/api/state/${name}`, 'POST'));

function requireValues(value, memory, durable) {
  if (value.memory_value !== memory || value.durable_value !== durable) {
    throw new Error(`Cần ${memory}/${durable}, API trả ${value.memory_value}/${value.durable_value}.`);
  }
}

async function restart(token, before, record) {
  $('previous-instance').textContent = before.instance_id;
  record.before_restart = before;
  record.restart_request = { attempts: 1 };
  try {
    const result = await requestApi(token, '/api/state/restart', { method: 'POST' });
    record.restart_request.status = result.status;
    record.restart_request.body = result.body;
  } catch (error) {
    record.restart_request.error = error.message;
  }
  notice('Đang kiểm tra instance mới… Đọc tối đa 10 lượt, cách nhau 500 ms.');
  record.polls = [];
  const after = await pollRestart(() => read(token), before, { onPoll: poll => record.polls.push(poll) });
  record.after_restart = after;
  showSnapshot('Sau restart object', after, 'PASS · instance mới, cùng object, RAM = 0, SQLite giữ nguyên');
  return after;
}

$('token-form').addEventListener('submit', event => {
  event.preventDefault();
  action(async token => { showSnapshot('Kết nối / Đọc', await read(token)); notice('Đã kết nối. Có thể chạy hai demo.'); });
});

for (const [index, id] of ['seq', 'parallel'].entries()) {
  $(id).addEventListener('click', () => action(async token => {
    notice('Đang chờ response hoàn tất…');
    const row = await asyncSample(token, ROUTES[index], asyncRows.length + 1);
    renderAsync(row);
    if (row.error) throw new Error(row.error);
    notice(`HTTP ${row.status} · body ${JSON.stringify(row.body)} · ${row.total_ms.toFixed(1)} ms`);
  }));
}

$('benchmark').addEventListener('click', () => action(async token => {
  asyncRows = [];
  $('async-rows').replaceChildren();
  notice('Đang warm-up rồi đo 5 lượt mỗi cách. Vui lòng chờ khoảng 24 giây.');
  const result = await measureAsync(token, (row, warmup) => {
    renderAsync(row, warmup);
    $('async-progress').textContent = `${warmup ? 'Warm-up' : `Lượt ${row.trial}/5`} · ${row.route} · ${row.error || 'đã đọc hết body'}`;
  });
  notice(result.passed ? 'PASS · Đã đo đủ 5 lượt mỗi cách; median chỉ lấy mẫu hợp lệ.'
    : 'FAIL · Có mẫu lỗi; vẫn giữ dữ liệu thật và loại mẫu lỗi khỏi median.', !result.passed);
}));

$('clear').addEventListener('click', () => {
  if (busy) return;
  asyncRows = [];
  $('async-rows').replaceChildren();
  for (const name of ['seq', 'parallel']) {
    $(`${name}-median`).textContent = '—';
    $(`${name}-count`).textContent = 'Chưa có mẫu';
  }
  $('async-progress').textContent = 'Đã xóa kết quả trên trang. Counter không thay đổi.';
  setBusy(false);
});

$('read').addEventListener('click', () => action(async token => {
  showSnapshot('Đọc lại', await read(token)); notice('Đã đọc state; GET không tăng hoặc reset dữ liệu.');
}));
$('increment').addEventListener('click', () => action(async token => {
  showSnapshot('Tăng một lần', await post(token, 'increment')); notice('Đã tăng cả hai đúng một request.');
}));
$('reset').addEventListener('click', () => action(async token => {
  const value = await post(token, 'reset');
  showSnapshot('Reset dữ liệu', value); requireValues(value, 0, 0); notice('Đã reset 0/0.');
}));
$('restart').addEventListener('click', () => action(async token => {
  const record = { recorded_at: new Date().toISOString(), passed: false };
  scenarioResult = record;
  try {
    await restart(token, await read(token), record);
    record.passed = true;
    notice('PASS · instance_id đổi, object_id giữ nguyên; SQLite được giữ lại.');
  } catch (error) { record.error = error.message; throw error; }
}));

$('scenario').addEventListener('click', () => action(async token => {
  const result = { base_url: location.origin, recorded_at: new Date().toISOString(), passed: false, increments: [] };
  scenarioResult = result;
  history = [];
  $('state-rows').replaceChildren();
  try {
    notice('Đang chạy kịch bản 0/0 → 3/3 → restart → 0/3 → 1/4…');
    const reset = await post(token, 'reset');
    result.after_reset = reset;
    showSnapshot('Reset dữ liệu', reset); requireValues(reset, 0, 0);
    for (let step = 1; step <= 3; step++) {
      const value = await post(token, 'increment');
      result.increments.push(value);
      showSnapshot(`Tăng lần ${step}`, value); requireValues(value, step, step);
      if (value.object_id !== reset.object_id || value.instance_id !== reset.instance_id) {
        throw new Error('Object/instance thay đổi trước khi yêu cầu restart.');
      }
    }
    const before = await read(token);
    requireValues(before, 3, 3);
    const after = await restart(token, before, result);
    requireValues(after, 0, 3);
    const updated = await post(token, 'increment');
    result.after_increment = updated;
    showSnapshot('Tăng sau restart', updated); requireValues(updated, 1, 4);
    if (updated.object_id !== before.object_id || updated.instance_id !== after.instance_id) {
      throw new Error('Object/instance thay đổi sau restart.');
    }
    const final = await read(token);
    result.final_read = final;
    requireValues(final, 1, 4);
    if (final.object_id !== updated.object_id || final.instance_id !== updated.instance_id) {
      throw new Error('Identity thay đổi trong lần đọc cuối.');
    }
    result.passed = true;
    notice('PASS · 0/0 → 3/3 → 0/3 → 1/4. Cùng object_id, instance_id mới.');
  } catch (error) { result.error = error.message; throw error; }
}));

function download(name, type, contents) {
  const url = URL.createObjectURL(new Blob([contents], { type }));
  const link = document.createElement('a');
  link.href = url; link.download = name; document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

$('csv').addEventListener('click', () => {
  const fields = ['trial', 'route', 'status', 'total_ms', 'body_ok', 'error'];
  const escape = value => `"${String(value ?? '').replaceAll('"', '""')}"`;
  download('async_samples.csv', 'text/csv;charset=utf-8',
    fields.join(',') + '\r\n' + asyncRows.map(row => fields.map(field => escape(row[field])).join(',')).join('\r\n') + '\r\n');
});
$('json').addEventListener('click', () => download('state_run.json', 'application/json', JSON.stringify({
  base_url: location.origin, recorded_at: new Date().toISOString(), history,
  last_snapshot: lastSnapshot, scenario: scenarioResult,
}, null, 2)));

$('origin').textContent = location.origin;
requestApi('', '/api/health').then(result => {
  if (result.status !== 200) throw new Error(`HTTP ${result.status}`);
  $('health').textContent = location.hostname === 'localhost' || location.hostname === '127.0.0.1'
    ? 'Wrangler local' : 'Cloudflare Workers';
}).catch(() => { $('health').textContent = 'Chưa kết nối Worker'; });
