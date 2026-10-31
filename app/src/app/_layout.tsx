import { router, Stack, usePathname } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { Animated, Dimensions, PanResponder, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaProvider, useSafeAreaInsets } from 'react-native-safe-area-context';

import { API_BASE } from '@/lib/api';
import { AppProvider, useApp } from '@/lib/app-context';
import { C, shadow } from '@/lib/theme';
import { AssistantAvatar } from '@/ui/assistant-avatar';

SplashScreen.preventAutoHideAsync();

const FAB_W = 64;
const FAB_H = 82;
const EDGE = 12;

/**
 * The assistant button. Tap to open; drag it anywhere and it snaps to the nearest side, so it never
 * covers what the user is reading. It keeps its place while moving between screens.
 */
function AskFab() {
  const path = usePathname();
  const { t } = useApp();
  const insets = useSafeAreaInsets();
  const { width, height } = useWindowDimensions();
  // Mutable drag state, read and written only inside gesture handlers and effects.
  const [drag] = useState(() => {
    const start = { x: width - FAB_W - EDGE, y: height - insets.bottom - 92 - FAB_H };
    return { last: start, bounds: { width, height, top: insets.top, bottom: insets.bottom }, pos: new Animated.ValueXY(start) };
  });
  const pos = drag.pos;

  const [responder] = useState(() =>
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dx) + Math.abs(g.dy) > 4,
      onPanResponderGrant: () => {
        pos.setOffset(drag.last);
        pos.setValue({ x: 0, y: 0 });
      },
      onPanResponderMove: Animated.event([null, { dx: pos.x, dy: pos.y }], { useNativeDriver: false }),
      onPanResponderRelease: (_, g) => {
        pos.flattenOffset();
        if (Math.abs(g.dx) < 6 && Math.abs(g.dy) < 6) {
          pos.setValue(drag.last);
          router.push('/assistant');
          return;
        }
        const { width: w, height: h } = Dimensions.get('window'); // current size, read at drop time
        const b = { ...drag.bounds, width: w, height: h };
        const x = drag.last.x + g.dx;
        const y = drag.last.y + g.dy;
        const snapX = x + FAB_W / 2 < b.width / 2 ? EDGE : b.width - FAB_W - EDGE;
        const snapY = Math.min(Math.max(y, b.top + 70), b.height - b.bottom - FAB_H - 16);
        drag.last = { x: snapX, y: snapY };
        Animated.spring(pos, { toValue: drag.last, useNativeDriver: false, friction: 7 }).start();
      },
      onPanResponderTerminate: () => {
        pos.flattenOffset();
        Animated.spring(pos, { toValue: drag.last, useNativeDriver: false }).start();
      },
    }),
  );

  const hidden = path === '/' || path.startsWith('/assistant') || path.startsWith('/onboarding');
  if (hidden) return null;
  return (
    <Animated.View
      {...responder.panHandlers}
      accessible
      accessibilityRole="button"
      accessibilityLabel="Ask the Claimezy assistant. Drag to move."
      onAccessibilityTap={() => router.push('/assistant')}
      style={{ position: 'absolute', left: 0, top: 0, width: FAB_W, alignItems: 'center', gap: 2, transform: pos.getTranslateTransform(), ...shadow, elevation: 6 }}>
      <AssistantAvatar size={60} />
      <Text style={{ color: C.navy, fontWeight: '800', fontSize: 11 }}>{t('ask')}</Text>
    </Animated.View>
  );
}

function OfflineBanner() {
  const { online } = useApp();
  const insets = useSafeAreaInsets();
  if (online !== false) return null;
  return (
    <View style={{ position: 'absolute', top: insets.top, left: 0, right: 0, backgroundColor: C.red, padding: 8 }}>
      <Text style={{ color: '#fff', textAlign: 'center', fontSize: 12 }}>{`Can't reach the Claimezy server at ${API_BASE}. Is the laptop on the same hotspot?`}</Text>
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
