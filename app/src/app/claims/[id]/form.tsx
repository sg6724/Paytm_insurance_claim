import Ionicons from '@expo/vector-icons/Ionicons';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { Pressable, Switch, Text, View } from 'react-native';

import { get, send } from '@/lib/api';
import { useApp } from '@/lib/app-context';
import { C } from '@/lib/theme';
import { Btn, Card, Field, Header, Loading, Pill, Screen, Section } from '@/ui/kit';
import { Tip } from '@/ui/tip';

type Correction = { field: string; severity: 'error' | 'warning' | 'info' | 'required'; message: string; suggestion?: any };

const GROUPS: { title: string; fields: [string, string, any?][] }[] = [
  { title: 'Policy & patient', fields: [['policy_number', 'Policy number', { autoCapitalize: 'characters' }], ['member_id', 'Patient']] },
  {
    title: 'Hospital stay',
    fields: [
      ['hospital_name', 'Hospital name'],
      ['admission_date', 'Date of admission', { placeholder: 'YYYY-MM-DD' }],
      ['discharge_date', 'Date of discharge', { placeholder: 'YYYY-MM-DD' }],
      ['diagnosis', 'Diagnosis'],
      ['procedure', 'Treatment / procedure'],
      ['room_category', 'Room category'],
      ['room_rent_per_day', 'Room rent per day (₹)', { keyboardType: 'numeric' }],
      ['room_days', 'Days in room', { keyboardType: 'numeric' }],
      ['total_claimed', 'Total amount claimed (₹)', { keyboardType: 'numeric' }],
    ],
  },
  { title: 'Bank account for payout', fields: [['account_name', 'Account holder name'], ['account_number', 'Account number', { keyboardType: 'numeric' }], ['ifsc', 'IFSC code', { autoCapitalize: 'characters' }]] },
  { title: 'Contact', fields: [['mobile', 'Mobile number', { keyboardType: 'phone-pad' }], ['email', 'Email', { keyboardType: 'email-address', autoCapitalize: 'none' }], ['pincode', 'PIN code', { keyboardType: 'numeric' }]] },
];

const ROOMS = [['general_ward', 'General ward'], ['twin_sharing', 'Twin sharing'], ['single_private', 'Single private'], ['deluxe', 'Deluxe']];

