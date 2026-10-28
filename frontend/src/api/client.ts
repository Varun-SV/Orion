let session: Promise<string> | undefined;
export function resetSession() {
  session = undefined;
}
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
async function token() {
  if (!session)
    session = fetch('/api/v1/session', { credentials: 'same-origin', cache: 'no-store' })
      .then(async (r) => {
        if (!r.ok) throw new ApiError(r.status, 'Unable to establish local session.');
        return (await r.json()).csrf_token as string;
      })
      .catch((e) => {
        session = undefined;
        throw e;
      });
  return session;
}
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set('Content-Type', 'application/json');
  if (!['GET', 'HEAD'].includes(options.method ?? 'GET'))
    headers.set('X-Orion-CSRF', await token());
  let response: Response;
  try {
    response = await fetch('/api/v1' + path, {
      ...options,
      headers,
      credentials: 'same-origin',
      cache: 'no-store',
    });
  } catch {
    throw new Error('Unable to connect to Orion. Check that the local engine is running.');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    if (body.code === 'session_required') resetSession();
    throw new ApiError(
      response.status,
      body.message ??
        body.errors?.map((e: { message: string }) => e.message).join('; ') ??
        'Request failed.',
    );
  }
  return response.json() as Promise<T>;
}
export const json = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
});
