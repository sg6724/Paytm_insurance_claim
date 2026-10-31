import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { send } from '@/lib/api';
import { JOURNEY, KEEP_READY } from '@/lib/guide';
import { C } from '@/lib/theme';
import { Btn, IconBubble, PaytmLogo, type IconName } from '@/ui/kit';

type Slide = { icon: IconName; title: string; body: string; points?: string[]; steps?: boolean; ready?: boolean; consent?: boolean };

const SLIDES: Slide[] = [
  {
    icon: 'shield-checkmark',
    title: 'Your health claim, start to finish',
    body: 'Claim-to-Cash helps after you buy a policy: when you or your family is in hospital and you need the insurer to pay.',
    points: ['Understand what your policy really covers', 'Spot costly deductions before you leave the hospital', 'File the claim right the first time and track it until you are paid'],
  },
  {
    icon: 'footsteps',
    title: 'How it works: 4 steps',
    body: 'You can do them in order, or jump in at the step you need today.',
    steps: true,
  },
  {
    icon: 'folder-open',
    title: 'What to keep ready',
    body: 'You do not need everything at once. Add things as you get them.',
    points: KEEP_READY,
    ready: true,
  },
  {
    icon: 'git-compare',
    title: 'AI explains. Rules decide.',
    body: 'Every rupee figure comes from your policy rules, never from an AI guess.',
    points: ['AI reads your papers and explains in your language, by text or voice', 'A rule engine works out what is payable', 'The insurer decides your claim. You stay in control'],
  },
  {
    icon: 'lock-closed',
    title: 'Your data, your consent',
    body: 'We only use your documents for your claim.',
    points: ['Nothing goes to your insurer until you tap Submit', 'See everything AI did under Privacy & AI activity', 'Withdraw consent or delete your data any time'],
    consent: true,
  },
];

export default function Onboarding() {
  const insets = useSafeAreaInsets();
  const [i, setI] = useState(0);
  const [consent, setConsent] = useState(true);
  const slide = SLIDES[i];
  const last = i === SLIDES.length - 1;

  async function finish(to: '/insurance' | '/samples' | '/policies/add' = '/insurance') {
    if (consent) await send('/consents/all?granted=true').catch(() => {});
    await send('/profile', { onboarded: true }, 'PATCH').catch(() => {});
    router.replace(to);
  }

  return (
    <View style={{ flex: 1, backgroundColor: '#fff', paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16, paddingHorizontal: 22 }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <PaytmLogo sub="Insurance Broking" />
        {last ? null : (
          <Pressable onPress={() => setI(SLIDES.length - 1)} hitSlop={10}>
            <Text style={{ color: C.sub, fontWeight: '600' }}>Skip</Text>
          </Pressable>
        )}
      </View>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ flexGrow: 1, justifyContent: 'center', gap: 16, paddingVertical: 12 }} showsVerticalScrollIndicator={false}>
        <IconBubble name={slide.icon} size={72} bg={C.skySoft} />
        <Text style={{ fontSize: 26, fontWeight: '800', color: C.text, lineHeight: 32 }}>{slide.title}</Text>
        <Text style={{ fontSize: 15, color: C.sub, lineHeight: 22 }}>{slide.body}</Text>

        {slide.steps ? (
          <View style={{ gap: 14, marginTop: 4 }}>
            {JOURNEY.map((s, n) => (
              <View key={s.title} style={{ flexDirection: 'row', gap: 12, alignItems: 'flex-start' }}>
                <View style={{ width: 28, height: 28, borderRadius: 14, backgroundColor: C.navy, alignItems: 'center', justifyContent: 'center' }}>
                  <Text style={{ color: '#fff', fontWeight: '800' }}>{n + 1}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={{ fontWeight: '700', fontSize: 15, color: C.text }}>{s.title}</Text>
                  <Text style={{ color: C.sub, fontSize: 13, lineHeight: 19 }}>{s.how}</Text>
                </View>
              </View>
            ))}
          </View>
        ) : (
          <View style={{ gap: 12, marginTop: 4 }}>
            {slide.points?.map((p) => (
              <View key={p} style={{ flexDirection: 'row', gap: 10, alignItems: 'flex-start' }}>
                <Ionicons name="checkmark-circle" size={20} color={C.green} />
                <Text style={{ fontSize: 15, color: C.text, flex: 1 }}>{p}</Text>
              </View>
            ))}
          </View>
        )}

        {slide.ready ? (
          <View style={{ backgroundColor: C.paleBlue, padding: 14, borderRadius: 12, flexDirection: 'row', gap: 10 }}>
            <Ionicons name="play-circle" size={22} color={C.navy} />
            <Text style={{ flex: 1, color: C.text, fontSize: 13 }}>No papers with you? You can walk through a full sample claim first. Nothing real is sent anywhere.</Text>
          </View>
        ) : null}

        {slide.consent ? (
          <Pressable onPress={() => setConsent((c) => !c)} style={{ flexDirection: 'row', gap: 10, backgroundColor: C.paleBlue, padding: 14, borderRadius: 12 }}>
            <Ionicons name={consent ? 'checkbox' : 'square-outline'} size={22} color={C.navy} />
            <Text style={{ flex: 1, color: C.text, fontSize: 13 }}>
              I agree that Claim-to-Cash may read my documents, use AI (Sarvam, hosted in India) to explain and draft, and share my claim with my insurer when I tap Submit. (DPDP Act, 2023)
            </Text>
          </Pressable>
        ) : null}
      </ScrollView>

      <View style={{ flexDirection: 'row', justifyContent: 'center', gap: 6, marginVertical: 14 }}>
        {SLIDES.map((_, k) => (
          <View key={k} style={{ width: k === i ? 22 : 8, height: 8, borderRadius: 4, backgroundColor: k === i ? C.navy : C.line }} />
        ))}
      </View>

      {last ? (
        <View style={{ gap: 10 }}>
          <Btn title="Try a sample claim" icon="play-circle-outline" onPress={() => finish('/samples')} />
          <Btn title="Add my own policy" kind="secondary" icon="add" onPress={() => finish('/policies/add')} />
        </View>
      ) : (
        <View style={{ flexDirection: 'row', gap: 10 }}>
          {i > 0 ? <Btn title="Back" kind="secondary" style={{ flex: 1 }} onPress={() => setI(i - 1)} /> : null}
          <Btn title="Next" style={{ flex: 2 }} onPress={() => setI(i + 1)} />
        </View>
      )}
    </View>
  );
}
