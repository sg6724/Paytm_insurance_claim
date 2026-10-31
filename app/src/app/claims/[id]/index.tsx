import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useState } from 'react';
import { Text, View } from 'react-native';

import { fmtDate, fmtTime, get, rupees, send } from '@/lib/api';
import { useApp } from '@/lib/app-context';
import { C } from '@/lib/theme';
import { Btn, Card, Header, Loading, Money, Pill, Screen, Section, Sheet, useAsync } from '@/ui/kit';
import { Tip } from '@/ui/tip';

const STATUS_TONE: Record<string, any> = { settled: 'ok', approved: 'ok', partially_approved: 'warn', rejected: 'bad', query_raised: 'warn' };
const STEPS = ['submitted', 'under_review', 'decision', 'settled'];

export default function ClaimTracker() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { setAssistantCtx } = useApp();
  const q = useAsync(() => get(`/claims/${id}`), [id]);
  const [task, setTask] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  useFocusEffect(
    useCallback(() => {
      setAssistantCtx({ screen: 'claim_tracker', claim_id: id });
      q.reload();
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [id]),
  );

  const c = q.data;
  if (!c) return (<View style={{ flex: 1 }}><Header sub="" /><Loading /></View>);
  const member = c.policy?.members?.find((m: any) => m.id === (c.form?.member_id ?? c.member_id));
  const decided = ['approved', 'partially_approved', 'rejected', 'settled'].includes(c.status);
  const stepIdx = c.status === 'settled' ? 3 : decided ? 2 : ['under_review', 'query_raised'].includes(c.status) ? 1 : c.status === 'submitted' ? 0 : -1;
  const openTasks = (c.tasks ?? []).filter((t: any) => t.status === 'open');

  async function advance() {
    setBusy(true);
    try {
      q.setData(await send(`/claims/${id}/advance`));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={{ flex: 1 }}>
      <Header sub="" title="Claim status" />
      <Screen>
        <Tip id="tracker" text="Your claim moves through these steps. We tell you when the insurer asks for something or decides, and what you can do next." />
        <Card style={{ gap: 8 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text style={{ color: C.sub, fontSize: 12 }}>{c.insurer_ref ?? 'Not submitted yet'}</Text>
            <Pill text={c.status.replace(/_/g, ' ')} tone={STATUS_TONE[c.status] ?? 'info'} />
          </View>
          <Text style={{ fontWeight: '800', fontSize: 18 }}>{member?.name} · {c.form?.procedure || c.form?.diagnosis || 'Hospital claim'}</Text>
          <Text style={{ color: C.sub }}>{c.policy?.plan} · {c.form?.hospital_name}</Text>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginTop: 6 }}>
            <View>
              <Text style={{ color: C.sub, fontSize: 12 }}>Claimed</Text>
              <Money value={c.preflight?.billed ?? Number(c.form?.total_claimed)} size={18} />
            </View>
            <View style={{ alignItems: 'flex-end' }}>
              <Text style={{ color: C.sub, fontSize: 12 }}>{c.decision ? 'Approved' : 'Expected'}</Text>
              <Money value={c.decision ? c.decision.amount_approved : c.preflight?.payable} size={18} color={C.navy} />
            </View>
          </View>
        </Card>

        {stepIdx >= 0 ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', paddingHorizontal: 6 }}>
            {STEPS.map((s, i) => (
              <View key={s} style={{ flex: 1, alignItems: 'center' }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', width: '100%' }}>
                  <View style={{ flex: 1, height: 3, backgroundColor: i === 0 ? 'transparent' : i <= stepIdx ? C.navy : C.line }} />
                  <View style={{ width: 22, height: 22, borderRadius: 11, backgroundColor: i <= stepIdx ? C.navy : C.line, alignItems: 'center', justifyContent: 'center' }}>
                    {i <= stepIdx ? <Ionicons name="checkmark" size={14} color="#fff" /> : null}
                  </View>
                  <View style={{ flex: 1, height: 3, backgroundColor: i === STEPS.length - 1 ? 'transparent' : i < stepIdx ? C.navy : C.line }} />
                </View>
                <Text style={{ fontSize: 11, color: C.sub, marginTop: 4 }}>{['Submitted', 'Review', 'Decision', 'Paid'][i]}</Text>
              </View>
            ))}
          </View>
        ) : null}

        {c.status === 'draft' || c.status === 'documents_pending' || c.status === 'ready' ? (
          <Btn title="Continue claim" onPress={() => router.push(`/claims/${id}/${c.fill_mode ? 'form' : 'documents'}`)} />
        ) : null}

        {openTasks.map((t: any) => (
          <Card key={t.id} style={{ borderColor: C.amber, borderWidth: 1.5, gap: 8 }} onPress={() => setTask(t)}>
            <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
              <Ionicons name="alert-circle" size={20} color={C.amber} />
              <Text style={{ fontWeight: '700', flex: 1 }}>{t.title}</Text>
            </View>
            <Text style={{ color: C.sub }}>Reply by {fmtDate(t.due)}. Tap to respond.</Text>
          </Card>
        ))}

        {c.decision ? (
          <Card style={{ gap: 10, borderColor: c.decision.type === 'rejected' ? C.red : C.sky, borderWidth: 1.5 }}>
            <Text style={{ fontWeight: '800', fontSize: 16 }}>{c.decision.type === 'rejected' ? 'Your claim was rejected' : `Insurer approved ${rupees(c.decision.amount_approved)}`}</Text>
            <Text style={{ color: C.sub }}>Understand why, in your language, and see what you can do next.</Text>
            <Btn title="Explain this decision" icon="chatbubble-ellipses-outline" onPress={() => router.push(`/claims/${id}/decision`)} />
          </Card>
        ) : null}

        {c.bridge_offer ? (
          <Card style={{ gap: 8, backgroundColor: C.paleBlue, borderColor: '#CFE6F7' }} onPress={() => router.push(`/claims/${id}/bridge`)}>
            <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
              <Ionicons name="flash" size={20} color={C.navy} />
              <Text style={{ fontWeight: '800', flex: 1 }}>{c.bridge_offer.kind === 'medical_emi' ? 'Pay the hospital in EMIs' : 'Need money before the insurer pays?'}</Text>
              <Ionicons name="chevron-forward" size={20} color={C.text} />
            </View>
            <Text style={{ color: C.sub }}>
              {c.bridge_offer.kind === 'medical_emi'
                ? `Up to ${rupees(c.bridge_offer.principal)} from a partner lender. See Key Facts first.`
                : `Get up to ${rupees(c.bridge_offer.principal)} now from a partner lender, repaid from your settlement.`}
            </Text>
          </Card>
        ) : null}
        {c.bridge ? (
          <Card style={{ gap: 4 }}>
            <Text style={{ fontWeight: '700' }}>Bridge loan · {c.bridge.status}</Text>
            <Text style={{ color: C.sub }}>{rupees(c.bridge.principal)} from {c.bridge.lender}. {c.bridge.status === 'repaid' ? 'Repaid from your settlement.' : c.bridge.status === 'part_repaid' ? `${rupees(c.bridge.balance_due)} is still due in EMIs.` : `Repaid automatically when the insurer pays. Cancel free until ${fmtDate(c.bridge.cooling_off_until)}.`}</Text>
          </Card>
        ) : null}

        {c.deadlines?.settlement_due && !c.settled_on ? (
          <Card style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
            <Ionicons name="timer-outline" size={22} color={C.navy} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontWeight: '700' }}>Insurer must settle by {fmtDate(c.deadlines.settlement_due)}</Text>
              <Text style={{ color: C.sub, fontSize: 12 }}>30 days from your last document. If late, they owe you interest at 2% above bank rate.</Text>
              {c.deadlines.interest_due ? <Text style={{ color: C.green, fontWeight: '700' }}>Interest owed so far: {rupees(c.deadlines.interest_due)}</Text> : null}
            </View>
          </Card>
        ) : null}

        <Section title="Timeline">
          <Card style={{ gap: 0 }}>
            {[...(c.timeline ?? [])].reverse().map((e: any, i: number, arr: any[]) => (
              <View key={i} style={{ flexDirection: 'row', gap: 12 }}>
                <View style={{ alignItems: 'center' }}>
                  <View style={{ width: 12, height: 12, borderRadius: 6, backgroundColor: i === 0 ? C.navy : C.line, marginTop: 4 }} />
                  {i < arr.length - 1 ? <View style={{ width: 2, flex: 1, backgroundColor: C.line }} /> : null}
                </View>
                <View style={{ flex: 1, paddingBottom: 14 }}>
                  <Text style={{ fontWeight: '600' }}>{e.title}</Text>
                  {e.detail ? <Text style={{ color: C.sub, fontSize: 13 }}>{e.detail}</Text> : null}
                  <Text style={{ color: C.faint, fontSize: 11 }}>{fmtTime(e.at)}</Text>
                </View>
              </View>
            ))}
          </Card>
        </Section>

        {c.insurer_ref ? (
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <Btn title="NHCX claim pack" kind="ghost" icon="code-slash-outline" style={{ flex: 1 }} onPress={() => router.push(`/claims/${id}/fhir`)} />
            {c.status !== 'settled' && c.status !== 'rejected' ? (
              <Btn title="Insurer: next step" kind="ghost" icon="play-forward-outline" style={{ flex: 1 }} loading={busy} onPress={advance} />
            ) : null}
          </View>
        ) : null}
        {c.insurer_ref ? <Text style={{ color: C.faint, fontSize: 11, textAlign: 'center' }}>{'Demo control: "Insurer: next step" moves the mock insurer forward.'}</Text> : null}
      </Screen>

      <Sheet visible={!!task} onClose={() => setTask(null)} title={task?.title}>
        <Text style={{ color: C.text }}>{task?.detail}</Text>
        <Btn
          title="Upload the documents and reply"
          onPress={async () => {
            q.setData(await send(`/claims/${id}/tasks/${task.id}`, { note: 'Pharmacy bills and prescriptions uploaded' }));
            setTask(null);
          }}
        />
      </Sheet>
    </View>
  );
}
