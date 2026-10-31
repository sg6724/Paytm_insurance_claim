import { router } from 'expo-router';
import { useState } from 'react';
import { Text, View } from 'react-native';

import { get, send } from '@/lib/api';
import { C } from '@/lib/theme';
import { Card, Header, IconBubble, Loading, Pill, Screen, useAsync } from '@/ui/kit';

const STORY: Record<string, { tone: 'warn' | 'ok' | 'bad'; tag: string; line: string }> = {
  sunita_gallbladder: { tone: 'warn', tag: 'Room above limit', line: 'Gallbladder surgery in a ₹7,500/day room on a ₹5,000/day policy limit. See the deduction coming, file, then fight a wrong cut.' },
  arjun_dengue: { tone: 'ok', tag: 'Clean claim', line: 'Dengue, 4 days. Policy bought on Paytm with no room cap. Full payout, plus a bridge loan while you wait.' },
  rakesh_knee: { tone: 'bad', tag: 'Waiting period', line: 'Knee replacement 14 months into the policy. See why it is rejected, the honest appeal odds, and options to pay the bill.' },
};

export default function Samples() {
  const q = useAsync(() => get<any[]>('/samples'));
  const [busy, setBusy] = useState<string | null>(null);
  return (
    <View style={{ flex: 1 }}>
      <Header title="Try a sample claim" sub="" />
      <Screen>
        <Text style={{ color: C.sub }}>Sample policies and hospital documents are made up for the demo. Everything else works exactly as it would for you.</Text>
        {q.loading ? <Loading /> : null}
        {(q.data ?? []).map((s) => (
          <Card
            key={s.key}
            style={{ gap: 8 }}
            onPress={async () => {
              setBusy(s.key);
              try {
                const p = await send(`/samples/${s.key}/policy`);
                router.replace(`/policies/${p.id}?sample=${s.key}`);
              } finally {
                setBusy(null);
              }
            }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <IconBubble name="person" />
              <View style={{ flex: 1 }}>
                <Text style={{ fontWeight: '700', fontSize: 16 }}>{s.member}</Text>
                <Text style={{ color: C.sub, fontSize: 13 }}>{s.title}</Text>
              </View>
              <Pill text={STORY[s.key]?.tag ?? ''} tone={STORY[s.key]?.tone} />
            </View>
            <Text style={{ color: C.text }}>{STORY[s.key]?.line}</Text>
            {busy === s.key ? <Loading label="Setting up…" /> : null}
          </Card>
        ))}
      </Screen>
    </View>
  );
}
