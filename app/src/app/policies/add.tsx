import * as DocumentPicker from 'expo-document-picker';
import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { useState } from 'react';
import { Text, View } from 'react-native';

import { get, rupees, send, upload } from '@/lib/api';
import { C } from '@/lib/theme';
import { Btn, Card, ErrorNote, Field, Header, Loading, Row, Screen, Sheet } from '@/ui/kit';

export default function AddPolicy() {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [paytm, setPaytm] = useState<any[] | null>(null);
  const [fetchOpen, setFetchOpen] = useState(false);
  const [insurer, setInsurer] = useState('');
  const [number, setNumber] = useState('');

  async function run(label: string, fn: () => Promise<any>) {
    setError(null);
    setBusy(label);
    try {
      const p = await fn();
      router.replace(`/policies/${p.id}`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  }

  async function pickPdf() {
    const r = await DocumentPicker.getDocumentAsync({ type: ['application/pdf', 'image/*'], copyToCacheDirectory: true });
    if (r.canceled) return;
    const a = r.assets[0];
    run('Reading your policy with Sarvam AI. This takes about 20 seconds…', () =>
      upload('/policies/upload', { uri: a.uri, name: a.name, type: a.mimeType ?? 'application/pdf' }),
    );
  }

  async function snap() {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) return setError('Allow camera access to photograph the policy schedule.');
    const r = await ImagePicker.launchCameraAsync({ quality: 0.7 });
    if (r.canceled) return;
    const a = r.assets[0];
    run('Reading your policy schedule…', () => upload('/policies/upload', { uri: a.uri, name: 'policy.jpg', type: a.mimeType ?? 'image/jpeg' }));
  }

  return (
    <View style={{ flex: 1 }}>
      <Header title="Add a policy" sub="" />
      <Screen>
        {busy ? (
          <Card>
            <Loading label={busy} />
          </Card>
        ) : null}
        {error ? <ErrorNote error={error} /> : null}
        <Card>
          <Row icon="phone-portrait-outline" title="Bought on Paytm" sub="Policies you bought through Paytm Insurance" onPress={async () => setPaytm(await get('/policies/paytm'))} />
          <Row icon="cloud-upload-outline" title="Upload policy PDF" sub="Policy schedule or wording. AI reads it in seconds" onPress={pickPdf} />
          <Row icon="camera-outline" title="Photograph the schedule" sub="Use your camera" onPress={snap} />
          <Row icon="search-outline" title="Fetch with policy number" sub="We look it up with your insurer" onPress={() => setFetchOpen(true)} />
        </Card>
        <Text style={{ color: C.sub, fontSize: 12, textAlign: 'center' }}>Your document is read only to explain your cover and help you claim. See Privacy & AI activity.</Text>
      </Screen>

      <Sheet visible={!!paytm} onClose={() => setPaytm(null)} title="Your policies on Paytm">
        {(paytm ?? []).map((p) => (
          <Card key={p.id} style={{ gap: 6 }}>
            <Text style={{ fontWeight: '700' }}>{p.plan}</Text>
            <Text style={{ color: C.sub }}>
              {p.insurer} · {rupees(p.sum_insured)} · {p.policy_number}
            </Text>
            <Btn title="Add this policy" onPress={() => { setPaytm(null); run('Adding…', () => send(`/policies/paytm/${p.id}`)); }} />
          </Card>
        ))}
      </Sheet>

      <Sheet visible={fetchOpen} onClose={() => setFetchOpen(false)} title="Fetch from insurer">
        <Field label="Insurer" value={insurer} onChangeText={setInsurer} placeholder="e.g. Suraksha General" />
        <Field label="Policy number" value={number} onChangeText={setNumber} placeholder="As on your e-card" autoCapitalize="characters" />
        <Text style={{ color: C.faint, fontSize: 12 }}>Demo: try SGI/HFS/2025/0048213</Text>
        <Btn title="Fetch policy" onPress={() => { setFetchOpen(false); run('Contacting insurer…', () => send('/policies/fetch', { insurer, policy_number: number })); }} disabled={!number} />
      </Sheet>
    </View>
  );
}
