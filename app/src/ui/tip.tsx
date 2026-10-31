import Ionicons from '@expo/vector-icons/Ionicons';
import { useEffect, useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { get, send } from '@/lib/api';
import { C } from '@/lib/theme';

/** One-time hint for a screen. Dismissal is saved on the profile, so it shows on the first visit only. */
export function Tip({ id, text }: { id: string; text: string }) {
  const [state, setState] = useState<{ show: boolean; seen: string[] }>({ show: false, seen: [] });

  useEffect(() => {
    let live = true;
    get('/profile')
      .then((p: any) => {
        const seen: string[] = p.tips_seen ?? [];
        if (live) setState({ show: p.onboarded !== false && !seen.includes(id), seen });
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [id]);

  if (!state.show) return null;
  return (
    <View style={{ flexDirection: 'row', gap: 10, backgroundColor: C.skySoft, borderRadius: 14, padding: 12, alignItems: 'flex-start' }}>
      <Ionicons name="bulb-outline" size={20} color={C.navy} />
      <Text style={{ flex: 1, color: C.text, fontSize: 13, lineHeight: 19 }}>{text}</Text>
      <Pressable
        hitSlop={10}
        onPress={() => {
          setState({ show: false, seen: state.seen });
          send('/profile', { tips_seen: [...state.seen, id] }, 'PATCH').catch(() => {});
        }}>
        <Text style={{ color: C.navy, fontWeight: '700', fontSize: 13 }}>Got it</Text>
      </Pressable>
    </View>
  );
}
