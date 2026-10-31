import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, Switch, Text, View } from 'react-native';

import { fmtTime, get, send } from '@/lib/api';
import { C } from '@/lib/theme';
import { act, Btn, Card, Header, Loading, Screen, Section, Sheet, useAsync } from '@/ui/kit';

const ACTOR = { ai: { icon: 'sparkles', color: C.navy, label: 'AI' }, rules: { icon: 'calculator', color: C.green, label: 'Rules' }, you: { icon: 'person', color: C.sub, label: 'You' } } as const;

export default function Trust() {
  const consents = useAsync(() => get<any[]>('/consents'));
  const audit = useAsync(() => get<any[]>('/audit'));
  const [confirm, setConfirm] = useState(false);

  return (
    <View style={{ flex: 1 }}>
      <Header title="Privacy & AI activity" />
      <Screen>
        <Section title="Your consents">
          <Card style={{ paddingVertical: 6 }}>
            {consents.loading ? <Loading /> : null}
            {(consents.data ?? []).map((c) => (
              <View key={c.purpose} style={{ flexDirection: 'row', gap: 12, alignItems: 'center', paddingVertical: 10 }}>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontWeight: '600', color: C.text }}>{c.title}</Text>
                  <Text style={{ color: C.sub, fontSize: 13 }}>{c.detail}</Text>
                </View>
                <Switch
                  value={c.granted}
                  trackColor={{ true: C.sky }}
                  onValueChange={act(async (v: boolean) => consents.setData(await send('/consents', { purpose: c.purpose, granted: v })))}
                />
              </View>
            ))}
          </Card>
        </Section>
        <Section title="What AI did with your data">
          <Card style={{ gap: 12 }}>
            {audit.loading ? <Loading /> : null}
            {(audit.data ?? []).length === 0 && !audit.loading ? <Text style={{ color: C.sub }}>Nothing yet. Every AI action, consent and submission will be listed here.</Text> : null}
            {(audit.data ?? []).slice(0, 60).map((a) => {
              const k = ACTOR[a.actor as keyof typeof ACTOR] ?? ACTOR.you;
              return (
                <View key={a.id} style={{ flexDirection: 'row', gap: 10 }}>
                  <Ionicons name={k.icon as any} size={16} color={k.color} style={{ marginTop: 2 }} />
                  <View style={{ flex: 1 }}>
                    <Text style={{ color: C.text }}>{a.detail}</Text>
                    <Text style={{ color: C.faint, fontSize: 12 }}>
                      {k.label} · {fmtTime(a.created_at)}
                    </Text>
                  </View>
                </View>
              );
            })}
          </Card>
        </Section>
        <Btn title="Delete all my data" kind="ghost" icon="trash-outline" onPress={() => setConfirm(true)} />
      </Screen>
      <Sheet visible={confirm} onClose={() => setConfirm(false)} title="Delete everything?">
        <Text style={{ color: C.sub }}>Policies, claims, documents and chats will be deleted from Claimezy. Claims already with your insurer are not affected.</Text>
        <Btn
          title="Delete my data"
          kind="danger"
          onPress={act(async () => {
            await send('/me/data', undefined, 'DELETE');
            setConfirm(false);
            router.replace('/insurance');
          })}
        />
        <Pressable onPress={() => setConfirm(false)}>
          <Text style={{ textAlign: 'center', color: C.navy, fontWeight: '600', padding: 8 }}>Keep my data</Text>
        </Pressable>
      </Sheet>
    </View>
  );
}
