import test from 'node:test';
import assert from 'node:assert/strict';
import { authorize } from '../src/auth.js';

test('missing server secret fails closed', async () => {
  assert.equal(await authorize(new Request('https://example.test'), {}), 503);
});

test('missing, wrong, malformed tokens are denied; only exact Bearer passes', async () => {
  for (const value of ['', 'Bearer wrong', 'Basic secret', 'Bearer secret-extra']) {
    const request = new Request('https://example.test', { headers: { Authorization: value } });
    assert.equal(await authorize(request, { DEMO_TOKEN: 'secret' }), 401);
  }
  assert.equal(await authorize(new Request('https://example.test', {
    headers: { Authorization: 'Bearer secret' },
  }), { DEMO_TOKEN: 'secret' }), 200);
});
