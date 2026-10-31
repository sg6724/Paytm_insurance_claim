import { router } from 'expo-router';
import { Text, View } from 'react-native';

import { JOURNEY, KEEP_READY } from '@/lib/guide';
import { C } from '@/lib/theme';
import { Btn, Card, Header, Screen, Section } from '@/ui/kit';

const GO: { label: string; to: string }[] = [
  { label: 'Add a policy', to: '/policies/add' },
  { label: "I'm in hospital", to: '/policies?next=hospital' },
  { label: 'Start a claim', to: '/policies' },
  { label: 'My claims', to: '/claims' },
];

/** The same four steps as onboarding, reachable from Help on any screen. */
export default function Guide() {
  return (
    <View style={{ flex: 1 }}>
      <Header title="How Claimezy works" sub="" right={<View />} />
      <Screen>
        <Text style={{ color: C.sub, lineHeight: 21 }}>Four steps from hospital to money in your account. Start at the one you need today.</Text>
        {JOURNEY.map((s, n) => (
          <Card key={s.title} style={{ gap: 8 }}>
            <View style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
              <View style={{ width: 28, height: 28, borderRadius: 14, backgroundColor: C.navy, alignItems: 'center', justifyContent: 'center' }}>
                <Text style={{ color: '#fff', fontWeight: '800' }}>{n + 1}</Text>
              </View>
              <Text style={{ fontWeight: '700', fontSize: 16, flex: 1 }}>{s.title}</Text>
            </View>
            <Text style={{ color: C.sub, lineHeight: 20 }}>{s.how}</Text>
            <Btn title={GO[n].label} kind="secondary" style={{ height: 42 }} onPress={() => router.push(GO[n].to as any)} />
          </Card>
        ))}
        <Section title="Keep these ready">
          <Card style={{ gap: 8 }}>
            {KEEP_READY.map((k) => (
              <Text key={k} style={{ color: C.text }}>• {k}</Text>
            ))}
          </Card>
        </Section>
        <Section title="Just exploring?">
          <Btn title="Try a sample claim" icon="play-circle-outline" onPress={() => router.push('/samples')} />
        </Section>
        <Text style={{ color: C.faint, fontSize: 12, textAlign: 'center' }}>Stuck anywhere? Tap the assistant button and ask in your language.</Text>
      </Screen>
    </View>
  );
}
