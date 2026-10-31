import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Text, View } from 'react-native';

import { rupees, send } from '@/lib/api';
import { C } from '@/lib/theme';
import { act, Btn, Card, Field, Header, Screen } from '@/ui/kit';

/** Mock UPI payment at the discharge counter. No real money moves. */
export default function Pay() {
  const { amount, claim } = useLocalSearchParams<{ amount?: string; claim?: string }>();
  const [amt, setAmt] = useState(amount ?? '');
  const [payee, setPayee] = useState('Shree Sai Multispeciality Hospital');
  const [busy, setBusy] = useState(false);
  const [txn, setTxn] = useState<any>(null);

  if (txn)
    return (
      <View style={{ flex: 1 }}>
        <Header sub="" />
        <Screen footer={<Btn title="Done" onPress={() => router.back()} />}>
          <Card style={{ alignItems: 'center', gap: 10, paddingVertical: 32 }}>
            <Ionicons name="checkmark-circle" size={72} color={C.green} />
            <Text style={{ fontSize: 28, fontWeight: '800' }}>{rupees(txn.amount)}</Text>
            <Text style={{ color: C.sub }}>Paid to {txn.payee}</Text>
            <Text style={{ color: C.faint, fontSize: 12 }}>UPI Ref {txn.utr} · demo payment</Text>
          </Card>
          <Text style={{ color: C.sub, textAlign: 'center' }}>Keep this receipt. It counts as a payment proof for your claim.</Text>
        </Screen>
      </View>
    );

  return (
    <View style={{ flex: 1 }}>
      <Header sub="UPI" title="Pay hospital" />
      <Screen
        footer={
          <Btn
            title={`Pay ${amt ? rupees(Number(amt)) : ''}`}
            disabled={!Number(amt)}
            loading={busy}
            onPress={act(async () => {
              setBusy(true);
              try {
                setTxn(await send('/mock/upi/pay', { amount: Number(amt), payee, note: 'Hospital discharge', claim_id: claim }));
              } finally {
                setBusy(false);
              }
            })}
          />
        }>
        <Field label="Pay to" value={payee} onChangeText={setPayee} />
        <Field label="Amount (₹)" value={amt} onChangeText={setAmt} keyboardType="numeric" />
        <Text style={{ color: C.faint, fontSize: 12 }}>Demo: Paytm UPI is simulated. You would enter your UPI PIN in the next step.</Text>
      </Screen>
    </View>
  );
}