export default function ClaimForm() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t, setAssistantCtx } = useApp();
  const [claim, setClaim] = useState<any>(null);
  const [form, setForm] = useState<Record<string, any>>({});
  const [corr, setCorr] = useState<Correction[]>([]);
  const [kept, setKept] = useState<Record<string, boolean>>({});
  const [checking, setChecking] = useState(false);
  const [pending, setPending] = useState<Record<string, any> | null>(null);

  useFocusEffect(useCallback(() => setAssistantCtx({ screen: 'claim_form', claim_id: id }), [id, setAssistantCtx]));

  useEffect(() => {
    get(`/claims/${id}`).then((c) => {
      setClaim(c);
      setForm(c.form ?? {});
      send(`/claims/${id}/validate`, { form: c.form ?? {} }).then((r) => setCorr(r.corrections));
    });
  }, [id]);

  // Live checks: re-validate 450 ms after the user stops typing.
  useEffect(() => {
    if (!pending) return;
    const h = setTimeout(async () => {
      setChecking(true);
      try {
        const r = await send(`/claims/${id}/validate`, { form: pending });
        setCorr(r.corrections);
      } finally {
        setChecking(false);
      }
    }, 450);
    return () => clearTimeout(h);
  }, [pending, id]);

  function update(k: string, v: any) {
    const next = { ...form, [k]: v };
    setForm(next);
    setKept((x) => ({ ...x, [k]: false }));
    setPending(next);
  }

  async function switchMode(mode: 'ai' | 'manual') {
    const r = await send(`/claims/${id}/fill-mode`, { mode });
    setClaim({ ...claim, fill_mode: mode, form_sources: r.sources });
    if (mode === 'ai') setForm(r.form);
    setCorr(r.corrections);
  }

  if (!claim) return (<View style={{ flex: 1 }}><Header sub="" /><Loading /></View>);
  const sources = claim.fill_mode === 'ai' ? claim.form_sources ?? {} : {};
  const blocking = corr.filter((c) => (c.severity === 'error' || c.severity === 'required') && !kept[c.field]);
  const members = claim.policy?.members ?? [];

  function hintFor(field: string) {
    const list = corr.filter((c) => c.field === field && !(kept[field] && c.severity !== 'required'));
    if (!list.length) return undefined;
    return (
      <View style={{ gap: 6 }}>
        {list.map((c, i) => (
          <View key={i} style={{ backgroundColor: c.severity === 'error' ? C.redSoft : c.severity === 'warning' ? C.amberSoft : c.severity === 'required' ? '#F2F4F7' : C.skySoft, borderRadius: 10, padding: 10, gap: 6 }}>
            <View style={{ flexDirection: 'row', gap: 6 }}>
              <Ionicons name={c.severity === 'error' ? 'alert-circle' : c.severity === 'warning' ? 'warning' : 'information-circle'} size={16} color={c.severity === 'error' ? C.red : c.severity === 'warning' ? C.amber : C.navy} />
              <Text style={{ flex: 1, color: C.text, fontSize: 13 }}>{c.message}</Text>
            </View>
            {c.suggestion !== null && c.suggestion !== undefined ? (
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <Pressable onPress={() => update(field, typeof c.suggestion === 'number' ? String(c.suggestion) : c.suggestion)} style={{ backgroundColor: C.navy, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 99 }}>
                  <Text style={{ color: '#fff', fontWeight: '700', fontSize: 12 }}>Fix: use {String(c.suggestion)}</Text>
                </Pressable>
                <Pressable onPress={() => setKept({ ...kept, [field]: true })} style={{ paddingHorizontal: 12, paddingVertical: 6 }}>
                  <Text style={{ color: C.navy, fontWeight: '600', fontSize: 12 }}>Keep mine</Text>
                </Pressable>
              </View>
            ) : null}
          </View>
        ))}
      </View>
    );
  }

  return (
    <View style={{ flex: 1 }}>
      <Header title={t('claimForm')} sub="" />
      <Screen
        footer={
          <>
            {blocking.length ? <Text style={{ color: C.red, fontSize: 12, textAlign: 'center' }}>{blocking.length} field{blocking.length > 1 ? 's' : ''} need attention before you submit</Text> : null}
            <Btn
              title={t('checkPayout')}
              icon="calculator-outline"
              onPress={async () => {
                await send(`/claims/${id}/validate`, { form });
                router.push(`/claims/${id}/preflight`);
              }}
            />
          </>
        }>
        <Tip id="form" text="Fields we filled show where the value came from. Fix anything that looks wrong; warnings update as you type, and you can switch to filling it yourself any time." />
        <Card style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <Ionicons name={claim.fill_mode === 'ai' ? 'sparkles' : 'create-outline'} size={20} color={C.navy} />
          <View style={{ flex: 1 }}>
            <Text style={{ fontWeight: '700' }}>{claim.fill_mode === 'ai' ? 'Filled from your documents' : 'You are filling this form'}</Text>
            <Text style={{ color: C.sub, fontSize: 12 }}>{claim.fill_mode === 'ai' ? 'Check each field. Tagged fields came from a document.' : 'We check each field as you type and suggest fixes.'}</Text>
          </View>
          <Pressable onPress={() => switchMode(claim.fill_mode === 'ai' ? 'manual' : 'ai')}>
            <Text style={{ color: C.sky, fontWeight: '700', fontSize: 13 }}>{claim.fill_mode === 'ai' ? 'Fill myself' : 'Fill for me'}</Text>
          </Pressable>
        </Card>
        {checking ? <Pill text="Checking…" tone="muted" /> : corr.length === 0 ? <Pill text="Everything looks right" tone="ok" /> : null}

        {GROUPS.map((g) => (
          <Section key={g.title} title={g.title}>
            <Card style={{ gap: 14 }}>
              {g.fields.map(([k, label, props]) => {
                if (k === 'member_id')
                  return (
                    <View key={k} style={{ gap: 6 }}>
                      <Text style={{ fontSize: 13, color: C.sub, fontWeight: '600' }}>{label}</Text>
                      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                        {members.map((m: any) => (
                          <Pressable key={m.id} onPress={() => update('member_id', m.id)} style={{ paddingHorizontal: 12, paddingVertical: 8, borderRadius: 99, borderWidth: 1.5, borderColor: form.member_id === m.id ? C.navy : C.line, backgroundColor: form.member_id === m.id ? C.skySoft : '#fff' }}>
                            <Text style={{ fontWeight: '600', color: C.text }}>{m.name}</Text>
                          </Pressable>
                        ))}
                      </View>
                      {hintFor(k)}
                    </View>
                  );
                if (k === 'room_category')
                  return (
                    <View key={k} style={{ gap: 6 }}>
                      <Text style={{ fontSize: 13, color: C.sub, fontWeight: '600' }}>{label}</Text>
                      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                        {ROOMS.map(([v, l]) => (
                          <Pressable key={v} onPress={() => update(k, v)} style={{ paddingHorizontal: 12, paddingVertical: 8, borderRadius: 99, borderWidth: 1.5, borderColor: form[k] === v ? C.navy : C.line, backgroundColor: form[k] === v ? C.skySoft : '#fff' }}>
                            <Text style={{ color: C.text }}>{l}</Text>
                          </Pressable>
                        ))}
                      </View>
                    </View>
                  );
                const tone = corr.find((c) => c.field === k && !kept[k])?.severity;
                return (
                  <Field key={k} label={label} value={form[k] === undefined || form[k] === null ? '' : String(form[k])} onChangeText={(v) => update(k, v)} source={sources[k]} tone={tone} hint={hintFor(k)} {...(props ?? {})} />
                );
              })}
            </Card>
          </Section>
        ))}
        <Card style={{ gap: 12 }}>
          {[
            ['is_accident', 'Was this due to an accident?'],
            ['intimation_done', 'Have you informed the insurer?'],
          ].map(([k, label]) => (
            <View key={k} style={{ gap: 6 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                <Text style={{ flex: 1, fontWeight: '600' }}>{label}</Text>
                <Switch value={!!form[k]} onValueChange={(v) => update(k, v)} trackColor={{ true: C.sky }} />
              </View>
              {k === 'intimation_done' && !form[k] ? (
                <Btn title="Inform insurer now" kind="secondary" icon="call-outline" style={{ height: 42 }} onPress={async () => { await send(`/claims/${id}/intimate`); update('intimation_done', true); }} />
              ) : null}
              {hintFor(k)}
            </View>
          ))}
        </Card>
        {hintFor('diagnosis') ? null : null}
      </Screen>
    </View>
  );
}
