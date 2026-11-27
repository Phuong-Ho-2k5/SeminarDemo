// DOM + real HTTP integration. This is not a visual/browser rendering test.
import { JSDOM } from 'jsdom';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const baseIndex = process.argv.indexOf('--base-url');
const base = baseIndex >= 0 ? process.argv[baseIndex + 1] : 'http://127.0.0.1:8787';
const local = ['127.0.0.1', 'localhost', '::1'].includes(new URL(base).hostname);
if (!local && new URL(base).protocol !== 'https:') throw new Error('Remote URL must use HTTPS');
let token = process.env.DEMO_TOKEN;
if (!token && local) {
  token = /^DEMO_TOKEN="([^"]+)"/m.exec(await readFile(path.join(root, '.dev.vars'), 'utf8'))?.[1];
}
if (!token) throw new Error('Set DEMO_TOKEN in the environment; it will not be printed.');
const result = { recorded_at: new Date().toISOString(), base_url: base,
  mode: 'JSDOM + real HTTP; no visual browser rendering', passed: false, checks: [] };
const networkFetch = globalThis.fetch;
let requests = [];
let failNextIncrement = false;
let loseNextIncrementResponse = false;
globalThis.fetch = async (route, options = {}) => {
  requests.push({ route, method: options.method ?? 'GET' });
  if (failNextIncrement && route === '/api/state/increment') {
    failNextIncrement = false;
    throw new Error('Test: ambiguous network failure');
  }
  const response = await networkFetch(new URL(route, base), options);
  if (loseNextIncrementResponse && route === '/api/state/increment') {
    loseNextIncrementResponse = false;
    await response.text(); // Server committed; client loses the completed response.
    throw new Error('Test: response lost after server commit');
  }
  return response;
};

function check(name, condition) {
  result.checks.push({ name, passed: Boolean(condition) });
  if (!condition) throw new Error(name);
}
async function until(predicate, timeout = 45000) {
  const started = Date.now();
  while (!predicate()) {
    if (Date.now() - started > timeout) throw new Error('Timed out waiting for UI');
    await new Promise(resolve => setTimeout(resolve, 25));
  }
}
const downloads = [];
const originalObjectURL = URL.createObjectURL;
URL.createObjectURL = blob => { downloads.push(blob); return 'blob:test-download'; };
const originalRevoke = URL.revokeObjectURL;
URL.revokeObjectURL = () => {};
let dom;
const $ = id => document.getElementById(id);
const displayed = () => [$('memory').textContent, $('durable').textContent];
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

async function mount(html, number) {
  dom = new JSDOM(html, { url: base });
  dom.window.HTMLAnchorElement.prototype.click = function () {};
  globalThis.document = dom.window.document;
  globalThis.location = dom.window.location;
  await import(new URL(`../public/app.js?ui-check=${number}`, import.meta.url));
  await until(() => !$('health').textContent.includes('Đang'));
}
async function click(id) {
  $(id).click();
  await until(() => !$('token').disabled);
}
async function connect(value) {
  $('token').value = value;
  $('token-form').dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }));
  await until(() => !$('token').disabled);
}

