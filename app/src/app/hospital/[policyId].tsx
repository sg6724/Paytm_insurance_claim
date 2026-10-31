import Ionicons from '@expo/vector-icons/Ionicons';
import * as DocumentPicker from 'expo-document-picker';
import * as ImagePicker from 'expo-image-picker';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View } from 'react-native';

import { get, rupees, send, upload } from '@/lib/api';
import { useApp } from '@/lib/app-context';
import { C } from '@/lib/theme';
import { Btn, Card, ErrorNote, Field, Header, Loading, Money, Pill, Section, useAsync } from '@/ui/kit';
import { Tip } from '@/ui/tip';
import { ListenButton, MicButton, VoiceHint, useSpeaker } from '@/ui/voice';

type Msg = { role: 'user' | 'assistant'; content: string };
const ROOMS = [['general_ward', 'General ward'], ['twin_sharing', 'Twin sharing'], ['single_private', 'Single private'], ['deluxe', 'Deluxe'], ['icu', 'ICU']];
const SEV: Record<string, { icon: any; color: string; bg: string }> = {
  high: { icon: 'alert-circle', color: C.red, bg: C.redSoft },
  medium: { icon: 'warning', color: C.amber, bg: C.amberSoft },
  ok: { icon: 'checkmark-circle', color: C.green, bg: C.greenSoft },
};

