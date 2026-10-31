import Ionicons from '@expo/vector-icons/Ionicons';
import * as ImagePicker from 'expo-image-picker';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { send, upload } from '@/lib/api';
import { useApp } from '@/lib/app-context';
import { C } from '@/lib/theme';
import { AssistantAvatar } from '@/ui/assistant-avatar';
import { Btn, Card } from '@/ui/kit';
import { ListenButton, MicButton } from '@/ui/voice';

type Msg = { role: 'user' | 'assistant'; content: string; image?: string };

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
  const scroll = useRef<any>(null);
  const langName = langs.find((l) => l.code === lang)?.native ?? 'English';

  useEffect(() => {
    if (human) handoff();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [human]);

  async function ask(text: string, attachmentText?: string, image?: string) {
    if (!text.trim() && !attachmentText) return;
    const shown: Msg = { role: 'user', content: text || 'Please look at this.', image };
    const content = attachmentText ? `${text || 'Explain this to me.'}\n\nATTACHMENT (text read from the screenshot/document):\n${attachmentText}` : text;
    const history = [...msgs.map((m) => ({ role: m.role, content: m.content })), { role: 'user', content }];
    setMsgs((m) => [...m, shown]);
    setInput('');
    setBusy(true);
    try {
      const out = await send('/assistant/chat', { messages: history, lang, ...assistantCtx });
      setMsgs((m) => [...m, { role: 'assistant', content: out.reply }]);
    } catch (e: any) {
      setMsgs((m) => [...m, { role: 'assistant', content: `Sorry, I couldn't answer that right now (${e.message}). You can talk to a human.` }]);
    } finally {
      setBusy(false);
      setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 100);
    }
  }

  async function attach() {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) return;
    const r = await ImagePicker.launchImageLibraryAsync({ quality: 0.7 });
    if (r.canceled) return;
    const a = r.assets[0];
    setBusy(true);
    try {
      const out = await upload('/assistant/attach', { uri: a.uri, name: 'screenshot.jpg', type: a.mimeType ?? 'image/jpeg' });
      setBusy(false);
      await ask(input, out.text, a.uri);
    } catch (e: any) {
      setBusy(false);
      setMsgs((m) => [...m, { role: 'assistant', content: `I couldn't read that image (${e.message}).` }]);
    }
  }

  async function handoff() {
    setTicket(await send('/support/ticket', { topic: assistantCtx.screen, messages: msgs, claim_id: assistantCtx.claim_id }));
  }

  const suggestions = SUGGEST[assistantCtx.screen] ?? ['How do I claim?', 'What is co-pay?', 'My claim was rejected. What now?'];

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: '#fff' }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
      <View style={{ paddingTop: insets.top + 8, paddingHorizontal: 16, paddingBottom: 10, flexDirection: 'row', alignItems: 'center', gap: 10, borderBottomWidth: 1, borderBottomColor: C.line }}>
        <AssistantAvatar size={44} />
        <View style={{ flex: 1 }}>
          <Text style={{ fontWeight: '800', fontSize: 16 }}>Claim-to-Cash assistant</Text>
          <Text style={{ color: C.sub, fontSize: 12 }}>Answers in {langName} · knows your {assistantCtx.claim_id ? 'claim' : 'policy'}</Text>
        </View>
        <Pressable onPress={() => router.back()} hitSlop={10}>
          <Ionicons name="close" size={26} color={C.text} />
        </Pressable>
      </View>
      <ScrollView ref={scroll} contentContainerStyle={{ padding: 16, gap: 12 }} keyboardShouldPersistTaps="handled">
        <View style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-end', maxWidth: '94%' }}>
          <AssistantAvatar size={32} />
          <View style={{ flexShrink: 1, backgroundColor: C.paleBlue, borderRadius: 16, borderBottomLeftRadius: 4, padding: 12 }}>
            <Text style={{ color: C.text }}>Hi! Ask me anything about your policy or claim. You can speak, type, or share a screenshot of an insurer message or letter.</Text>
          </View>
        </View>
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
            {m.image ? (
              <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center' }}>
                <Ionicons name="image-outline" size={16} color="#fff" />
                <Text style={{ color: '#fff', fontSize: 12 }}>Screenshot shared</Text>
              </View>
            ) : null}
            <Text style={{ color: m.role === 'user' ? '#fff' : C.text, lineHeight: 20 }}>{m.content.replace(/\*\*/g, '')}</Text>
            {m.role === 'assistant' ? <ListenButton text={m.content} /> : null}
          </View>
        ))}
        {busy ? <ActivityIndicator color={C.navy} style={{ alignSelf: 'flex-start' }} /> : null}
        {ticket ? (
          <Card style={{ gap: 6, backgroundColor: C.greenSoft, borderColor: '#BFE7D6' }}>
            <Text style={{ fontWeight: '700', color: C.green }}>Request sent · {ticket.id}</Text>
            <Text style={{ color: C.text }}>{ticket.eta} {"Your conversation is attached so you don't have to repeat yourself."}</Text>
          </Card>
        ) : null}
      </ScrollView>
      <View style={{ padding: 12, paddingBottom: insets.bottom + 10, borderTopWidth: 1, borderTopColor: C.line, gap: 8 }}>
        <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
          <Pressable onPress={attach} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: C.skySoft, alignItems: 'center', justifyContent: 'center' }} accessibilityLabel="Share a screenshot">
            <Ionicons name="image-outline" size={20} color={C.navy} />
          </Pressable>
          <TextInput value={input} onChangeText={setInput} placeholder={t('askPlaceholder')} placeholderTextColor={C.faint} onSubmitEditing={() => ask(input)} returnKeyType="send"
            style={{ flex: 1, borderWidth: 1.5, borderColor: C.line, borderRadius: 24, paddingHorizontal: 14, paddingVertical: 10, fontSize: 14, color: C.text }} />
          <MicButton onText={(tx) => ask(tx)} size={44} />
          <Pressable onPress={() => ask(input)} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: C.navy, alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="send" size={18} color="#fff" />
          </Pressable>
        </View>
        {!ticket ? <Btn title={t('talkToHuman')} kind="ghost" icon="headset-outline" style={{ height: 40 }} onPress={handoff} /> : null}
      </View>
    </KeyboardAvoidingView>
  );
}
