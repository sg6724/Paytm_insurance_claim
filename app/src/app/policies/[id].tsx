import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { get, rupees, send } from '@/lib/api';
import { useApp } from '@/lib/app-context';
import { C } from '@/lib/theme';
import { Btn, Card, ErrorNote, Field, Header, IconBubble, Loading, Pill, Row, Screen, Section, Sheet, useAsync } from '@/ui/kit';
import { Tip } from '@/ui/tip';
import { ListenButton } from '@/ui/voice';

const TOPIC_ICON: Record<string, any> = { room_rent: 'bed-outline', waiting: 'time-outline', coverage: 'medkit-outline', copay: 'cash-outline', claims: 'business-outline' };

export default function PolicyDetail() {
  const { id, sample } = useLocalSearchParams<{ id: string; sample?: string }>();
  const { lang, t, setAssistantCtx } = useApp();
  const policy = useAsync(() => get(`/policies/${id}`), [id]);
  const ex = useAsync(() => get(`/policies/${id}/explainer?lang=${lang}`), [id, lang]);
  const [open, setOpen] = useState<string | null>('room_rent');
  const [clause, setClause] = useState<any | null>(null);
  const [startOpen, setStartOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState(false);

  useFocusEffect(useCallback(() => setAssistantCtx({ screen: 'policy_explainer', policy_id: id }), [id, setAssistantCtx]));

  async function startClaim(type: string, memberId: string) {
    setBusy(true);
    try {
      const c = await send('/claims', { policy_id: id, member_id: memberId, claim_type: type });
      setStartOpen(false);
      router.push(`/claims/${c.id}/documents${sample ? `?sample=${sample}` : ''}`);
    } finally {
      setBusy(false);
    }
  }

  const p = policy.data;
  if (!p) return (<View style={{ flex: 1 }}><Header sub="" />{policy.error ? <ErrorNote error={policy.error} /> : <Loading />}</View>);
  const sampleMember = sample ? { sunita_gallbladder: 'm_sunita', rakesh_knee: 'm_rakesh', arjun_dengue: 'm_arjun' }[sample] : undefined;

  return (
    <View style={{ flex: 1 }}>
      <Header sub="" />
      <Screen
        footer={
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <Btn title={t('imInHospital')} kind="secondary" icon="medkit-outline" style={{ flex: 1 }} onPress={() => router.push(`/hospital/${id}`)} />
            <Btn title={t('startClaim')} icon="document-text-outline" style={{ flex: 1 }} onPress={() => setStartOpen(true)} />
          </View>
        }>
        <Tip id="policy" text="Tap a topic to read it in plain words. The clause link shows the exact wording from your policy, and Listen reads it aloud in your language." />
        <Card style={{ backgroundColor: C.navy, borderColor: C.navy, gap: 6 }}>
          <Text style={{ color: '#BFD7F5', fontSize: 12 }}>{p.insurer}</Text>
          <Text style={{ color: '#fff', fontSize: 20, fontWeight: '800' }}>{p.plan}</Text>
          <Text style={{ color: '#BFD7F5', fontSize: 12 }}>Policy {p.policy_number ?? '—'}</Text>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 }}>
            <View>
              <Text style={{ color: '#BFD7F5', fontSize: 12 }}>Cover</Text>
              <Text style={{ color: '#fff', fontSize: 18, fontWeight: '800' }}>{rupees(p.sum_insured)}</Text>
            </View>
            <View>
              <Text style={{ color: '#BFD7F5', fontSize: 12 }}>Room limit</Text>
              <Text style={{ color: '#fff', fontSize: 18, fontWeight: '800' }}>{ex.data?.highlights?.room_cap_per_day ? rupees(ex.data.highlights.room_cap_per_day) + '/day' : 'None'}</Text>
            </View>
            <View>
              <Text style={{ color: '#BFD7F5', fontSize: 12 }}>Co-pay</Text>
              <Text style={{ color: '#fff', fontSize: 18, fontWeight: '800' }}>{(p.copay?.percent ?? 0) + '%'}</Text>
            </View>
          </View>
          <Text style={{ color: '#fff', marginTop: 6 }}>{p.members.map((m: any) => `${m.name} (${m.relation}${m.age ? ', ' + m.age : ''})`).join(' · ')}</Text>
        </Card>

        {p.review_ticket ? (
          <Card style={{ backgroundColor: C.amberSoft, borderColor: '#F5D9A8' }}>
            <Text style={{ fontWeight: '700', color: C.amber }}>A person will double-check this policy</Text>
            <Text style={{ color: C.amber, fontSize: 13 }}>We could not read it with enough confidence ({p.review_ticket}). Please confirm the details below meanwhile.</Text>
          </Card>
        ) : null}

        {p.needs_review?.length ? (
          <Card style={{ backgroundColor: C.amberSoft, borderColor: '#F5D9A8' }} onPress={() => setReview(true)}>
            <Text style={{ fontWeight: '700', color: C.amber }}>Please confirm {p.needs_review.length} details</Text>
            <Text style={{ color: C.amber, fontSize: 13 }}>AI was not fully sure about: {p.needs_review.slice(0, 4).join(', ')}. Tap to check.</Text>
          </Card>
        ) : null}

        <Section title={t('yourCover')}>
          {ex.loading ? <Loading label={lang.startsWith('en') ? 'Explaining your policy…' : 'Translating with Sarvam…'} /> : null}
          {ex.data?.topics?.map((tp: any) => (
            <Card key={tp.key} style={{ paddingVertical: 4 }}>
              <Row icon={TOPIC_ICON[tp.key]} title={tp.title} sub={tp.question} onPress={() => setOpen(open === tp.key ? null : tp.key)}
                right={<Ionicons name={open === tp.key ? 'chevron-up' : 'chevron-down'} size={20} color={C.text} />} />
              {open === tp.key ? (
                <View style={{ paddingBottom: 12, gap: 10 }}>
                  <Text style={{ fontSize: 15, lineHeight: 23, color: C.text }}>{tp.text}</Text>
                  <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                    <ListenButton text={tp.text} />
                    {tp.clause ? (
                      <Pressable onPress={() => setClause(tp.clause)} style={{ flexDirection: 'row', gap: 4, alignItems: 'center', paddingHorizontal: 10, paddingVertical: 8 }}>
                        <Ionicons name="document-outline" size={14} color={C.sky} />
                        <Text style={{ color: C.sky, fontWeight: '600', fontSize: 13 }}>Clause {tp.clause.id}, page {tp.clause.page}</Text>
                      </Pressable>
                    ) : null}
                  </View>
                </View>
              ) : null}
            </Card>
          ))}
        </Section>
        <Pressable onPress={() => router.push('/settings')} style={{ flexDirection: 'row', gap: 6, alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="language-outline" size={16} color={C.navy} />
          <Text style={{ color: C.navy, fontWeight: '600' }}>Read this in another language</Text>
        </Pressable>
      </Screen>

      <Sheet visible={!!clause} onClose={() => setClause(null)} title={clause ? `Clause ${clause.id}: ${clause.title}` : ''}>
        <Pill text={`Page ${clause?.page}`} tone="muted" />
        <Text style={{ fontSize: 15, lineHeight: 23, color: C.text, fontStyle: 'italic' }}>“{clause?.text}”</Text>
        <Text style={{ color: C.sub, fontSize: 12 }}>Exact wording from your policy document.</Text>
      </Sheet>

      <Sheet visible={startOpen} onClose={() => setStartOpen(false)} title="Start a claim">
        <Text style={{ color: C.sub }}>Who was in hospital, and how is the bill being paid?</Text>
        {p.members.map((m: any) => (
          <Card key={m.id} style={{ gap: 10, borderColor: sampleMember === m.id ? C.sky : C.line }}>
            <View style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
              <IconBubble name="person" size={36} />
              <Text style={{ fontWeight: '700', flex: 1 }}>{m.name} · {m.relation}</Text>
              {sampleMember === m.id ? <Pill text="Sample" /> : null}
            </View>
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <Btn title={t('reimbursement')} style={{ flex: 1, height: 44 }} loading={busy} onPress={() => startClaim('reimbursement', m.id)} />
              <Btn title={t('cashless')} kind="secondary" style={{ flex: 1, height: 44 }} onPress={() => startClaim('cashless', m.id)} />
            </View>
          </Card>
        ))}
      </Sheet>

      <ReviewSheet visible={review} onClose={() => setReview(false)} policy={p} onSaved={(np) => policy.setData(np)} />
    </View>
  );
}

function ReviewSheet({ visible, onClose, policy, onSaved }: { visible: boolean; onClose: () => void; policy: any; onSaved: (p: any) => void }) {
  const [vals, setVals] = useState<Record<string, string>>({});
  const fields = (policy.needs_review ?? []).filter((f: string) => ['sum_insured', 'policy_number', 'start_date', 'end_date', 'insurer', 'plan', 'deductible', 'submission_days'].includes(f));
  return (
    <Sheet visible={visible} onClose={onClose} title="Confirm details">
      {fields.length === 0 ? <Text style={{ color: C.sub }}>These need a closer look in the document: {(policy.needs_review ?? []).join(', ')}. You can continue; we will flag them if they matter for a claim.</Text> : null}
      {fields.map((f: string) => (
        <Field key={f} label={f.replace(/_/g, ' ')} value={vals[f] ?? String(policy[f] ?? '')} onChangeText={(v) => setVals({ ...vals, [f]: v })} />
      ))}
      <Btn
        title="Looks right"
        onPress={async () => {
          const updates: Record<string, any> = {};
          for (const f of policy.needs_review ?? []) updates[f] = vals[f] !== undefined ? (['sum_insured', 'deductible', 'submission_days'].includes(f) ? Number(vals[f]) : vals[f]) : policy[f];
          onSaved(await send(`/policies/${policy.id}`, { updates }, 'PATCH'));
          onClose();
        }}
      />
    </Sheet>
  );
}
