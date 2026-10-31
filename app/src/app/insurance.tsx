import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Text, View } from 'react-native';

import { get } from '@/lib/api';
import { useApp } from '@/lib/app-context';
import { C } from '@/lib/theme';
import { Btn, Card, Header, Pill, Row, Screen } from '@/ui/kit';

/** Paytm Insurance landing, extended with the post-purchase journey that is missing today. */
export default function Insurance() {
  const { t, setAssistantCtx } = useApp();
  const [counts, setCounts] = useState<{ policies: number; claims: number; open: any | null; onlyPolicy: string | null }>({ policies: 0, claims: 0, open: null, onlyPolicy: null });

  useFocusEffect(
    useCallback(() => {
      setAssistantCtx({ screen: 'insurance_home' });
      (async () => {
        try {
          const prof = await get('/profile');
          if (!prof.onboarded) {
            router.push('/onboarding');
            return;
          }
          const [p, c] = await Promise.all([get<any[]>('/policies'), get<any[]>('/claims')]);
          const open = c.find((x) => !['settled', 'draft'].includes(x.status)) ?? null;
          setCounts({ policies: p.length, claims: c.length, open, onlyPolicy: p.length === 1 ? p[0].id : null });
        } catch {}
      })();
    }, [setAssistantCtx]),
  );

  return (
    <View style={{ flex: 1 }}>
      <Header />
      <Screen>
        <View style={{ backgroundColor: C.paleBlue, borderRadius: 16, padding: 18, gap: 10 }}>
          <Text style={{ fontSize: 26, fontWeight: '400', color: C.text, lineHeight: 32 }}>
            Your health cover,{'\n'}
            <Text style={{ backgroundColor: C.highlight, fontWeight: '800' }}> claimed right. </Text>
          </Text>
          <View style={{ gap: 6 }}>
            <Text style={{ color: C.text }}>
              <Ionicons name="sparkles-outline" size={14} /> Policy explained in your language
            </Text>
            <Text style={{ color: C.text }}>
              <Ionicons name="calculator-outline" size={14} /> Know your payout before you file
            </Text>
            <Text style={{ color: C.text }}>
              <Ionicons name="shield-checkmark-outline" size={14} /> Help with deductions and rejections
            </Text>
          </View>
        </View>

        {counts.open ? (
          <Card onPress={() => router.push(`/claims/${counts.open.id}`)} style={{ borderColor: C.sky, borderWidth: 1.5 }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text style={{ fontWeight: '700', fontSize: 15 }}>Claim in progress</Text>
              <Pill text={counts.open.status.replace(/_/g, ' ')} />
            </View>
            <Text style={{ color: C.sub, marginTop: 4 }}>
              {counts.open.policy?.plan} · {counts.open.timeline?.[counts.open.timeline.length - 1]?.title}
            </Text>
          </Card>
        ) : null}

        {counts.policies === 0 && counts.claims === 0 ? (
          <Card style={{ gap: 10 }}>
            <Text style={{ fontWeight: '700', fontSize: 16 }}>New here? Start with step 1</Text>
            <Text style={{ color: C.sub }}>Add the policy you already have, or walk through a full claim with a made-up policy and bill. Nothing real is sent anywhere.</Text>
            <Btn title="Add my policy" icon="add" onPress={() => router.push('/policies/add')} />
            <Btn title={t('trySample')} kind="secondary" icon="play-circle-outline" onPress={() => router.push('/samples')} />
            <Text style={{ color: C.faint, fontSize: 12, textAlign: 'center' }}>Tap Help at the top right any time to see the 4 steps.</Text>
          </Card>
        ) : null}

        <Card>
          <Row icon="document-text-outline" title={t('myPolicies')} sub={counts.policies ? `${counts.policies} added` : 'Add the policy you already have'} onPress={() => router.push('/policies')} />
          <Row icon="medkit-outline" title={t('imInHospital')} sub={t('imInHospitalSub')} onPress={() => router.push(counts.onlyPolicy ? `/hospital/${counts.onlyPolicy}` : '/policies?next=hospital')} iconBg={C.redSoft} iconColor={C.red} />
          <Row icon="receipt-outline" title={t('myClaims')} sub={counts.claims ? `${counts.claims} claim${counts.claims > 1 ? 's' : ''}` : 'File and track claims'} onPress={() => router.push('/claims')} />
          <Row icon="lock-closed-outline" title={t('privacy')} sub="Consents and everything AI did with your data" onPress={() => router.push('/trust')} />
        </Card>

        <Text style={{ textAlign: 'center', color: C.faint, fontSize: 11 }}>Paytm Insurance Broking Pvt Ltd · Claims assistance as a licensed broker (demo)</Text>
      </Screen>
    </View>
  );
}
