import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';

import { useApp } from '@/lib/app-context';
import { C } from '@/lib/theme';
import { Btn, Card, Header, Screen } from '@/ui/kit';

export default function Settings() {
  const { user, signOut, langs, lang, setLang, translating } = useApp();
  return (
    <View style={{ flex: 1 }}>
      <Header title="Account and language" />
      <Screen>
        <Card style={{ gap: 4 }}>
          <Text style={{ fontWeight: '700', fontSize: 16, color: C.text }}>{user?.name}</Text>
          <Text style={{ color: C.sub }}>{user?.email}</Text>
          <Btn title="Sign out" kind="ghost" icon="log-out-outline" style={{ marginTop: 10, height: 42 }} onPress={signOut} />
        </Card>
        <Text style={{ color: C.sub }}>Explanations, letters and the assistant use this language. Voice playback is available for languages marked with a speaker.</Text>
        {translating ? (
          <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
            <ActivityIndicator color={C.navy} />
            <Text style={{ color: C.navy }}>Translating the app with Sarvam…</Text>
          </View>
        ) : null}
        <Card style={{ paddingVertical: 4 }}>
          {langs.map((l) => (
            <Pressable
              key={l.code}
              onPress={async () => {
                await setLang(l.code);
                router.back();
              }}
              style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 13, borderBottomWidth: 1, borderBottomColor: C.line, gap: 12 }}>
              <Text style={{ fontSize: 16, fontWeight: '600', color: C.text, flex: 1 }}>
                {l.native} <Text style={{ color: C.sub, fontWeight: '400', fontSize: 14 }}>· {l.name}</Text>
              </Text>
              {l.tts ? <Ionicons name="volume-medium-outline" size={18} color={C.sub} /> : null}
              {l.code === lang ? <Ionicons name="checkmark-circle" size={22} color={C.green} /> : null}
            </Pressable>
          ))}
        </Card>
      </Screen>
    </View>
  );
}
