import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useApp } from '@/lib/app-context';
import { C } from '@/lib/theme';
import { Btn, ErrorNote, Field, PaytmLogo } from '@/ui/kit';

export default function Login() {
  const insets = useSafeAreaInsets();
  const { signIn, signUp } = useApp();
  const [mode, setMode] = useState<'in' | 'up'>('in');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const creating = mode === 'up';

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      if (creating) await signUp(name.trim(), email.trim(), password);
      else await signIn(email.trim(), password);
    } catch (e: any) {
      setError(e?.message ?? 'Something went wrong. Try again.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: '#fff' }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
      <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: 'center', padding: 22, paddingTop: insets.top + 22, paddingBottom: insets.bottom + 22, gap: 14 }} keyboardShouldPersistTaps="handled">
        <View style={{ alignItems: 'flex-start', marginBottom: 6 }}>
          <PaytmLogo size={30} sub="Insurance Broking" />
        </View>
        <Text style={{ fontSize: 26, fontWeight: '800', color: C.text }}>{creating ? 'Create your account' : 'Sign in to Claimezy'}</Text>
        <Text style={{ color: C.sub, lineHeight: 21 }}>Your policies, claims and chats are saved to your account, so they are here whenever you come back.</Text>
        {creating ? <Field label="Your name" value={name} onChangeText={setName} autoComplete="name" textContentType="name" /> : null}
        <Field label="Email" value={email} onChangeText={setEmail} autoCapitalize="none" autoCorrect={false} autoComplete="email" keyboardType="email-address" textContentType="emailAddress" />
        <Field label="Password" value={password} onChangeText={setPassword} secureTextEntry autoCapitalize="none" autoComplete={creating ? 'new-password' : 'current-password'} hint={creating ? 'At least 8 characters.' : undefined} />
        {error ? <ErrorNote error={error} /> : null}
        <Btn title={creating ? 'Create account' : 'Sign in'} loading={busy} disabled={!email.trim() || !password || (creating && !name.trim())} onPress={submit} />
        <Pressable
          hitSlop={8}
          onPress={() => {
            setMode(creating ? 'in' : 'up');
            setError(null);
          }}>
          <Text style={{ textAlign: 'center', color: C.navy, fontWeight: '600', padding: 8 }}>{creating ? 'Already have an account? Sign in' : 'New here? Create an account'}</Text>
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
