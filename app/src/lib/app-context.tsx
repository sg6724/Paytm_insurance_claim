import * as SecureStore from 'expo-secure-store';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { get, send, setAuthToken, setSessionEndedHandler } from './api';
import { EN, type StringKey } from './strings';

export type Lang = { code: string; name: string; native: string; tts: boolean };

type AssistantContext = { screen: string; policy_id?: string; claim_id?: string };

export type User = { email: string; name: string };
const SESSION_KEY = 'claimezy_session';

type Ctx = {
  user: User | null;
  authReady: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (name: string, email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  lang: string;
  langs: Lang[];
  setLang: (code: string) => Promise<void>;
  t: (k: StringKey) => string;
  translating: boolean;
  online: boolean | null;
  assistantCtx: AssistantContext;
  setAssistantCtx: (c: AssistantContext) => void;
  ttsSupported: boolean;
};

const AppCtx = createContext<Ctx | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState('en-IN');
  const [langs, setLangs] = useState<Lang[]>([]);
  const [strings, setStrings] = useState<Record<string, string>>(EN);
  const [translating, setTranslating] = useState(false);
  const [online, setOnline] = useState<boolean | null>(null);
  const [assistantCtx, setAssistantCtxState] = useState<AssistantContext>({ screen: 'home' });
  const [user, setUser] = useState<User | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const cache = useRef<Record<string, Record<string, string>>>({ 'en-IN': EN });

  const loadStrings = useCallback(async (code: string) => {
    if (cache.current[code]) {
      setStrings(cache.current[code]);
      return;
    }
    setTranslating(true);
    try {
      const out = await send<Record<string, string>>('/i18n', { lang: code, strings: EN });
      cache.current[code] = out;
      setStrings(out);
    } catch {
      setStrings(EN);
    } finally {
      setTranslating(false);
    }
  }, []);

  const endSession = useCallback(async () => {
    setAuthToken(null);
    setUser(null);
    setLangState('en-IN');
    setStrings(EN);
    await SecureStore.deleteItemAsync(SESSION_KEY).catch(() => {});
  }, []);

  const startSession = useCallback(async (out: { token: string; user: User }) => {
    setAuthToken(out.token);
    await SecureStore.setItemAsync(SESSION_KEY, JSON.stringify(out));
    setUser(out.user);
  }, []);

  useEffect(() => {
    setSessionEndedHandler(endSession);
    (async () => {
      try {
        await get('/health');
        setOnline(true);
        setLangs(await get<Lang[]>('/languages'));
      } catch {
        setOnline(false);
      }
      // A saved session opens the app straight away; the server has the final say on the first request.
      const saved = await SecureStore.getItemAsync(SESSION_KEY).catch(() => null);
      if (saved) {
        const session = JSON.parse(saved);
        setAuthToken(session.token);
        setUser(session.user);
      }
      setAuthReady(true);
    })();
  }, [endSession]);

  // Each account has its own saved language.
  useEffect(() => {
    if (!user) return;
    get<any>('/profile')
      .then((p) => {
        if (p?.language && p.language !== 'en-IN') {
          setLangState(p.language);
          loadStrings(p.language);
        }
      })
      .catch(() => {});
  }, [user, loadStrings]);

  const signIn = useCallback(
    async (email: string, password: string) => startSession(await send('/auth/login', { email, password })),
    [startSession],
  );
  const signUp = useCallback(
    async (name: string, email: string, password: string) => startSession(await send('/auth/signup', { name, email, password })),
    [startSession],
  );
  const signOut = useCallback(async () => {
    await send('/auth/logout').catch(() => {});
    await endSession();
  }, [endSession]);

  const setLang = useCallback(
    async (code: string) => {
      setLangState(code);
      send('/profile', { language: code }, 'PATCH').catch(() => {});
      await loadStrings(code);
    },
    [loadStrings],
  );

  const t = useCallback((k: StringKey) => strings[k] ?? EN[k], [strings]);
  const setAssistantCtx = useCallback((c: AssistantContext) => setAssistantCtxState(c), []);
  const ttsSupported = langs.find((l) => l.code === lang)?.tts ?? true;

  const value = useMemo(
    () => ({ user, authReady, signIn, signUp, signOut, lang, langs, setLang, t, translating, online, assistantCtx, setAssistantCtx, ttsSupported }),
    [user, authReady, signIn, signUp, signOut, lang, langs, setLang, t, translating, online, assistantCtx, setAssistantCtx, ttsSupported],
  );
  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>;
}

export function useApp() {
  const c = useContext(AppCtx);
  if (!c) throw new Error('useApp outside AppProvider');
  return c;
}
