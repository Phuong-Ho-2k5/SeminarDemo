export const ROUTES = ['/api/async/seq', '/api/async/parallel'];

export async function requestApi(token, route, { method = 'GET', fetchImpl = fetch, timeoutMs = 15000 } = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const started = performance.now();
  try {
    const response = await fetchImpl(route, {
      method, headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store', redirect: 'error', signal: controller.signal,
    });
    const body = await response.text();
    return { status: response.status, body, total_ms: performance.now() - started };
  } finally {
    clearTimeout(timeout);
  }
}

export async function requestJSON(token, route, method = 'GET') {
  const response = await requestApi(token, route, { method });
  if (response.status !== 200) throw new Error(`HTTP ${response.status}: ${response.body.slice(0, 300)}`);
  return JSON.parse(response.body);
}

export function validateSnapshot(value) {
  if (!value || !Number.isSafeInteger(value.memory_value) || value.memory_value < 0
      || !Number.isSafeInteger(value.durable_value) || value.durable_value < 0
      || typeof value.instance_id !== 'string' || !value.instance_id
      || typeof value.object_id !== 'string' || !value.object_id
      || value.counter_name !== 'seminar-demo-2') throw new Error('Snapshot không hợp lệ.');
  return value;
}

const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

export async function pollRestart(read, before, { sleep = pause, onPoll = () => {} } = {}) {
  validateSnapshot(before);
  for (let attempt = 1; attempt <= 10; attempt++) {
    if (attempt > 1) await sleep(500);
    let observed;
    try {
      observed = validateSnapshot(await read());
    } catch (error) {
      onPoll({ attempt, error: error.message });
      continue;
    }
    onPoll({ attempt, snapshot: observed });
    if (observed.object_id !== before.object_id || observed.counter_name !== before.counter_name) {
      throw new Error('object_id hoặc counter_name đã đổi; không thể xác nhận restart cùng object.');
    }
    if (observed.instance_id !== before.instance_id) {
      if (observed.memory_value !== 0 || observed.durable_value !== before.durable_value) {
        throw new Error('Instance mới nhưng RAM/SQLite không đúng giá trị cần kiểm chứng.');
      }
      return observed;
    }
  }
  throw new Error('FAIL: instance_id chưa đổi sau tối đa 10 lượt đọc.');
}

export async function asyncSample(token, route, trial, request = requestApi) {
  const row = { trial, route, status: null, total_ms: null, body_ok: false, error: '' };
  try {
    const response = await request(token, route);
    Object.assign(row, { status: response.status, body: response.body,
      total_ms: response.total_ms, body_ok: response.body === 'done\n' });
    if (row.status !== 200 || !row.body_ok) row.error = 'Cần HTTP 200 và body done\\n.';
  } catch (error) {
    row.error = error.name === 'AbortError' ? 'Timeout 15 giây.' : error.message;
  }
  return row;
}

export function stats(rows) {
  const valid = rows.filter(row => !row.error && row.status === 200 && row.body_ok)
    .map(row => row.total_ms).sort((a, b) => a - b);
  const middle = Math.floor(valid.length / 2);
  return { valid_samples: valid.length, invalid_samples: rows.length - valid.length,
    median_ms: valid.length ? (valid.length % 2 ? valid[middle] : (valid[middle - 1] + valid[middle]) / 2) : null };
}

export async function measureAsync(token, onSample, { request = requestApi } = {}) {
  const warmups = [];
  for (const route of ROUTES) {
    const row = await asyncSample(token, route, 0, request);
    warmups.push(row);
    onSample(row, true);
  }
  const rows = [];
  for (let trial = 1; trial <= 5; trial++) {
    const order = trial % 2 ? ROUTES : [...ROUTES].reverse();
    for (const route of order) {
      const row = await asyncSample(token, route, trial, request);
      rows.push(row);
      onSample(row, false);
    }
  }
  return { rows, warmups, passed: [...warmups, ...rows].every(row => !row.error),
    summary: { seq: stats(rows.filter(row => row.route === ROUTES[0])),
      parallel: stats(rows.filter(row => row.route === ROUTES[1])) } };
}
