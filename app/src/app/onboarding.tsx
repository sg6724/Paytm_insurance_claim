import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { send } from '@/lib/api';
import { C } from '@/lib/theme';
import { Btn, IconBubble, PaytmLogo, type IconName } from '@/ui/kit';

const SLIDES: { icon: IconName; title: string; body: string; points: string[] }[] = [
  {
    icon: 'shield-checkmark',
    title: 'From hospital bill to money in hand',
    body: 'Claim-to-Cash stays with you from admission to settlement.',
    points: ['Understand your policy in plain words', 'Catch costly mistakes before discharge', 'File right the first time, then track it'],
  },
  {
    icon: 'git-compare',
    title: 'AI explains. Rules decide.',
    body: 'Every rupee figure comes from your policy rules, never from a guess.',
    points: ['AI reads your documents and explains in your language', 'A rule engine calculates what is payable', 'The insurer decides your claim. You stay in control'],
  },
  {
    icon: 'lock-closed',
    title: 'Your data, your consent',
    body: 'We only use your documents for your claim.',
    points: ['You choose what we can read and share', 'See everything AI did in Privacy & AI activity', 'Delete your data any time'],
  },
];

export default function Onboarding() {
  const insets = useSafeAreaInsets();
  const [i, setI] = useState(0);
  const [consent, setConsent] = useState(true);
  const slide = SLIDES[i];
  const last = i === SLIDES.length - 1;

  async function finish() {
    if (consent) await send('/consents/all?granted=true').catch(() => {});
    await send('/profile', { onboarded: true }, 'PATCH').catch(() => {});
    router.replace('/insurance');
  }

  return (
    <View style={{ flex: 1, backgroundColor: '#fff', paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16, paddingHorizontal: 22 }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <PaytmLogo sub="Insurance Broking" />
        <Pressable onPress={finish} hitSlop={10}>
          <Text style={{ color: C.sub, fontWeight: '600' }}>Skip</Text>
        </Pressable>
      </View>
      <View style={{ flex: 1, justifyContent: 'center', gap: 18 }}>
        <IconBubble name={slide.icon} size={84} bg={C.skySoft} />
        <Text style={{ fontSize: 28, fontWeight: '800', color: C.text, lineHeight: 34 }}>{slide.title}</Text>
        <Text style={{ fontSize: 16, color: C.sub }}>{slide.body}</Text>
        <View style={{ gap: 12, marginTop: 6 }}>
          {slide.points.map((p) => (
            <View key={p} style={{ flexDirection: 'row', gap: 10, alignItems: 'flex-start' }}>
              <Ionicons name="checkmark-circle" size={20} color={C.green} />
              <Text style={{ fontSize: 15, color: C.text, flex: 1 }}>{p}</Text>
            </View>
          ))}
        </View>
        {last ? (
          <Pressable onPress={() => setConsent((c) => !c)} style={{ flexDirection: 'row', gap: 10, backgroundColor: C.paleBlue, padding: 14, borderRadius: 12, marginTop: 8 }}>
            <Ionicons name={consent ? 'checkbox' : 'square-outline'} size={22} color={C.navy} />
            <Text style={{ flex: 1, color: C.text, fontSize: 13 }}>
              I agree that Claim-to-Cash may read my documents, use AI (Sarvam, hosted in India) to explain and draft, and share my claim with my insurer when I tap Submit. (DPDP Act, 2023)
            </Text>
          </Pressable>
        ) : null}
      </View>
      <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 6, marginBottom: 16 }}>
        {SLIDES.map((_, k) => (
          <View key={k} style={{ width: k === i ? 22 : 8, height: 8, borderRadius: 4, backgroundColor: k === i ? C.navy : C.line }} />
        ))}
      </View>
      <Btn title={last ? 'Get started' : 'Next'} onPress={() => (last ? finish() : setI(i + 1))} />
    </View>
  );
}
