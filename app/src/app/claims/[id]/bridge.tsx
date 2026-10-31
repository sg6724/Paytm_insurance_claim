import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { get, rupees, send } from '@/lib/api';
import { C } from '@/lib/theme';
import { Btn, Card, ErrorNote, Header, Loading, Money, Screen, Section, useAsync } from '@/ui/kit';

export default function Bridge() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const q = useAsync(() => get(`/claims/${id}/bridge`), [id]);
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const o = q.data;
  const emi = o?.kind === 'medical_emi';

  const rows: [string, string][] = o
    ? emi
      ? [
          ['Loan amount', rupees(o.principal)],
          ['Annual interest rate (APR)', `${o.apr}%`],
          ['Tenure', `${o.tenure_months} months`],
          ['Monthly EMI', rupees(o.emi)],
          ['Processing fee + GST', `${rupees(o.processing_fee)} + ${rupees(o.gst)}`],
          ['Total you repay', rupees(o.total_repayable)],
          ['Cooling-off period', `${o.cooling_off_days} days, cancel free`],
        ]
      : [
          ['Loan amount', rupees(o.principal)],
          ['Annual interest rate (APR)', `${o.apr}%`],
          ['Tenure', `${o.tenure_days} days or until settlement`],
          ['Interest', rupees(o.interest)],
          ['Processing fee + GST', `${rupees(o.processing_fee)} + ${rupees(o.gst)}`],
          ['Total you repay', rupees(o.total_repayable)],
          ['Repayment', 'From your claim settlement, automatically'],
          ['Cooling-off period', `${o.cooling_off_days} days, cancel free`],
        ]
    : [];

  return (
    <View style={{ flex: 1 }}>
      <Header title={emi ? 'Medical EMI' : 'Bridge until settlement'} sub="" />
      <Screen
        footer={
          o ? (
            <>
              <Pressable onPress={() => setAgree(!agree)} style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-start' }}>
                <Ionicons name={agree ? 'checkbox' : 'square-outline'} size={20} color={C.navy} />
                <Text style={{ flex: 1, fontSize: 12, color: C.text }}>I have read the Key Facts. I agree to share my claim status with {o.lender} for this loan.</Text>
              </Pressable>
              <Btn
                title={`Get ${rupees(o.principal)}`}
                disabled={!agree}
                loading={busy}
                onPress={async () => {
                  setBusy(true);
                  try {
                    await send(`/claims/${id}/bridge/accept`, { consent: agree });
                    router.replace(`/claims/${id}`);
                  } finally {
                    setBusy(false);
                  }
                }}
              />
            </>
          ) : null
        }>
        {q.loading ? <Loading /> : null}
        {q.error ? <ErrorNote error={q.error} /> : null}
        {o ? (
          <>
            <Card style={{ alignItems: 'center', gap: 6, backgroundColor: C.paleBlue, borderColor: '#CFE6F7' }}>
              <Text style={{ color: C.sub }}>Available now</Text>
              <Money value={o.principal} size={36} color={C.navy} />
              <Text style={{ color: C.sub, textAlign: 'center' }}>{o.why}</Text>
            </Card>
            <Section title="Key Facts Statement">
              <Card style={{ gap: 0 }}>
                {rows.map(([k, v]) => (
                  <View key={k} style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: C.line }}>
                    <Text style={{ color: C.sub, flex: 1 }}>{k}</Text>
                    <Text style={{ fontWeight: '700', textAlign: 'right', flex: 1 }}>{v}</Text>
                  </View>
                ))}
                <Text style={{ color: C.sub, fontSize: 12, marginTop: 10 }}>{o.repayment}</Text>
              </Card>
            </Section>
            <Card style={{ gap: 6 }}>
              <Text style={{ fontWeight: '700' }}>Lender: {o.lender}</Text>
              <Text style={{ color: C.sub, fontSize: 13 }}>The lender decides whether to lend. Paytm only connects you. Loan terms follow the RBI Digital Lending Directions: Key Facts before you accept, money goes straight to your account, and you can cancel during the cooling-off period without penalty.</Text>
            </Card>
          </>
        ) : null}
      </Screen>
    </View>
  );
}
