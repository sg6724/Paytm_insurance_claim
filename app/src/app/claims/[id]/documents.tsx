import Ionicons from '@expo/vector-icons/Ionicons';
import * as DocumentPicker from 'expo-document-picker';
import * as ImagePicker from 'expo-image-picker';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { get, send, upload } from '@/lib/api';
import { useApp } from '@/lib/app-context';
import { C } from '@/lib/theme';
import { act, Btn, Card, ErrorNote, Header, IconBubble, Loading, Pill, Screen, Section, Sheet, useAsync } from '@/ui/kit';
import { Tip } from '@/ui/tip';

export default function Documents() {
  const { id, sample } = useLocalSearchParams<{ id: string; sample?: string }>();
  const { t, setAssistantCtx } = useApp();
  const claim = useAsync(() => get(`/claims/${id}`), [id]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ask, setAsk] = useState(false);

  useFocusEffect(useCallback(() => setAssistantCtx({ screen: 'claim_documents', claim_id: id }), [id, setAssistantCtx]));

  async function add(file: { uri: string; name: string; type: string }) {
    setError(null);
    setBusy(`Reading ${file.name}…`);
    try {
      await upload(`/claims/${id}/documents`, file);
      claim.reload();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  }

  async function camera() {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) return setError('Allow camera access to photograph documents.');
    const r = await ImagePicker.launchCameraAsync({ quality: 0.7 });
    if (!r.canceled) add({ uri: r.assets[0].uri, name: `photo_${Date.now()}.jpg`, type: r.assets[0].mimeType ?? 'image/jpeg' });
  }
  async function files() {
    const r = await DocumentPicker.getDocumentAsync({ type: ['application/pdf', 'image/*'], multiple: true, copyToCacheDirectory: true });
    if (r.canceled) return;
    for (const a of r.assets) await add({ uri: a.uri, name: a.name, type: a.mimeType ?? 'application/pdf' });
  }
  async function abha() {
    setError(null);
    setBusy('Fetching your records from ABHA…');
    try {
      await send(`/mock/abha/fetch/${id}`);
      claim.reload();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  }

  async function useSamples() {
    setBusy('Adding sample documents…');
    try {
      claim.setData(await send(`/samples/${sample}/documents/${id}`));
    } finally {
      setBusy(null);
    }
  }
  async function chooseMode(mode: 'ai' | 'manual') {
    setAsk(false);
    await send(`/claims/${id}/fill-mode`, { mode });
    router.push(`/claims/${id}/form`);
  }

  const c = claim.data;
  const docs = c?.documents ?? [];
  const done = (c?.checklist ?? []).filter((x: any) => x.done).length;

  return (
    <View style={{ flex: 1 }}>
      <Header title={t('documents')} sub="" />
      <Screen
        footer={
          <>
            <Btn title={docs.length ? t('continue') : 'Fill the form without documents'} onPress={act(() => (docs.length ? setAsk(true) : chooseMode('manual')))} />
          </>
        }>
        <Tip id="documents" text="Add the papers you have, as photos or files. We read each one, then you choose whether we fill the claim form for you." />
        {!c ? <Loading /> : null}
        {c ? (
          <Card style={{ gap: 4 }}>
            <Text style={{ color: C.sub, fontSize: 12 }}>{c.policy?.plan} · {c.claim_type === 'cashless' ? 'Cashless' : 'Reimbursement'}</Text>
            <Text style={{ fontWeight: '700', fontSize: 16 }}>{c.policy?.members?.find((m: any) => m.id === c.member_id)?.name}</Text>
          </Card>
        ) : null}
        <View style={{ flexDirection: 'row', gap: 10 }}>
          <Card onPress={camera} style={{ flex: 1, alignItems: 'center', gap: 6 }}>
            <IconBubble name="camera-outline" />
            <Text style={{ fontWeight: '600' }}>Take photo</Text>
          </Card>
          <Card onPress={files} style={{ flex: 1, alignItems: 'center', gap: 6 }}>
            <IconBubble name="folder-open-outline" />
            <Text style={{ fontWeight: '600' }}>Upload files</Text>
          </Card>
          <Card onPress={abha} style={{ flex: 1, alignItems: 'center', gap: 6 }}>
            <IconBubble name="finger-print-outline" />
            <Text style={{ fontWeight: '600' }}>From ABHA</Text>
          </Card>
        </View>
        {sample && docs.length === 0 ? <Btn title="Use sample documents" kind="secondary" icon="albums-outline" onPress={act(useSamples)} /> : null}
        {busy ? <Loading label={busy} /> : null}
        {error ? <ErrorNote error={error} /> : null}

        {c ? (
          <Section title={`Checklist · ${done}/${c.checklist.length}`}>
            <Card style={{ gap: 10 }}>
              {c.checklist.map((x: any) => (
                <View key={x.type} style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
                  <Ionicons name={x.done ? 'checkmark-circle' : 'ellipse-outline'} size={20} color={x.done ? C.green : C.faint} />
                  <Text style={{ flex: 1, color: x.done ? C.text : C.sub }}>{x.label}</Text>
                </View>
              ))}
            </Card>
          </Section>
        ) : null}

        {docs.length ? (
          <Section title="Read by AI">
            {docs.map((d: any) => (
              <Card key={d.id} style={{ gap: 6 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <Ionicons name="document-attach-outline" size={18} color={C.navy} />
                  <Text style={{ fontWeight: '600', flex: 1 }} numberOfLines={1}>{d.filename}</Text>
                  <Pill text={(d.doc_type || 'other').replace(/_/g, ' ')} tone={d.doc_type === 'other' ? 'warn' : 'info'} />
                </View>
                <Text style={{ color: C.sub, fontSize: 13 }}>{d.fields?.summary}</Text>
                {d.review_ticket ? (
                  <Pill text={`Not sure we read this right. A person will check it (${d.review_ticket})`} tone="warn" />
                ) : null}
                <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                  <Text style={{ color: C.faint, fontSize: 12 }}>Confidence {Math.round((d.confidence || 0) * 100)}%</Text>
                  <Pressable onPress={act(async () => { await send(`/documents/${d.id}`, undefined, 'DELETE'); claim.reload(); })}>
                    <Text style={{ color: C.red, fontSize: 12 }}>Remove</Text>
                  </Pressable>
                </View>
              </Card>
            ))}
          </Section>
        ) : null}
      </Screen>

      <Sheet visible={ask} onClose={() => setAsk(false)}>
        <View style={{ alignItems: 'center', gap: 10 }}>
          <IconBubble name="sparkles" size={56} />
          <Text style={{ fontSize: 20, fontWeight: '800', textAlign: 'center', color: C.text }}>{t('fillQuestion')}</Text>
          <Text style={{ color: C.sub, textAlign: 'center' }}>{t('fillQuestionSub')}</Text>
        </View>
        <Btn title={t('fillForMe')} icon="sparkles" onPress={act(() => chooseMode('ai'))} />
        <Btn title={t('fillMyself')} kind="ghost" icon="create-outline" onPress={act(() => chooseMode('manual'))} />
        <Text style={{ color: C.faint, fontSize: 11, textAlign: 'center' }}>Your choice is recorded in Privacy & AI activity.</Text>
      </Sheet>
    </View>
  );
}
