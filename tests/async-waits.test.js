import test from 'node:test';
import assert from 'node:assert/strict';
import { runSequential, runParallel, WAIT_MS, TASK_COUNT } from '../src/async-waits.js';

test('three independent waits of 1000 ms', () => {
  assert.equal(WAIT_MS, 1000);
  assert.equal(TASK_COUNT, 3);
});

test('sequential starts each wait after the previous resolves', async () => {
  const pending = [];
  const done = runSequential(ms => new Promise(resolve => pending.push({ ms, resolve })));
  for (let index = 0; index < TASK_COUNT; index++) {
    assert.equal(pending.length, index + 1);
    assert.equal(pending[index].ms, WAIT_MS);
    pending[index].resolve();
    await Promise.resolve();
  }
  await done;
});

test('parallel creates every promise before awaiting and waits for all', async () => {
  const pending = [];
  let finished = false;
  const done = runParallel(ms => new Promise(resolve => pending.push({ ms, resolve })));
  done.then(() => { finished = true; });
  assert.equal(pending.length, TASK_COUNT);
  assert.ok(pending.every(task => task.ms === WAIT_MS));
  pending.slice(0, -1).forEach(task => task.resolve());
  await Promise.resolve();
  assert.equal(finished, false);
  pending.at(-1).resolve();
  await done;
});
