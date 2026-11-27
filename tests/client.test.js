import test from 'node:test';
import assert from 'node:assert/strict';
import { requestApi, pollRestart, measureAsync } from '../public/demo-client.js';

test('client waits for the full body before resolving or reporting time', async () => {
  let releaseBody;
  let finished = false;
  const body = new Promise(resolve => { releaseBody = resolve; });
  const pending = requestApi('test-only', '/api/async/seq', {
    fetchImpl: async () => ({ status: 200, text: () => body }),
  });
  pending.then(() => { finished = true; });
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(finished, false);
  releaseBody('done\n');
  const response = await pending;
  assert.equal(response.body, 'done\n');
  assert.ok(response.total_ms >= 0);
});

test('a failed POST is sent once', async () => {
  let calls = 0;
  await assert.rejects(requestApi('test-only', '/api/state/increment', {
    method: 'POST', fetchImpl: async () => { calls++; throw new Error('connection lost'); },
  }), /connection lost/);
  assert.equal(calls, 1);
});

test('restart polling is bounded and unchanged instance never passes', async () => {
  const before = { memory_value: 3, durable_value: 3, instance_id: 'old',
    object_id: 'same', counter_name: 'seminar-demo-2' };
  let calls = 0;
  await assert.rejects(pollRestart(async () => { calls++; return before; }, before,
    { sleep: async () => {} }), /instance/);
  assert.equal(calls, 10);
  await assert.rejects(pollRestart(async () => ({ ...before, instance_id: 'new', object_id: 'wrong' }),
    before, { sleep: async () => {} }), /object_id/);
  const after = { ...before, instance_id: 'new', memory_value: 0 };
  assert.deepEqual(await pollRestart(async () => after, before), after);
});

test('browser benchmark warms up and alternates five pairs', async () => {
  const routes = [];
  const result = await measureAsync('test-only', () => {}, {
    request: async (token, route) => {
      routes.push(route);
      return { status: 200, body: 'done\n', total_ms: route.endsWith('/seq') ? 3000 : 1000 };
    },
  });
  assert.equal(routes.length, 12);
  assert.deepEqual(routes.slice(2, 6), ['/api/async/seq', '/api/async/parallel',
    '/api/async/parallel', '/api/async/seq']);
  assert.equal(result.rows.length, 10);
  assert.equal(result.summary.seq.median_ms, 3000);
  assert.equal(result.summary.parallel.valid_samples, 5);
});
