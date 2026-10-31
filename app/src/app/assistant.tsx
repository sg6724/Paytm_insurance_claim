import Ionicons from '@expo/vector-icons/Ionicons';
import * as DocumentPicker from 'expo-document-picker';
import * as ImagePicker from 'expo-image-picker';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Image, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { fmtTime, get, send, upload } from '@/lib/api';
import { useApp } from '@/lib/app-context';
import { C } from '@/lib/theme';
import { AssistantAvatar } from '@/ui/assistant-avatar';
import { act, Btn, Card, Row, Sheet } from '@/ui/kit';
import { ListenButton, MicButton, useSpeaker } from '@/ui/voice';

type Msg = { role: 'user' | 'assistant'; content: string; image?: string | boolean; file?: string };
type Attachment = { id: number; kind: 'image' | 'pdf'; name: string; uri: string; status: 'reading' | 'ready' | 'error'; text?: string; error?: string };
type AskOpts = { attachment?: string; image?: string; file?: string; spoken?: boolean };
type Recap = { recap: string | null; next_step: string | null; last_at: string };

const SUGGEST: Record<string, string[]> = {
  claim_form: ['Which documents prove my admission date?', 'Why is my room rent a problem?'],
  decision_explainer: ['Is the deduction on medicines fair?', 'What should I write in the appeal?'],
  claim_tracker: ['When will I get my money?', 'What does this insurer query mean?'],
  hospital_check: ['What is proportionate deduction?', 'What papers do I need at discharge?'],
  policy_explainer: ['Is cataract covered?', 'What is my room rent limit?'],
};

