import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback } from 'react';
import { Text, View } from 'react-native';

import { get, rupees } from '@/lib/api';
import { useApp } from '@/lib/app-context';
import { C } from '@/lib/theme';
import { Btn, Card, Header, IconBubble, Loading, Pill, Screen, useAsync } from '@/ui/kit';

export default function Policies() {
  const { next } = useLocalSearchParams<{ next?: string }>();
  const { t, setAssistantCtx } = useApp();
  const q = useAsync(() => get<any[]>('/policies'));
  useFocusEffect(
    useCallback(() => {
      setAssistantCtx({ screen: 'my_policies' });
      q.reload();
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []),
  );
  const list = q.data ?? [];

  return (
    <View style={{ flex: 1 }}>
      <Header sub="" title={next === 'hospital' ? 'Which policy covers this stay?' : t('myPolicies')} />
      <Screen footer={<Btn title={t('addPolicy')} icon="add" onPress={() => router.push('/policies/add')} />}>
        {q.loading && !q.data ? <Loading /> : null}
        {!q.loading && list.length === 0 ? (
          <>
            <Card style={{ alignItems: 'center', paddingVertical: 32, gap: 10 }}>
              <IconBubble name="document-text-outline" size={64} />
              <Text style={{ fontSize: 16, fontWeight: '600' }}>{t('noPolicies')}</Text>
              <Text style={{ color: C.sub, textAlign: 'center' }}>{t('noPoliciesSub')}</Text>
            </Card>
            <Btn title={t('trySample')} kind="secondary" icon="play-circle-outline" onPress={() => router.push('/samples')} />
          </>
        ) : null}
        {list.map((p) => (
          <Card key={p.id} onPress={() => router.push(next === 'hospital' ? `/hospital/${p.id}` : `/policies/${p.id}`)} style={{ gap: 10 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
              <IconBubble name="shield-checkmark" />
              <View style={{ flex: 1 }}>
                <Text style={{ fontWeight: '700', fontSize: 16, color: C.text }}>{p.plan}</Text>
                <Text style={{ color: C.sub, fontSize: 13 }}>{p.insurer}</Text>
              </View>
              <Ionicons name="chevron-forward" size={20} color={C.text} />
            </View>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
              <View>
                <Text style={{ color: C.sub, fontSize: 12 }}>Cover</Text>
                <Text style={{ fontWeight: '700' }}>{rupees(p.sum_insured)}</Text>
              </View>
              <View>
                <Text style={{ color: C.sub, fontSize: 12 }}>Members</Text>
                <Text style={{ fontWeight: '700' }}>{p.members.map((m: any) => m.name.split(' ')[0]).join(', ')}</Text>
              </View>
              <View style={{ alignItems: 'flex-end' }}>
                <Text style={{ color: C.sub, fontSize: 12 }}>Source</Text>
                <Pill text={{ paytm: 'Bought on Paytm', upload: 'Uploaded', sample: 'Sample', insurer_fetch: 'From insurer' }[p.source as string] ?? p.source} tone={p.source === 'paytm' ? 'info' : 'muted'} />
              </View>
            </View>
            {p.needs_review?.length ? <Pill text={`${p.needs_review.length} details to confirm`} tone="warn" /> : null}
          </Card>
        ))}
      </Screen>
    </View>
  );
}
