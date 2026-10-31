import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { send } from '@/lib/api';
import { useApp } from '@/lib/app-context';
import { C } from '@/lib/theme';
import { Btn, ErrorNote, Field, PaytmLogo } from '@/ui/kit';

export default function Login() {
  const insets = useSafeAreaInsets();
  const { signIn, signUp } = useApp();
  const [mode, setMode] = useState<'in' | 'up' | 'forgot' | 'reset'>('in');
  const [code, setCode] = useState('');
  const [note, setNote] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const creating = mode === 'up';
  const title = { in: 'Sign in to Claimezy', up: 'Create your account', forgot: 'Reset your password', reset: 'Enter your code' }[mode];
  const action = { in: 'Sign in', up: 'Create account', forgot: 'Send me a code', reset: 'Set new password' }[mode];
  const ready = !!email.trim() && (mode === 'forgot' || !!password) && (mode !== 'up' || !!name.trim()) && (mode !== 'reset' || !!code.trim());
  const go = (m: typeof mode) => {
    setMode(m);
    setError(null);
    setNote(null);
  };

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      if (creating) await signUp(name.trim(), email.trim(), password);
      else if (mode === 'forgot') {
        await send('/auth/forgot-password', { email: email.trim() });
        setNote('If that email has an account, we sent a 6-digit code. Check your inbox and spam folder.');
        setPassword('');
        setMode('reset');
      } else if (mode === 'reset') {
        await send('/auth/reset-password', { email: email.trim(), code: code.trim(), password });
        await signIn(email.trim(), password);
      } else await signIn(email.trim(), password);
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
        <Text style={{ fontSize: 26, fontWeight: '800', color: C.text }}>{title}</Text>
        <Text style={{ color: C.sub, lineHeight: 21 }}>{note ?? (mode === 'forgot' ? 'Enter your email and we will send you a code.' : 'Your policies, claims and chats are saved to your account, so they are here whenever you come back.')}</Text>
        {creating ? <Field label="Your name" value={name} onChangeText={setName} autoComplete="name" textContentType="name" /> : null}
        <Field label="Email" value={email} onChangeText={setEmail} autoCapitalize="none" autoCorrect={false} autoComplete="email" keyboardType="email-address" textContentType="emailAddress" />
        {mode === 'reset' ? <Field label="6-digit code" value={code} onChangeText={setCode} keyboardType="number-pad" maxLength={6} /> : null}
        {mode !== 'forgot' ? <Field label={mode === 'reset' ? 'New password' : 'Password'} value={password} onChangeText={setPassword} secureTextEntry autoCapitalize="none" autoComplete={mode === 'in' ? 'current-password' : 'new-password'} hint={mode === 'in' ? undefined : 'At least 8 characters.'} /> : null}
        {error ? <ErrorNote error={error} /> : null}
        <Btn title={action} loading={busy} disabled={!ready} onPress={submit} />
        {mode === 'in' ? (
          <Pressable hitSlop={8} onPress={() => go('forgot')}>
            <Text style={{ textAlign: 'center', color: C.navy, fontWeight: '600', padding: 4 }}>Forgot password?</Text>
          </Pressable>
        ) : null}
        <Pressable hitSlop={8} onPress={() => go(mode === 'in' ? 'up' : 'in')}>
          <Text style={{ textAlign: 'center', color: C.navy, fontWeight: '600', padding: 8 }}>{mode === 'in' ? 'New here? Create an account' : 'Back to sign in'}</Text>
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
