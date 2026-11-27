// Read-only account inspection. Never prints the Wrangler OAuth/API credential.
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';

const accountId = process.argv[2] ?? process.env.CLOUDFLARE_ACCOUNT_ID;
if (!/^[a-f0-9]{32}$/.test(accountId ?? '')) throw new Error('Pass the account ID shown by wrangler whoami.');
let credential = process.env.CLOUDFLARE_API_TOKEN;
if (!credential) {
  const configRoot = process.platform === 'win32'
    ? path.join(process.env.APPDATA, 'xdg.config')
    : (process.env.XDG_CONFIG_HOME ?? path.join(os.homedir(), '.config'));
  const config = await readFile(path.join(configRoot, '.wrangler', 'config', 'default.toml'), 'utf8');
  credential = /^oauth_token\s*=\s*"([^"]+)"/m.exec(config)?.[1];
}
if (!credential) throw new Error('No Wrangler credential. Run npx wrangler login.');

async function get(resource) {
  const response = await fetch(`https://api.cloudflare.com/client/v4/accounts/${accountId}/${resource}`, {
    headers: { Authorization: `Bearer ${credential}` }, signal: AbortSignal.timeout(15000),
  });
  const data = await response.json();
  if (!response.ok || !data.success) throw new Error(`Read-only ${resource} check failed: HTTP ${response.status}`);
  return data.result;
}

const subscriptions = await get('subscriptions');
const settings = await get('workers/account-settings');
const scripts = await get('workers/scripts');
const summary = subscriptions.map(item => ({
  product: item.rate_plan?.public_name ?? item.rate_plan?.id ?? 'unknown',
  rate_plan_id: item.rate_plan?.id, price: item.price ?? item.rate_plan?.price ?? null,
  state: item.state,
}));
const paidWorkers = summary.some(item => /worker/i.test(`${item.product} ${item.rate_plan_id}`)
  && (!/free/i.test(`${item.product} ${item.rate_plan_id}`) || Number(item.price) > 0));
const result = {
  recorded_at: new Date().toISOString(), account_id: accountId,
  subscriptions: summary, workers_settings: settings,
  paid_workers_subscription_found: paidWorkers,
  worker_name_already_exists: scripts.some(item => item.id === 'neon-workers-seminar'),
  checked_with: 'Read-only Cloudflare GET subscriptions, workers/account-settings, workers/scripts',
};
await mkdir('results/cloud', { recursive: true });
await writeFile('results/cloud/preflight.json', JSON.stringify(result, null, 2) + '\n');
console.log(JSON.stringify(result, null, 2));
if (paidWorkers) throw new Error('Workers paid subscription detected. Do not deploy under the Free-only requirement.');
