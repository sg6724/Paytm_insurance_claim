import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { get, send } from './api';
import { EN, type StringKey } from './strings';

export type Lang = { code: string; name: string; native: string; tts: boolean };

type AssistantContext = { screen: string; policy_id?: string; claim_id?: string };

type Ctx = {
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

  useEffect(() => {
    (async () => {
      try {
        await get('/health');
        setOnline(true);
        const [l, p] = await Promise.all([get<Lang[]>('/languages'), get<any>('/profile')]);
        setLangs(l);
        if (p?.language && p.language !== 'en-IN') {
          setLangState(p.language);
          loadStrings(p.language);
        }
      } catch {
        setOnline(false);
      }
    })();
  }, [loadStrings]);

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
    () => ({ lang, langs, setLang, t, translating, online, assistantCtx, setAssistantCtx, ttsSupported }),
    [lang, langs, setLang, t, translating, online, assistantCtx, setAssistantCtx, ttsSupported],
  );
  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>;
}

export function useApp() {
  const c = useContext(AppCtx);
  if (!c) throw new Error('useApp outside AppProvider');
  return c;
}