try {
  const html = await (await networkFetch(base + '/')).text();
  for (const file of ['index.html', 'app.js', 'demo-client.js', 'style.css']) {
    const remote = await (await networkFetch(base + (file === 'index.html' ? '/' : '/' + file))).text();
    const source = await readFile(path.join(root, 'public', file), 'utf8');
    const hash = value => createHash('sha256').update(value).digest('hex');
    check(`served ${file} matches source`, hash(remote) === hash(source));
  }
  await mount(html, 1);
  check('only health GET on page load', requests.length === 1 && requests[0].route === '/api/health');
  await connect('intentionally-wrong-token');
  check('wrong token gives error and restores buttons', $('notice').textContent.includes('401') && !$('scenario').disabled);
  await connect(token);
  check('valid token reads state', $('object-id').textContent !== '—');
  await click('seq');
  await click('parallel');
  check('single-run buttons show real completed responses', $('async-rows').rows.length === 2
    && $('async-rows').textContent.includes('200') && $('async-rows').textContent.includes('done'));
  await click('benchmark');
  check('benchmark shows warmups and ten measured samples', $('async-rows').rows.length === 12);
  check('both medians have five valid samples', $('seq-count').textContent.includes('5 mẫu hợp lệ')
    && $('parallel-count').textContent.includes('5 mẫu hợp lệ'));
  $('csv').click();
  const csv = await downloads.at(-1).text();
  check('CSV has header + 10 samples, no secret', csv.trim().split(/\r?\n/).length === 11 && !csv.includes(token));
  await click('clear');
  check('clear resets visible timing results', $('async-rows').rows.length === 0 && $('seq-median').textContent === '—');
  await click('reset');
  check('reset UI 0/0', same(displayed(), ['0', '0']));
  for (let index = 0; index < 3; index++) await click('increment');
  check('increment UI 3/3', same(displayed(), ['3', '3']));
  const beforeInstance = $('instance-id').textContent;
  const objectId = $('object-id').textContent;
  await click('read');
  check('read button unchanged', same(displayed(), ['3', '3']) && $('instance-id').textContent === beforeInstance);
  await click('restart');
  check('restart UI 0/3 with real identity comparison', same(displayed(), ['0', '3'])
    && $('instance-id').textContent !== beforeInstance && $('object-id').textContent === objectId
    && $('notice').textContent.startsWith('PASS'));
  await click('increment');
  check('increment after restart UI 1/4', same(displayed(), ['1', '4']));
  await click('scenario');
  check('full scenario UI PASS', same(displayed(), ['1', '4']) && $('notice').textContent.startsWith('PASS'));
  $('json').click();
  const jsonText = await downloads.at(-1).text();
  const saved = JSON.parse(jsonText);
  check('JSON has successful real snapshots and no secret', saved.scenario.passed
    && saved.scenario.after_restart.memory_value === 0 && saved.scenario.after_restart.durable_value === 3
    && !jsonText.includes(token));
  requests = [];
  failNextIncrement = true;
  await click('increment');
  check('failed POST is not retried and controls recover', requests.filter(item => item.route === '/api/state/increment').length === 1
    && $('notice').textContent.startsWith('FAIL') && !$('scenario').disabled);
  requests = [];
  loseNextIncrementResponse = true;
  await click('increment');
  check('lost committed response gives error without retry', requests.filter(item => item.route === '/api/state/increment').length === 1
    && $('notice').textContent.startsWith('FAIL') && !$('scenario').disabled);
  await click('read');
  check('read recovers actual committed 2/5 after lost response', same(displayed(), ['2', '5']));
  await click('scenario');
  check('explicit fresh scenario restores expected 1/4', same(displayed(), ['1', '4']) && $('notice').textContent.startsWith('PASS'));
  requests = [];
  await mount(html, 2);
  check('refresh loses token and sends only a health GET', $('token').value === '' && requests.length === 1
    && requests[0].route === '/api/health');
  await connect(token);
  check('refresh/reconnect preserves 1/4', same(displayed(), ['1', '4']));
  result.passed = true;
} catch (error) {
  result.error = error.message;
} finally {
  globalThis.fetch = networkFetch;
  URL.createObjectURL = originalObjectURL;
  URL.revokeObjectURL = originalRevoke;
  dom?.window.close();
}
const output = path.join(root, 'results', local ? 'local' : 'cloud', 'ui_checks.json');
await mkdir(path.dirname(output), { recursive: true });
await writeFile(output, JSON.stringify(result, null, 2) + '\n');
console.log(`UI DOM/HTTP ${result.passed ? 'PASS' : 'FAIL'}: ${result.checks.filter(item => item.passed).length}/${result.checks.length}`);
if (result.error) console.log(result.error);
console.log(`Artifact: ${output}`);
process.exitCode = result.passed ? 0 : 1;
