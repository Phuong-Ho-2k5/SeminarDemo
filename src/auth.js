export async function authorize(request, env) {
  if (!env.DEMO_TOKEN) return 503;
  const authorization = request.headers.get('Authorization') ?? '';
  if (!authorization.startsWith('Bearer ')) return 401;
  // Compare fixed-length digests; do not return early based on token characters.
  const encoder = new TextEncoder();
  const [actual, expected] = await Promise.all([
    crypto.subtle.digest('SHA-256', encoder.encode(authorization.slice(7))),
    crypto.subtle.digest('SHA-256', encoder.encode(env.DEMO_TOKEN)),
  ]);
  const left = new Uint8Array(actual);
  const right = new Uint8Array(expected);
  let difference = 0;
  for (let index = 0; index < left.length; index++) difference |= left[index] ^ right[index];
  return difference === 0 ? 200 : 401;
}
