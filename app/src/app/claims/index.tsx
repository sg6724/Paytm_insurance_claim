import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useFocusEffect } from 'expo-router';
import { useCallback } from 'react';
import { Text, View } from 'react-native';

import { get, rupees } from '@/lib/api';
import { C } from '@/lib/theme';
import { Btn, Card, Header, IconBubble, Loading, Pill, Screen, useAsync } from '@/ui/kit';

export default function Claims() {
  const q = useAsync(() => get<any[]>('/claims'));
  useFocusEffect(
    useCallback(() => {
      q.reload();
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []),
  );
  return (
    <View style={{ flex: 1 }}>
      <Header title="My claims" sub="" />
      <Screen>
        {q.loading && !q.data ? <Loading /> : null}
        {q.data?.length === 0 ? (
          <Card style={{ alignItems: 'center', gap: 10, paddingVertical: 28 }}>
            <IconBubble name="receipt-outline" size={56} />
            <Text style={{ fontWeight: '600' }}>No claims yet</Text>
            <Btn title="Start from a policy" kind="secondary" onPress={() => router.push('/policies')} />
          </Card>
        ) : null}
        {(q.data ?? []).map((c) => {
          const m = c.policy?.members?.find((x: any) => x.id === (c.form?.member_id ?? c.member_id));
          return (
            <Card key={c.id} onPress={() => router.push(`/claims/${c.id}`)} style={{ gap: 6 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Text style={{ fontWeight: '700', flex: 1 }}>{m?.name} · {c.form?.procedure || c.claim_type}</Text>
                <Pill text={c.status.replace(/_/g, ' ')} tone={c.status === 'settled' ? 'ok' : c.status === 'rejected' ? 'bad' : 'info'} />
                <Ionicons name="chevron-forward" size={18} color={C.text} />
              </View>
              <Text style={{ color: C.sub }}>
                {c.policy?.plan} · {c.decision ? `Approved ${rupees(c.decision.amount_approved)}` : c.preflight ? `Expected ${rupees(c.preflight.payable)}` : 'In progress'}
              </Text>
            </Card>
          );
        })}
      </Screen>
    </View>
  );
}
