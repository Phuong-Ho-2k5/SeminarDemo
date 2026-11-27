import { authorize } from './auth.js';
import { runSequential, runParallel } from './async-waits.js';
import { COUNTER_NAME } from './durable-counter.js';
export { PersistentCounter } from './durable-counter.js';

function json(data, status = 200, headers = {}) {
  return Response.json(data, { status, headers: { 'Cache-Control': 'no-store', ...headers } });
}

const stateMethods = new Map([
  ['/api/state', ['GET', 'read']],
  ['/api/state/increment', ['POST', 'increment']],
  ['/api/state/reset', ['POST', 'resetData']],
  ['/api/state/restart', ['POST', 'restartForDemo']],
]);

async function handleApi(request, env, pathname, requestId) {
  if (pathname === '/api/health') {
    return request.method === 'GET'
      ? json({ application: 'neon-workers-seminar', status: 'ok' })
      : json({ error: 'METHOD_NOT_ALLOWED' }, 405, { Allow: 'GET' });
  }
  const auth = await authorize(request, env);
  if (auth !== 200) return json({ error: auth === 503 ? 'DEMO_TOKEN_NOT_CONFIGURED' : 'UNAUTHORIZED' }, auth);

  if (pathname === '/api/async/seq' || pathname === '/api/async/parallel') {
    if (request.method !== 'GET') return json({ error: 'METHOD_NOT_ALLOWED' }, 405, { Allow: 'GET' });
    console.log(JSON.stringify({ route: pathname, request_id: requestId }));
    await (pathname.endsWith('/seq') ? runSequential() : runParallel());
    return new Response('done\n', { headers: {
      'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store',
    } });
  }

  const route = stateMethods.get(pathname);
  if (!route) return json({ error: 'NOT_FOUND' }, 404);
  const [method, operation] = route;
  if (request.method !== method) return json({ error: 'METHOD_NOT_ALLOWED' }, 405, { Allow: method });
  console.log(JSON.stringify({ route: pathname, request_id: requestId }));
  // A fresh stub per HTTP request; no retry loop for any state operation.
  const counter = env.COUNTER.getByName(COUNTER_NAME);
  if (operation === 'restartForDemo') {
    try {
      await counter.restartForDemo();
    } catch {
      return json({ error: 'OBJECT_RESTART_PENDING',
        message: 'Request restart ended. Read state to verify object_id and instance_id.' }, 503);
    }
    return json({ status: 'RESTART_REQUEST_SENT', verified: false }, 202);
  }
  return json(await counter[operation]());
}

export default {
  async fetch(request, env) {
    const pathname = new URL(request.url).pathname;
    if (!pathname.startsWith('/api/')) return env.ASSETS.fetch(request);
    const requestId = crypto.randomUUID();
    let response;
    try {
      response = await handleApi(request, env, pathname, requestId);
    } catch {
      console.error(JSON.stringify({ event: 'API_ERROR', route: pathname, request_id: requestId }));
      response = json({ error: 'API_ERROR', request_id: requestId }, 500);
    }
    response.headers.set('X-Request-Id', requestId);
    response.headers.set('X-Content-Type-Options', 'nosniff');
    return response;
  },
};
