import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useState } from 'react';
import { Pressable, Text, TextInput, View } from 'react-native';

import { fmtDate, get, rupees, send } from '@/lib/api';
import { useApp } from '@/lib/app-context';
import { C } from '@/lib/theme';
import { Btn, Card, ErrorNote, Header, Loading, Money, Pill, Screen, Section, Sheet, useAsync } from '@/ui/kit';
import { ListenButton } from '@/ui/voice';

const STRENGTH: Record<string, { label: string; tone: any }> = {
  strong: { label: 'Strong case to appeal', tone: 'ok' },
  weak: { label: 'Appeal unlikely to succeed', tone: 'bad' },
  none: { label: 'Deductions follow your policy', tone: 'muted' },
};

export default function Decision() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { lang, t, setAssistantCtx } = useApp();
  const q = useAsync(() => get(`/claims/${id}/decision?lang=${lang}`), [id, lang]);
  const [draft, setDraft] = useState<{ step: string; text: string; ombudsman?: any } | null>(null);
  const [drafting, setDrafting] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [letter, setLetter] = useState(false);

  useFocusEffect(useCallback(() => setAssistantCtx({ screen: 'decision_explainer', claim_id: id }), [id, setAssistantCtx]));

  async function openDraft(step: string) {
    setDrafting(step);
    try {
      setDraft(await send(`/claims/${id}/appeal/draft`, { step, lang }));
    } finally {
      setDrafting(null);
    }
  }

  const d = q.data;
  return (
    <View style={{ flex: 1 }}>
      <Header title="Your decision, explained" sub="" />
      <Screen>
        {q.loading ? <Loading label="Reading the insurer\u2019s letter and checking it against your policy…" /> : null}
        {q.error ? <ErrorNote error={q.error} onRetry={q.reload} /> : null}
        {d ? (
          <>
            <Card style={{ gap: 10 }}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                <View>
                  <Text style={{ color: C.sub, fontSize: 12 }}>Insurer paid</Text>
                  <Money value={d.decision.amount_approved} size={24} color={d.decision.type === 'rejected' ? C.red : C.text} />
                </View>
                <View style={{ alignItems: 'flex-end' }}>
                  <Text style={{ color: C.sub, fontSize: 12 }}>Policy rules say</Text>
                  <Money value={d.analysis.expected_payable} size={24} color={C.green} />
                </View>
              </View>
              <Pill text={STRENGTH[d.analysis.strength]?.label ?? ''} tone={STRENGTH[d.analysis.strength]?.tone} />
              {d.analysis.disputed_amount ? (
                <Text style={{ fontWeight: '700', color: C.green }}>{rupees(d.analysis.disputed_amount)} looks wrongly deducted.</Text>
              ) : null}
            </Card>

            <Card style={{ gap: 10 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Ionicons name="sparkles" size={18} color={C.navy} />
                <Text style={{ fontWeight: '700', flex: 1 }}>In plain words</Text>
                <ListenButton text={d.explanation} label={t('listen')} />
              </View>
              <Text style={{ fontSize: 15, lineHeight: 23, color: C.text }}>{d.explanation.replace(/\*\*/g, '')}</Text>
              <Pressable onPress={() => setLetter(true)}>
                <Text style={{ color: C.sky, fontWeight: '600' }}>See the insurer’s letter</Text>
              </Pressable>
            </Card>

            {d.analysis.grounds?.length ? (
              <Card style={{ gap: 6, backgroundColor: C.greenSoft, borderColor: '#BFE7D6' }}>
                <Text style={{ fontWeight: '700', color: C.green }}>Why you can appeal</Text>
                {d.analysis.grounds.map((g: string, i: number) => (
                  <Text key={i} style={{ color: C.text }}>• {g}</Text>
                ))}
              </Card>
            ) : null}

            <Section title={t('nextSteps')}>
              {d.ladder.map((s: any, i: number) => (
                <Card key={s.step} style={{ gap: 6, opacity: s.status === 'locked' ? 0.55 : 1 }}>
                  <View style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
                    <View style={{ width: 26, height: 26, borderRadius: 13, backgroundColor: s.status === 'sent' ? C.green : C.navy, alignItems: 'center', justifyContent: 'center' }}>
                      {s.status === 'sent' ? <Ionicons name="checkmark" size={16} color="#fff" /> : <Text style={{ color: '#fff', fontWeight: '700' }}>{i + 1}</Text>}
                    </View>
                    <Text style={{ fontWeight: '700', flex: 1 }}>{s.title}</Text>
                  </View>
                  <Text style={{ color: C.sub }}>{s.detail}</Text>
                  <Text style={{ color: C.amber, fontSize: 12, fontWeight: '600' }}>
                    {s.when}
                    {s.due ? ` · by ${fmtDate(s.due)}` : ''}
                  </Text>
                  {s.status === 'available' ? (
                    <Btn title={drafting === s.step ? 'Drafting…' : 'Draft letter for me'} icon="create-outline" kind={i === 0 ? 'primary' : 'secondary'} loading={drafting === s.step} onPress={() => openDraft(s.step)} style={{ height: 44 }} />
                  ) : null}
                  {s.status === 'sent' ? <Pill text="Sent" tone="ok" /> : null}
                </Card>
              ))}
            </Section>

            {d.decision.type === 'rejected' ? (
              <Card style={{ gap: 8 }}>
                <Text style={{ fontWeight: '700' }}>Need to pay the hospital bill?</Text>
                <Text style={{ color: C.sub }}>If you decide not to appeal, a partner lender can offer a medical EMI. You see the full Key Facts before anything is shared.</Text>
                <Btn title="See EMI options" kind="ghost" onPress={async () => { await send(`/claims/${id}/appeal/dismiss`); router.push(`/claims/${id}/bridge`); }} />
              </Card>
            ) : null}
            <Btn title={t('talkToHuman')} kind="ghost" icon="headset-outline" onPress={() => router.push('/assistant?human=1')} />
          </>
        ) : null}
      </Screen>

      <Sheet visible={!!draft} onClose={() => setDraft(null)} title="Your letter">
        {draft?.ombudsman?.found ? (
          <Card style={{ gap: 4, backgroundColor: C.paleBlue }}>
            <Text style={{ fontWeight: '700' }}>{draft.ombudsman.office}</Text>
            <Text style={{ color: C.sub, fontSize: 13 }}>{draft.ombudsman.email} · {draft.ombudsman.portal}</Text>
            {draft.ombudsman.rules.map((r: string) => (
              <Text key={r} style={{ color: C.sub, fontSize: 12 }}>• {r}</Text>
            ))}
          </Card>
        ) : null}
        <TextInput multiline value={draft?.text ?? ''} onChangeText={(v) => draft && setDraft({ ...draft, text: v })}
          style={{ borderWidth: 1, borderColor: C.line, borderRadius: 12, padding: 12, minHeight: 260, maxHeight: 360, textAlignVertical: 'top', fontSize: 14, color: C.text }} />
        <Text style={{ color: C.faint, fontSize: 12 }}>Edit anything. Nothing is sent until you tap Send.</Text>
        <Btn
          title="Send"
          icon="send"
          loading={sending}
          onPress={async () => {
            setSending(true);
            try {
              await send(`/claims/${id}/appeal/send`, { step: draft!.step, text: draft!.text });
              setDraft(null);
              q.reload();
            } finally {
              setSending(false);
            }
          }}
        />
      </Sheet>

      <Sheet visible={letter} onClose={() => setLetter(false)} title="Insurer's letter">
        <Text style={{ fontFamily: 'monospace', fontSize: 12, color: C.text }}>{d?.decision?.letter}</Text>
      </Sheet>
    </View>
  );
}
