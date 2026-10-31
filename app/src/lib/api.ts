import Constants from 'expo-constants';

// The backend runs on the laptop. On the phone (Expo Go over the laptop hotspot) we reuse the
// host that served the JS bundle, so no IP needs to be typed. EXPO_PUBLIC_API_URL overrides it.
function resolveBase(): string {
  const env = process.env.EXPO_PUBLIC_API_URL;
  if (env) return env.replace(/\/$/, '');
  const hostUri = Constants.expoConfig?.hostUri ?? '';
  const host = hostUri.split(':')[0];
  return `http://${host || 'localhost'}:8787`;
}

export const API_BASE = resolveBase();

export class ApiError extends Error {
  status: number;
  body: any;
  constructor(status: number, body: any) {
    const msg = typeof body?.detail === 'string' ? body.detail : body?.detail?.message ?? `Request failed (${status})`;
    super(msg);
    this.status = status;
    this.body = body;
  }
}

async function handle<T>(r: Response): Promise<T> {
  const text = await r.text();
  let body: any = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = { detail: text };
  }
  if (!r.ok) throw new ApiError(r.status, body);
  return body as T;
}

export async function get<T = any>(path: string): Promise<T> {
  return handle<T>(await fetch(API_BASE + path));
}

export async function send<T = any>(path: string, body?: any, method = 'POST'): Promise<T> {
  return handle<T>(
    await fetch(API_BASE + path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  );
}

export type Picked = { uri: string; name: string; type: string };

// Uploads use React Native's own fetch (app/.env sets EXPO_PUBLIC_USE_RN_FETCH=1). Expo's fetch rejects
// { uri, name, type } form parts, and expo-file-system's uploader can't read files the pickers hand back in Expo Go.
export async function upload<T = any>(path: string, file: Picked, extra: Record<string, string> = {}): Promise<T> {
  const fd = new FormData();
  fd.append('file', { uri: file.uri, name: file.name, type: file.type } as any);
  Object.entries(extra).forEach(([k, v]) => fd.append(k, v));
  let r: Response;
  try {
    r = await fetch(API_BASE + path, { method: 'POST', body: fd });
  } catch (e: any) {
    throw new ApiError(0, { detail: `Can't reach the server at ${API_BASE}. ${e?.message ?? ''}`.trim() });
  }
  return handle<T>(r);
}

export const ttsUrl = (text: string, lang: string) =>
  `${API_BASE}/assistant/tts.wav?lang=${encodeURIComponent(lang)}&text=${encodeURIComponent(text.slice(0, 1500))}`;

/** Split text for speech into sentence chunks, so playback can start after the first one is ready. */
export function speechChunks(text: string, max = 260): string[] {
  const clean = text.replace(/[*#_`>]/g, '').replace(/\s*\n+\s*/g, '. ').trim();
  const sentences = clean.split(/(?<=[.!?।])\s+/).filter(Boolean);
  const out: string[] = [];
  let cur = '';
  for (const s of sentences) {
    if ((cur + ' ' + s).trim().length > max && cur) {
      out.push(cur.trim());
      cur = s;
    } else {
      cur = `${cur} ${s}`;
    }
  }
  if (cur.trim()) out.push(cur.trim());
  return out.flatMap((c) => (c.length > max * 2 ? c.match(new RegExp(`.{1,${max}}(\\s|$)`, 'g')) ?? [c] : [c]));
}

export const rupees = (n: number | null | undefined) =>
  n === null || n === undefined || isNaN(Number(n)) ? '–' : '₹' + Math.round(Number(n)).toLocaleString('en-IN');

export const fmtDate = (s?: string | null) => {
  if (!s) return '–';
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
};

export const fmtTime = (s?: string | null) => {
  if (!s) return '';
  const d = new Date(s);
  return d.toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });
};