export default function Assistant() {
  const insets = useSafeAreaInsets();
  const { human } = useLocalSearchParams<{ human?: string }>();
  const { lang, langs, t, assistantCtx } = useApp();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [ticket, setTicket] = useState<any>(null);
  const [recap, setRecap] = useState<Recap | null>(null);
  const scroll = useRef<any>(null);
  const speaker = useSpeaker();
  const [pickOpen, setPickOpen] = useState(false);
  const [att, setAtt] = useState<Attachment | null>(null);
  const langName = langs.find((l) => l.code === lang)?.native ?? 'English';

  const scope = [assistantCtx.claim_id && `claim_id=${assistantCtx.claim_id}`, assistantCtx.policy_id && `policy_id=${assistantCtx.policy_id}`].filter(Boolean).join('&');

  // Coming back: pick up the saved conversation for this claim or policy.
  useEffect(() => {
    let live = true;
    get<any>(`/assistant/thread?lang=${lang}&${scope}`)
      .then((t) => {
        if (!live || !t.messages.length) return;
        setMsgs(t.messages);
        setRecap({ recap: t.recap, next_step: t.next_step, last_at: t.last_at });
        if (!t.recap_pending) return;
        // The chat shows at once; the AI-written recap fills in when ready (unless the user has moved on).
        get<any>(`/assistant/thread/recap?lang=${lang}&${scope}`)
          .then((r) => live && setRecap((cur) => (cur ? { ...cur, recap: r.recap } : cur)))
          .catch(() => {});
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [scope, lang]);

  async function startFresh() {
    await send(`/assistant/thread?${scope}`, undefined, 'DELETE').catch(() => {});
    setMsgs([]);
    setRecap(null);
  }

  useEffect(() => {
    if (human) handoff();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [human]);

  async function ask(text: string, { attachment: attachmentText, image, file, spoken = false }: AskOpts = {}) {
    if (!text.trim() && !attachmentText) return;
    const shown: Msg = { role: 'user', content: text || (file ? 'Please explain this document.' : 'Please look at this.'), image, file };
    setRecap(null);
    setMsgs((m) => [...m, shown]);
    setInput('');
    setBusy(true);
    try {
      const out = await send('/assistant/chat', { message: shown.content, attachment: attachmentText, attachment_name: file, lang, ...assistantCtx });
      setMsgs((m) => [...m, { role: 'assistant', content: out.reply }]);
      if (spoken && out.reply) speaker.speak(out.reply); // they talked, so answer out loud
    } catch (e: any) {
      setMsgs((m) => [...m, { role: 'assistant', content: `Sorry, I couldn't answer that right now (${e.message}). You can talk to a human.` }]);
    } finally {
      setBusy(false);
      setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 100);
    }
  }

  async function share(kind: 'image' | 'pdf') {
    setPickOpen(false);
    // Android drops the picker's result if it opens while the sheet is still animating closed.
    await new Promise((r) => setTimeout(r, 450));
    let picked: { uri: string; name: string; type: string } | null = null;
    if (kind === 'image') {
      const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted) return;
      const r = await ImagePicker.launchImageLibraryAsync({ quality: 0.7 });
      if (r.canceled) return;
      picked = { uri: r.assets[0].uri, name: 'screenshot.jpg', type: r.assets[0].mimeType ?? 'image/jpeg' };
    } else {
      const r = await DocumentPicker.getDocumentAsync({ type: 'application/pdf', copyToCacheDirectory: true });
      if (r.canceled) return;
      picked = { uri: r.assets[0].uri, name: r.assets[0].name, type: 'application/pdf' };
    }
    console.log('[assistant] picked', kind, picked.name);
    // Like ChatGPT or Claude: the file waits above the input as a chip while it is read, and goes out
    // with the user's own question when they tap send.
    const id = Date.now();
    setAtt({ id, kind, name: picked.name, uri: picked.uri, status: 'reading' });
    try {
      const out = await upload('/assistant/attach', picked);
      setAtt((a) => (a && a.id === id ? { ...a, status: 'ready', text: out.text } : a));
    } catch (e: any) {
      setAtt((a) => (a && a.id === id ? { ...a, status: 'error', error: e.message } : a));
    }
  }

  function sendNow() {
    if (att?.status === 'reading') return;
    if (att?.status === 'ready') {
      const fallback = att.kind === 'pdf' ? 'Please explain this document.' : 'Please explain this.';
      ask(input.trim() || fallback, att.kind === 'pdf' ? { attachment: att.text, file: att.name } : { attachment: att.text, image: att.uri });
      setAtt(null);
      return;
    }
    ask(input);
  }

  const handoff = act(async () => {
    setTicket(await send('/support/ticket', { topic: assistantCtx.screen, messages: msgs, claim_id: assistantCtx.claim_id }));
  });

  const suggestions = SUGGEST[assistantCtx.screen] ?? ['How do I claim?', 'What is co-pay?', 'My claim was rejected. What now?'];

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: '#fff' }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
      <View style={{ paddingTop: insets.top + 8, paddingHorizontal: 16, paddingBottom: 10, flexDirection: 'row', alignItems: 'center', gap: 10, borderBottomWidth: 1, borderBottomColor: C.line }}>
        <AssistantAvatar size={44} />
        <View style={{ flex: 1 }}>
          <Text style={{ fontWeight: '800', fontSize: 16 }}>Claimezy assistant</Text>
          <Text style={{ color: C.sub, fontSize: 12 }}>Answers in {langName} · knows your {assistantCtx.claim_id ? 'claim' : 'policy'}</Text>
        </View>
        {msgs.length ? (
          <Pressable onPress={startFresh} hitSlop={10} accessibilityLabel="Clear this chat">
            <Ionicons name="trash-outline" size={21} color={C.sub} />
          </Pressable>
        ) : null}
        <Pressable onPress={() => router.back()} hitSlop={10}>
          <Ionicons name="close" size={26} color={C.text} />
        </Pressable>
      </View>
      <ScrollView ref={scroll} contentContainerStyle={{ padding: 16, gap: 12 }} keyboardShouldPersistTaps="handled">
        {msgs.length === 0 ? <View style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-end', maxWidth: '94%' }}>
          <AssistantAvatar size={32} />
          <View style={{ flexShrink: 1, backgroundColor: C.paleBlue, borderRadius: 16, borderBottomLeftRadius: 4, padding: 12 }}>
            <Text style={{ color: C.text }}>Hi! Ask me anything about your policy or claim. You can speak, type, or share a screenshot of an insurer message or letter.</Text>
          </View>
        </View> : null}
        {msgs.length === 0 ? (
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            {suggestions.map((s) => (
              <Pressable key={s} onPress={() => ask(s)} style={{ borderWidth: 1, borderColor: C.line, borderRadius: 99, paddingHorizontal: 12, paddingVertical: 8 }}>
                <Text style={{ color: C.navy, fontWeight: '600', fontSize: 13 }}>{s}</Text>
              </Pressable>
            ))}
          </View>
        ) : null}
        {msgs.map((m, i) => (
          <View key={i} style={{ alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '88%', backgroundColor: m.role === 'user' ? C.navy : C.paleBlue, borderRadius: 16, padding: 12, gap: 8 }}>
            {typeof m.image === 'string' ? <Image source={{ uri: m.image }} style={{ width: 160, height: 160, borderRadius: 10 }} /> : null}
            {m.file ? (
              <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center', backgroundColor: 'rgba(255,255,255,0.14)', borderRadius: 10, padding: 8 }}>
                <View style={{ width: 30, height: 30, borderRadius: 6, backgroundColor: C.red, alignItems: 'center', justifyContent: 'center' }}>
                  <Text style={{ color: '#fff', fontWeight: '800', fontSize: 9 }}>PDF</Text>
                </View>
                <Text style={{ color: '#fff', fontSize: 13, fontWeight: '600', flexShrink: 1 }} numberOfLines={1}>{m.file}</Text>
              </View>
            ) : null}
            {m.image === true ? (
              <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center' }}>
                <Ionicons name="image-outline" size={16} color="#fff" />
                <Text style={{ color: '#fff', fontSize: 12 }}>Screenshot shared</Text>
              </View>
            ) : null}
            <Text style={{ color: m.role === 'user' ? '#fff' : C.text, lineHeight: 20 }}>{m.content.replace(/\*\*/g, '')}</Text>
            {m.role === 'assistant' ? <ListenButton text={m.content} /> : null}
          </View>
        ))}
        {recap ? (
          <Card style={{ gap: 8, backgroundColor: C.paleBlue, borderColor: '#CFE6F7' }}>
            <Text style={{ fontWeight: '800', color: C.navy }}>{t('whereWeLeftOff')}</Text>
            <Text style={{ color: C.faint, fontSize: 11 }}>{fmtTime(recap.last_at)}</Text>
            {recap.recap ? (
              <Text style={{ color: C.text, lineHeight: 20 }}>{recap.recap.replace(/\*\*/g, '')}</Text>
            ) : (
              <Text style={{ color: C.sub, fontStyle: 'italic' }}>{t('catchingUp')}</Text>
            )}
            {recap.next_step ? <Text style={{ color: C.text, fontWeight: '700' }}>{t('nextLabel')}: {recap.next_step}</Text> : null}
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <Btn title={t('continueChat')} style={{ flex: 1, height: 40 }} onPress={() => ask('Let us continue from where we left off.')} />
              <Btn title={t('startFresh')} kind="secondary" style={{ flex: 1, height: 40 }} onPress={startFresh} />
            </View>
          </Card>
        ) : null}
        {busy ? <ActivityIndicator color={C.navy} style={{ alignSelf: 'flex-start' }} /> : null}
        {ticket ? (
          <Card style={{ gap: 6, backgroundColor: C.greenSoft, borderColor: '#BFE7D6' }}>
            <Text style={{ fontWeight: '700', color: C.green }}>Request sent · {ticket.id}</Text>
            <Text style={{ color: C.text }}>{ticket.eta} {"Your conversation is attached so you don't have to repeat yourself."}</Text>
          </Card>
        ) : null}
      </ScrollView>
      <View style={{ padding: 12, paddingBottom: insets.bottom + 10, borderTopWidth: 1, borderTopColor: C.line, gap: 8 }}>
        {att ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, alignSelf: 'flex-start', maxWidth: '100%', backgroundColor: C.paleBlue, borderRadius: 14, padding: 8, paddingRight: 10, borderWidth: 1, borderColor: att.status === 'error' ? C.red : C.line }}>
            {att.kind === 'image' ? (
              <Image source={{ uri: att.uri }} style={{ width: 40, height: 40, borderRadius: 8 }} />
            ) : (
              <View style={{ width: 40, height: 40, borderRadius: 8, backgroundColor: C.red, alignItems: 'center', justifyContent: 'center' }}>
                <Text style={{ color: '#fff', fontWeight: '800', fontSize: 11 }}>PDF</Text>
              </View>
            )}
            <View style={{ flexShrink: 1 }}>
              <Text numberOfLines={1} style={{ fontWeight: '700', color: C.text, fontSize: 13 }}>{att.kind === 'pdf' ? att.name : 'Screenshot'}</Text>
              <Text style={{ fontSize: 12, color: att.status === 'error' ? C.red : C.sub }} numberOfLines={2}>
                {att.status === 'reading' ? 'Reading…' : att.status === 'ready' ? 'Ready. Ask your question and send.' : `Couldn't read it: ${att.error}`}
              </Text>
            </View>
            {att.status === 'reading' ? <ActivityIndicator size="small" color={C.navy} /> : null}
            <Pressable onPress={() => setAtt(null)} hitSlop={10} accessibilityLabel="Remove attachment">
              <Ionicons name="close-circle" size={22} color={C.sub} />
            </Pressable>
          </View>
        ) : null}
        <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
          <Pressable onPress={() => setPickOpen(true)} disabled={att?.status === 'reading'} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: C.skySoft, alignItems: 'center', justifyContent: 'center' }} accessibilityLabel="Share a screenshot or PDF">
            <Ionicons name="attach" size={22} color={C.navy} />
          </Pressable>
          <TextInput value={input} onChangeText={setInput} placeholder={att ? 'Ask about this file…' : t('askPlaceholder')} placeholderTextColor={C.faint} onSubmitEditing={sendNow} returnKeyType="send"
            style={{ flex: 1, borderWidth: 1.5, borderColor: C.line, borderRadius: 24, paddingHorizontal: 14, paddingVertical: 10, fontSize: 14, color: C.text }} />
          <MicButton onText={(tx) => ask(tx, { spoken: true })} size={44} />
          <Pressable onPress={sendNow} disabled={att?.status === 'reading'} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: C.navy, opacity: att?.status === 'reading' ? 0.4 : 1, alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="send" size={18} color="#fff" />
          </Pressable>
        </View>
        {!ticket ? <Btn title={t('talkToHuman')} kind="ghost" icon="headset-outline" style={{ height: 40 }} onPress={handoff} /> : null}
      </View>
      <Sheet visible={pickOpen} onClose={() => setPickOpen(false)} title="Share with the assistant">
        <Row icon="image-outline" title="Photo or screenshot" sub="An insurer SMS, WhatsApp message, letter or bill" onPress={() => share('image')} />
        <Row icon="document-text-outline" title="PDF document" sub="A policy, settlement letter, bill or discharge summary" onPress={() => share('pdf')} />
      </Sheet>
    </KeyboardAvoidingView>
  );
}