export default function HospitalCheck() {
  const { policyId } = useLocalSearchParams<{ policyId: string }>();
  const { lang, t, setAssistantCtx } = useApp();
  const policy = useAsync(() => get(`/policies/${policyId}`), [policyId]);
  const [tab, setTab] = useState<'chat' | 'form' | 'bill'>('chat');
  const [claimType, setClaimType] = useState<'cashless' | 'reimbursement'>('cashless');
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [facts, setFacts] = useState<Record<string, any>>({});
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const scroll = useRef<any>(null);
  const speaker = useSpeaker();

  useFocusEffect(useCallback(() => setAssistantCtx({ screen: 'hospital_check', policy_id: policyId }), [policyId, setAssistantCtx]));

  // Pick up where this stay left off.
  useEffect(() => {
    let live = true;
    get<any>(`/hospital/stay?policy_id=${encodeURIComponent(policyId)}`)
      .then((stay) => {
        if (!live) return;
        setMsgs(stay.messages ?? []);
        setFacts(stay.facts ?? {});
        setResult(stay.result);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [policyId]);

  async function startOver() {
    await send(`/hospital/stay?policy_id=${encodeURIComponent(policyId)}`, undefined, 'DELETE').catch(() => {});
    setMsgs([]);
    setFacts({});
    setResult(null);
  }

  const p = policy.data;
  const greeting = p
    ? `I'm here to help while you're in hospital. Who is admitted, what room are you in and how much is it per day? What is the treatment? You can type or tap the mic and speak in your language. No bill needed.`
    : '';

  async function sendChat(text: string, spoken = false) {
    if (!text.trim()) return;
    const next: Msg[] = [...msgs, { role: 'user', content: text }];
    setMsgs(next);
    setInput('');
    setBusy('Thinking…');
    setError(null);
    try {
      const out = await send('/hospital/chat', { policy_id: policyId, messages: next, facts: { ...facts, claim_type: claimType }, lang });
      setMsgs([...next, { role: 'assistant', content: out.reply }]);
      if (spoken && out.reply) speaker.speak(out.reply); // they talked, so answer out loud
      setFacts(out.facts);
      if (out.ready && out.check) setResult({ ...out.check, summary: null });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(null);
      setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 100);
    }
  }

  async function runCheck(f = facts) {
    setBusy('Checking your stay against the policy…');
    setError(null);
    try {
      setResult(await send('/hospital/check', { policy_id: policyId, facts: { ...f, claim_type: claimType }, lang }));
      setTimeout(() => scroll.current?.scrollToEnd({ animated: true }), 150);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  }

  // Camera, gallery or a file (PDF or image). Every step is guarded: a picker or permission failure shows a message.
  async function addBill(source: 'camera' | 'gallery' | 'file') {
    setError(null);
    let file: { uri: string; name: string; type: string } | null = null;
    try {
      if (source === 'file') {
        const r = await DocumentPicker.getDocumentAsync({ type: ['application/pdf', 'image/*'], copyToCacheDirectory: true });
        if (r.canceled) return;
        const a = r.assets[0];
        file = { uri: a.uri, name: a.name, type: a.mimeType ?? (a.name.toLowerCase().endsWith('.pdf') ? 'application/pdf' : 'image/jpeg') };
      } else {
        const perm = source === 'camera' ? await ImagePicker.requestCameraPermissionsAsync() : await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (!perm.granted) return setError(`Allow ${source === 'camera' ? 'camera' : 'photo'} access to read the bill.`);
        const r = source === 'camera' ? await ImagePicker.launchCameraAsync({ quality: 0.6 }) : await ImagePicker.launchImageLibraryAsync({ quality: 0.6 });
        if (r.canceled) return;
        file = { uri: r.assets[0].uri, name: 'bill.jpg', type: r.assets[0].mimeType ?? 'image/jpeg' };
      }
    } catch (e: any) {
      return setError(`Couldn't open the ${source === 'file' ? 'file picker' : source}: ${e?.message ?? 'unknown error'}`);
    }
    console.log('[hospital] bill picked', source, file.name, file.type);
    setBusy(file.type === 'application/pdf' ? 'Reading the bill PDF…' : 'Reading the bill photo…');
    try {
      const out = await upload('/hospital/bill', file, { policy_id: String(policyId) });
      const merged = { ...facts, ...out.facts };
      setFacts(merged);
      if (!Object.keys(out.facts ?? {}).length) {
        setBusy(null);
        return setError("We couldn't find room or treatment details on this bill. Tell us in the chat or the quick form instead.");
      }
      await runCheck(merged);
    } catch (e: any) {
      setError(e.message);
      setBusy(null);
    }
  }

  const setF = (k: string, v: any) => setFacts({ ...facts, [k]: v });

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: C.bg }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Header title={t('imInHospital')} sub="" />
      <ScrollView ref={scroll} contentContainerStyle={{ padding: 16, gap: 14, paddingBottom: 140 }} keyboardShouldPersistTaps="handled">
        <Tip id="hospital" text="You do not need a bill. Just tell us the room and the treatment, by voice or by typing. We show what the insurer is likely to cut while you can still change it." />
        {!p ? <Loading /> : null}
        <View style={{ flexDirection: 'row', backgroundColor: '#fff', borderRadius: 12, padding: 4, borderWidth: 1, borderColor: C.line }}>
          {(['cashless', 'reimbursement'] as const).map((k) => (
            <Pressable key={k} onPress={() => setClaimType(k)} style={{ flex: 1, paddingVertical: 10, borderRadius: 9, backgroundColor: claimType === k ? C.navy : 'transparent' }}>
              <Text style={{ textAlign: 'center', fontWeight: '700', color: claimType === k ? '#fff' : C.text }}>{t(k)}</Text>
            </Pressable>
          ))}
        </View>
        <Text style={{ color: C.sub, fontSize: 13 }}>
          {claimType === 'cashless' ? 'Network hospital: the insurer pays the hospital directly. You pay only what is not covered.' : 'Non-network hospital or no cashless: you pay now and claim back after discharge.'}
        </Text>

        <Section title={t('tellUs')}>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            {([['chat', t('chatVoice'), 'chatbubbles-outline'], ['form', t('quickForm'), 'list-outline'], ['bill', t('billPhoto'), 'camera-outline']] as const).map(([k, label, icon]) => (
              <Pressable key={k} onPress={() => setTab(k)} style={{ flex: 1, alignItems: 'center', gap: 4, paddingVertical: 10, borderRadius: 12, borderWidth: 1.5, borderColor: tab === k ? C.navy : C.line, backgroundColor: tab === k ? C.skySoft : '#fff' }}>
                <Ionicons name={icon} size={20} color={C.navy} />
                <Text style={{ fontSize: 12, fontWeight: '600', color: C.text }}>{label}</Text>
              </Pressable>
            ))}
          </View>
        </Section>

        {tab === 'chat' && p ? (
          <Card style={{ gap: 10 }}>
            <Bubble role="assistant" text={greeting} />
            {msgs.map((m, i) => (
              <Bubble key={i} role={m.role} text={m.content} />
            ))}
            {Object.keys(facts).filter((k) => facts[k] !== undefined && k !== 'claim_type').length ? (
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
                {Object.entries(facts).filter(([k, v]) => v !== null && v !== '' && k !== 'claim_type').map(([k, v]) => (
                  <Pill key={k} text={`${k.replace(/_/g, ' ')}: ${k === 'member_id' ? p.members.find((m: any) => m.id === v)?.name ?? v : String(v)}`} tone="muted" />
                ))}
              </View>
            ) : null}
            <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
              <TextInput value={input} onChangeText={setInput} placeholder="e.g. My mother, single room ₹7,500 a day, gallbladder surgery" placeholderTextColor={C.faint}
                style={{ flex: 1, borderWidth: 1.5, borderColor: C.line, borderRadius: 24, paddingHorizontal: 14, paddingVertical: 10, fontSize: 14, color: C.text }} onSubmitEditing={() => sendChat(input)} returnKeyType="send" />
              <MicButton onText={(tx) => sendChat(tx, true)} size={44} />
              <Pressable onPress={() => sendChat(input)} style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: C.navy, alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name="send" size={18} color="#fff" />
              </Pressable>
            </View>
            <VoiceHint />
          </Card>
        ) : null}

        {tab === 'form' && p ? (
          <Card style={{ gap: 12 }}>
            <Text style={{ fontSize: 13, color: C.sub, fontWeight: '600' }}>Who is admitted?</Text>
            <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
              {p.members.map((m: any) => (
                <Chip key={m.id} on={facts.member_id === m.id} label={m.name} onPress={() => setF('member_id', m.id)} />
              ))}
            </View>
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <Chip on={facts.admission_type !== 'planned'} label="Emergency" onPress={() => setF('admission_type', 'emergency')} />
              <Chip on={facts.admission_type === 'planned'} label="Planned" onPress={() => setF('admission_type', 'planned')} />
              <Chip on={!!facts.is_accident} label="Accident" onPress={() => setF('is_accident', !facts.is_accident)} />
            </View>
            <Text style={{ fontSize: 13, color: C.sub, fontWeight: '600' }}>Room</Text>
            <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
              {ROOMS.map(([v, l]) => (
                <Chip key={v} on={facts.room_category === v} label={l} onPress={() => setF('room_category', v)} />
              ))}
            </View>
            <Field label="Room rent per day (₹)" value={facts.room_rent_per_day?.toString() ?? ''} onChangeText={(v) => setF('room_rent_per_day', v)} keyboardType="numeric" />
            <Field label="Expected days" value={facts.expected_days?.toString() ?? ''} onChangeText={(v) => setF('expected_days', v)} keyboardType="numeric" />
            <Field label="Illness or treatment" value={facts.procedure ?? ''} onChangeText={(v) => setF('procedure', v)} placeholder="e.g. knee replacement, dengue" />
            <Field label="Admission date" value={facts.admission_date ?? ''} onChangeText={(v) => setF('admission_date', v)} placeholder="YYYY-MM-DD" />
            <Field label="Estimated bill (optional, ₹)" value={facts.estimated_bill?.toString() ?? ''} onChangeText={(v) => setF('estimated_bill', v)} keyboardType="numeric" />
            <Btn title={t('checkStay')} onPress={() => runCheck()} disabled={!facts.member_id} />
          </Card>
        ) : null}

        {tab === 'bill' ? (
          <Card style={{ gap: 10 }}>
            <Text style={{ color: C.sub }}>If the hospital gave you an estimate or interim bill, we can read it: a photo or a PDF. This is optional.</Text>
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <Btn title="Camera" icon="camera-outline" kind="secondary" style={{ flex: 1 }} onPress={() => addBill('camera')} />
              <Btn title="Gallery" icon="images-outline" kind="secondary" style={{ flex: 1 }} onPress={() => addBill('gallery')} />
              <Btn title="PDF" icon="document-text-outline" kind="secondary" style={{ flex: 1 }} onPress={() => addBill('file')} />
            </View>
          </Card>
        ) : null}

        {busy ? <Loading label={busy} /> : null}
        {error ? <ErrorNote error={error} /> : null}
        {result ? <CheckResult result={result} policy={p} claimType={claimType} /> : null}
        {msgs.length || result ? <Btn title="Start over" kind="ghost" icon="refresh-outline" style={{ height: 42 }} onPress={startOver} /> : null}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function Chip({ on, label, onPress }: { on: boolean; label: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={{ paddingHorizontal: 12, paddingVertical: 8, borderRadius: 99, borderWidth: 1.5, borderColor: on ? C.navy : C.line, backgroundColor: on ? C.skySoft : '#fff' }}>
      <Text style={{ fontWeight: '600', color: C.text }}>{label}</Text>
    </Pressable>
  );
}

function Bubble({ role, text }: { role: string; text: string }) {
  const me = role === 'user';
  return (
    <View style={{ alignSelf: me ? 'flex-end' : 'flex-start', maxWidth: '88%', backgroundColor: me ? C.navy : C.paleBlue, borderRadius: 16, padding: 12, gap: 8 }}>
      <Text style={{ color: me ? '#fff' : C.text, fontSize: 14, lineHeight: 20 }}>{text}</Text>
      {!me ? <ListenButton text={text} /> : null}
    </View>
  );
}

function CheckResult({ result, policy, claimType }: { result: any; policy: any; claimType: string }) {
  const high = result.findings.filter((f: any) => f.severity === 'high').length;
  const est = result.estimate;
  return (
    <View style={{ gap: 12 }}>
      <Card style={{ gap: 8, borderColor: high ? C.red : C.green, borderWidth: 1.5 }}>
        <Text style={{ fontSize: 18, fontWeight: '800' }}>{high ? `${high} thing${high > 1 ? 's' : ''} to fix before discharge` : 'Your stay looks covered'}</Text>
        {result.summary ? <Text style={{ color: C.text }}>{result.summary}</Text> : null}
        <ListenButton text={result.summary ?? result.findings.map((f: any) => `${f.title}. ${f.detail}`).join(' ')} />
      </Card>
      {result.findings.map((f: any, i: number) => {
        const s = SEV[f.severity] ?? SEV.medium;
        return (
          <Card key={i} style={{ gap: 6, backgroundColor: s.bg, borderColor: 'transparent' }}>
            <View style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-start' }}>
              <Ionicons name={s.icon} size={20} color={s.color} />
              <Text style={{ fontWeight: '700', flex: 1, color: C.text }}>{f.title}</Text>
            </View>
            <Text style={{ color: C.text }}>{f.detail}</Text>
            {f.clause_id ? <Text style={{ color: C.sky, fontSize: 12, fontWeight: '600' }}>Clause {f.clause_id}</Text> : null}
          </Card>
        );
      })}
      {est ? (
        <Card style={{ gap: 4, alignItems: 'center' }}>
          <Text style={{ color: C.sub }}>On an estimated bill of {rupees(est.billed)}, insurance would pay about</Text>
          <Money value={est.payable} size={30} color={C.navy} />
          <Text style={{ color: C.red, fontWeight: '700' }}>You pay about {rupees(est.billed - est.payable)}</Text>
        </Card>
      ) : null}
      <Section title="Do this now">
        <Card style={{ gap: 8 }}>
          {result.actions.map((a: string, i: number) => (
            <View key={i} style={{ flexDirection: 'row', gap: 8 }}>
              <Ionicons name="arrow-forward-circle" size={18} color={C.navy} />
              <Text style={{ flex: 1 }}>{a}</Text>
            </View>
          ))}
        </Card>
      </Section>
      <Section title="Deadlines">
        <Card style={{ gap: 8 }}>
          {Object.values(result.deadlines).map((d: any, i) => (
            <View key={i} style={{ flexDirection: 'row', gap: 8 }}>
              <Ionicons name="timer-outline" size={18} color={C.amber} />
              <Text style={{ flex: 1 }}>{d}</Text>
            </View>
          ))}
        </Card>
      </Section>
      <Section title="Collect before you leave">
        <Card style={{ gap: 8 }}>
          {result.documents.map((d: string, i: number) => (
            <View key={i} style={{ flexDirection: 'row', gap: 8 }}>
              <Ionicons name="document-text-outline" size={18} color={C.navy} />
              <Text style={{ flex: 1 }}>{d}</Text>
            </View>
          ))}
        </Card>
      </Section>
      {claimType === 'cashless' ? (
        <Card style={{ gap: 8 }}>
          <Text style={{ fontWeight: '700' }}>At the discharge counter</Text>
          <Text style={{ color: C.sub }}>If cashless does not cover the full bill, pay the rest with UPI. The receipt is saved for your records.</Text>
          <Btn title="Pay hospital with UPI" kind="secondary" icon="qr-code-outline" onPress={() => router.push(`/pay?amount=${est ? Math.round(est.billed - est.payable) : ''}`)} />
        </Card>
      ) : (
        <Btn title="Start my claim" onPress={() => router.push(`/policies/${policy?.id}`)} />
      )}
    </View>
  );
}
