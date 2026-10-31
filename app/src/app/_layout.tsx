import { router, Stack, usePathname } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { Pressable, Text, View } from 'react-native';
import { SafeAreaProvider, useSafeAreaInsets } from 'react-native-safe-area-context';

import { API_BASE } from '@/lib/api';
import { AppProvider, useApp } from '@/lib/app-context';
import { C, shadow } from '@/lib/theme';
import { AssistantAvatar } from '@/ui/assistant-avatar';

SplashScreen.preventAutoHideAsync();

function AskFab() {
  const path = usePathname();
  const { t } = useApp();
  const insets = useSafeAreaInsets();
  const hidden = path === '/' || path.startsWith('/assistant') || path.startsWith('/onboarding');
  if (hidden) return null;
  return (
    <Pressable
      onPress={() => router.push('/assistant')}
      accessibilityLabel="Ask the Claim-to-Cash assistant"
      style={{ position: 'absolute', right: 16, bottom: insets.bottom + 92, alignItems: 'center', gap: 2, ...shadow, elevation: 6 }}>
      <AssistantAvatar size={60} />
      <Text style={{ color: C.navy, fontWeight: '800', fontSize: 11 }}>{t('ask')}</Text>
    </Pressable>
  );
}

function OfflineBanner() {
  const { online } = useApp();
  const insets = useSafeAreaInsets();
  if (online !== false) return null;
  return (
    <View style={{ position: 'absolute', top: insets.top, left: 0, right: 0, backgroundColor: C.red, padding: 8 }}>
      <Text style={{ color: '#fff', textAlign: 'center', fontSize: 12 }}>{`Can't reach the Claim-to-Cash server at ${API_BASE}. Is the laptop on the same hotspot?`}</Text>
    </View>
  );
}

export default function RootLayout() {
  useEffect(() => {
    SplashScreen.hideAsync();
  }, []);
  return (
    <SafeAreaProvider>
      <AppProvider>
        <StatusBar style="dark" />
        <View style={{ flex: 1, backgroundColor: C.bg }}>
          <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: C.bg }, animation: 'slide_from_right' }}>
            <Stack.Screen name="assistant" options={{ presentation: 'modal', animation: 'slide_from_bottom' }} />
          </Stack>
          <AskFab />
          <OfflineBanner />
        </View>
      </AppProvider>
    </SafeAreaProvider>
  );
}
