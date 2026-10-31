import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Linking, Text, View } from 'react-native';

import { API_BASE, rupees, send } from '@/lib/api';
import { useApp } from '@/lib/app-context';
import { C } from '@/lib/theme';
import { Btn, Card, ErrorNote, Header, Loading, Money, Pill, Screen, Section, useAsync } from '@/ui/kit';

const KIND: Record<string, { label: string; icon: any }> = {
  non_payable: { label: 'Not payable', icon: 'close-circle-outline' },
  proportionate: { label: 'Room rent ratio', icon: 'git-compare-outline' },
  room_excess: { label: 'Room above limit', icon: 'bed-outline' },
  sub_limit: { label: 'Sub-limit', icon: 'remove-circle-outline' },
  copay: { label: 'Co-pay', icon: 'cash-outline' },
  deductible: { label: 'Deductible', icon: 'cash-outline' },
  si_cap: { label: 'Cover exhausted', icon: 'alert-circle-outline' },
  waiting: { label: 'Waiting period', icon: 'time-outline' },
};

export default function Preflight() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t } = useApp();
  const q = useAsync(() => send(`/claims/${id}/preflight`), [id]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const r = q.data;

  const groups: Record<string, { total: number; items: any[] }> = {};
  (r?.deductions ?? []).forEach((d: any) => {
    groups[d.kind] = groups[d.kind] ?? { total: 0, items: [] };
    groups[d.kind].total += d.amount;
    groups[d.kind].items.push(d);
  });

  return (
    <View style={{ flex: 1 }}>
      <Header title="Before you submit" sub="" />
      <Screen
        footer={
          r ? (
            <>
              {error ? <Text style={{ color: C.red, textAlign: 'center' }}>{error}</Text> : null}
              <Btn
                title={r.rejected ? 'Submit anyway' : t('submit')}
                kind={r.rejected ? 'ghost' : 'primary'}
                loading={submitting}
                onPress={async () => {
                  setSubmitting(true);
                  setError(null);
                  try {
                    await send(`/claims/${id}/submit`);
                    router.replace(`/claims/${id}`);
                  } catch (e: any) {
                    setError(e.message);
                    if (e.body?.detail?.corrections) router.back();
                  } finally {
                    setSubmitting(false);
                  }
                }}
              />
            </>
          ) : null
        }>
        {q.loading ? <Loading label="Checking against your policy rules…" /> : null}
        {q.error ? <ErrorNote error={q.error} onRetry={q.reload} /> : null}
        {r ? (
          <>
            <Card style={{ alignItems: 'center', gap: 6, paddingVertical: 24, backgroundColor: r.rejected ? C.redSoft : C.paleBlue, borderColor: r.rejected ? '#F7C5C0' : '#CFE6F7' }}>
              <Text style={{ color: C.sub }}>{r.rejected ? 'This claim is likely to be rejected' : t('expectedPayout')}</Text>
              <Money value={r.payable} size={40} color={r.rejected ? C.red : C.navy} />
              <Text style={{ color: C.sub }}>
                {t('of')} {rupees(r.billed)} billed
              </Text>
              <Pill text={`Rejection risk: ${r.risk}`} tone={r.risk === 'low' ? 'ok' : r.risk === 'medium' ? 'warn' : 'bad'} />
            </Card>
            {r.rejected ? (
              <Card style={{ gap: 6 }}>
                {r.reject_reasons.map((x: any, i: number) => (
                  <View key={i} style={{ flexDirection: 'row', gap: 8 }}>
                    <Ionicons name="alert-circle" size={18} color={C.red} />
                    <Text style={{ flex: 1 }}>
                      {x.reason} {x.clause_id ? <Text style={{ color: C.sky }}>(Clause {x.clause_id})</Text> : null}
                    </Text>
                  </View>
                ))}
                <Text style={{ color: C.sub, marginTop: 6 }}>You can still submit. If it is rejected, we will show your options, including paying the bill in EMIs.</Text>
              </Card>
            ) : null}
            {!r.rejected && r.deductions.length ? (
              <Section title={`${t('whyDeducted')} · ${rupees(r.total_deducted)}`}>
                {Object.entries(groups).map(([k, g]) => (
                  <Card key={k} style={{ gap: 8 }}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                      <Ionicons name={KIND[k]?.icon ?? 'remove-circle-outline'} size={18} color={C.amber} />
                      <Text style={{ fontWeight: '700', flex: 1 }}>{KIND[k]?.label ?? k}</Text>
                      <Text style={{ fontWeight: '800', color: C.red }}>−{rupees(g.total)}</Text>
                    </View>
                    {g.items.map((d: any, i: number) => (
                      <View key={i} style={{ flexDirection: 'row', gap: 8 }}>
                        <Text style={{ flex: 1, color: C.sub, fontSize: 13 }}>
                          {d.item}: {d.reason} {d.clause_id ? <Text style={{ color: C.sky }}>(Clause {d.clause_id})</Text> : null}
                        </Text>
                        <Text style={{ color: C.sub, fontSize: 13 }}>{rupees(d.amount)}</Text>
                      </View>
                    ))}
                  </Card>
                ))}
              </Section>
            ) : null}
            {r.flags?.length ? (
              <Card style={{ gap: 6, backgroundColor: C.amberSoft, borderColor: '#F5D9A8' }}>
                {r.flags.map((f: any, i: number) => (
                  <Text key={i} style={{ color: C.amber }}>• {f.message}</Text>
                ))}
              </Card>
            ) : null}
            <Btn title="Export the form as PDF" kind="ghost" icon="download-outline" onPress={() => Linking.openURL(`${API_BASE}/claims/${id}/form.pdf`)} />
            <Text style={{ color: C.faint, fontSize: 12, textAlign: 'center' }}>Calculated by the Claim-to-Cash rule engine from your policy terms and IRDAI rules. The insurer makes the final decision.</Text>
          </>
        ) : null}
      </Screen>
    </View>
  );
}
