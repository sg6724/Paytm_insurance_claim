import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { useEffect, useState, type ReactNode } from 'react';
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type StyleProp,
  type TextInputProps,
  type ViewStyle,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { C, R, shadow } from '@/lib/theme';

export type IconName = keyof typeof Ionicons.glyphMap;

export function PaytmLogo({ size = 22, sub }: { size?: number; sub?: string }) {
  return (
    <View style={{ alignItems: 'center' }}>
      <Text style={{ fontSize: size, fontWeight: '900', letterSpacing: -0.5 }}>
        <Text style={{ color: C.navy }}>pay</Text>
        <Text style={{ color: C.sky }}>tm</Text>
      </Text>
      {sub ? <Text style={{ fontSize: 8, color: C.navy, marginTop: -3, fontWeight: '600' }}>{sub}</Text> : null}
    </View>
  );
}

/** Paytm Insurance Broking header: back arrow, logo centred, Help on the right. */
export function Header({ title, sub = 'Insurance Broking', onHelp, back = true, right }: { title?: string; sub?: string; onHelp?: () => void; back?: boolean; right?: ReactNode }) {
  const insets = useSafeAreaInsets();
  return (
    <View style={[s.header, { paddingTop: insets.top + 6 }]}>
      <View style={s.headerRow}>
        <View style={{ width: 64 }}>
          {back ? (
            <Pressable hitSlop={12} onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} accessibilityLabel="Back">
              <Ionicons name="arrow-back" size={24} color={C.text} />
            </Pressable>
          ) : null}
        </View>
        <PaytmLogo sub={sub} />
        <View style={{ width: 64, alignItems: 'flex-end' }}>
          {right ?? (
            <Pressable hitSlop={12} onPress={onHelp ?? (() => router.push('/guide'))}>
              <Text style={{ color: C.sky, fontWeight: '600' }}>Help</Text>
            </Pressable>
          )}
        </View>
      </View>
      {title ? <Text style={s.headerTitle}>{title}</Text> : null}
    </View>
  );
}

export function Screen({ children, footer, scroll = true, style }: { children: ReactNode; footer?: ReactNode; scroll?: boolean; style?: StyleProp<ViewStyle> }) {
  const insets = useSafeAreaInsets();
  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      {scroll ? (
        <ScrollView contentContainerStyle={[{ padding: 16, paddingBottom: footer ? 120 : 40, gap: 14 }, style]} keyboardShouldPersistTaps="handled">
          {children}
        </ScrollView>
      ) : (
        <View style={[{ flex: 1 }, style]}>{children}</View>
      )}
      {footer ? <View style={[s.footer, { paddingBottom: insets.bottom + 12 }]}>{footer}</View> : null}
    </View>
  );
}

export function Card({ children, style, onPress }: { children: ReactNode; style?: StyleProp<ViewStyle>; onPress?: () => void }) {
  if (onPress)
    return (
      <Pressable onPress={onPress} style={({ pressed }) => [s.card, style, pressed && { opacity: 0.85 }]}>
        {children}
      </Pressable>
    );
  return <View style={[s.card, style]}>{children}</View>;
}

export function H({ children, style }: { children: ReactNode; style?: any }) {
  return <Text style={[s.h, style]}>{children}</Text>;
}

export function P({ children, style, muted }: { children: ReactNode; style?: any; muted?: boolean }) {
  return <Text style={[s.p, muted && { color: C.sub }, style]}>{children}</Text>;
}

export function Btn({ title, onPress, kind = 'primary', icon, loading, disabled, style }: { title: string; onPress?: () => void; kind?: 'primary' | 'secondary' | 'ghost' | 'danger'; icon?: IconName; loading?: boolean; disabled?: boolean; style?: StyleProp<ViewStyle> }) {
  const bg = kind === 'primary' ? C.navy : kind === 'danger' ? C.red : kind === 'secondary' ? C.skySoft : 'transparent';
  const fg = kind === 'primary' || kind === 'danger' ? '#fff' : C.navy;
  return (
    <Pressable
      onPress={loading || disabled ? undefined : onPress}
      style={({ pressed }) => [s.btn, { backgroundColor: bg, opacity: disabled ? 0.45 : pressed ? 0.85 : 1 }, kind === 'ghost' && { borderWidth: 1, borderColor: C.line }, style]}
      accessibilityRole="button">
      {loading ? <ActivityIndicator color={fg} /> : icon ? <Ionicons name={icon} size={18} color={fg} /> : null}
      <Text style={[s.btnText, { color: fg }]}>{title}</Text>
    </Pressable>
  );
}

export function IconBubble({ name, color = C.navy, bg = C.skySoft, size = 40 }: { name: IconName; color?: string; bg?: string; size?: number }) {
  return (
    <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: bg, alignItems: 'center', justifyContent: 'center' }}>
      <Ionicons name={name} size={size * 0.5} color={color} />
    </View>
  );
}

/** List row from the Paytm "Know before you choose a plan" pattern. */
export function Row({ icon, title, sub, onPress, right, iconColor, iconBg }: { icon: IconName; title: string; sub?: string; onPress?: () => void; right?: ReactNode; iconColor?: string; iconBg?: string }) {
  return (
    <Pressable onPress={onPress} disabled={!onPress} style={({ pressed }) => [s.row, pressed && { backgroundColor: C.paleBlue }]}>
      <IconBubble name={icon} color={iconColor} bg={iconBg} />
      <View style={{ flex: 1 }}>
        <Text style={s.rowTitle}>{title}</Text>
        {sub ? <Text style={s.rowSub}>{sub}</Text> : null}
      </View>
      {right ?? (onPress ? <Ionicons name="chevron-forward" size={20} color={C.text} /> : null)}
    </Pressable>
  );
}

export function Pill({ text, tone = 'info' }: { text: string; tone?: 'info' | 'ok' | 'warn' | 'bad' | 'muted' }) {
  const map = { info: [C.skySoft, C.navy], ok: [C.greenSoft, C.green], warn: [C.amberSoft, C.amber], bad: [C.redSoft, C.red], muted: [C.line, C.sub] } as const;
  const [bg, fg] = map[tone];
  return (
    <View style={{ backgroundColor: bg, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 99, alignSelf: 'flex-start' }}>
      <Text style={{ color: fg, fontSize: 12, fontWeight: '700' }}>{text}</Text>
    </View>
  );
}

export function Field({ label, value, onChangeText, hint, tone, source, ...rest }: { label: string; value: string; onChangeText: (t: string) => void; hint?: ReactNode; tone?: 'error' | 'warning' | 'info' | 'required'; source?: string } & TextInputProps) {
  const border = tone === 'error' ? C.red : tone === 'warning' ? C.amber : C.line;
  return (
    <View style={{ gap: 4 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        <Text style={s.label}>{label}</Text>
        {source ? (
          <View style={s.aiTag}>
            <Ionicons name="sparkles" size={10} color={C.navy} />
            <Text style={{ fontSize: 10, color: C.navy, fontWeight: '700' }}>{source}</Text>
          </View>
        ) : null}
      </View>
      <TextInput value={value} onChangeText={onChangeText} placeholderTextColor={C.faint} style={[s.input, { borderColor: border }]} {...rest} />
      {typeof hint === 'string' ? <Text style={{ color: C.sub, fontSize: 12 }}>{hint}</Text> : hint}
    </View>
  );
}

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <View style={{ padding: 32, alignItems: 'center', gap: 10 }}>
      <ActivityIndicator color={C.navy} size="large" />
      <Text style={{ color: C.sub }}>{label}</Text>
    </View>
  );
}

export function ErrorNote({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <Card style={{ backgroundColor: C.redSoft, borderColor: '#F7C5C0' }}>
      <Text style={{ color: C.red, fontWeight: '600' }}>{error}</Text>
      {onRetry ? <Btn title="Try again" kind="ghost" onPress={onRetry} style={{ marginTop: 8 }} /> : null}
    </Card>
  );
}

export function Sheet({ visible, onClose, children, title }: { visible: boolean; onClose: () => void; children: ReactNode; title?: string }) {
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={s.scrim} onPress={onClose} />
      <View style={[s.sheet, { paddingBottom: insets.bottom + 16 }]}>
        <View style={s.grabber} />
        {title ? <Text style={[s.h, { marginBottom: 8 }]}>{title}</Text> : null}
        {children}
      </View>
    </Modal>
  );
}

export function Money({ value, size = 28, color = C.text }: { value: number | null | undefined; size?: number; color?: string }) {
  return <Text style={{ fontSize: size, fontWeight: '800', color, fontVariant: ['tabular-nums'] }}>{value === null || value === undefined ? '–' : '₹' + Math.round(value).toLocaleString('en-IN')}</Text>;
}

export function Section({ title, action, onAction, children }: { title: string; action?: string; onAction?: () => void; children: ReactNode }) {
  return (
    <View style={{ gap: 10 }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text style={s.sectionTitle}>{title}</Text>
        {action ? (
          <Pressable onPress={onAction}>
            <Text style={{ color: C.sky, fontWeight: '600' }}>{action} →</Text>
          </Pressable>
        ) : null}
      </View>
      {children}
    </View>
  );
}

/** Wrap a button handler: if it fails (network, server), show a friendly message instead of crashing. */
export function act<A extends any[]>(fn: (...args: A) => unknown) {
  return (...args: A) => {
    Promise.resolve()
      .then(() => fn(...args))
      .catch((e: any) => {
        console.log('[action failed]', e?.message);
        Alert.alert('Something went wrong', e?.message ?? 'Please try again.');
      });
  };
}

export function useAsync<T>(fn: () => Promise<T>, deps: any[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const key = JSON.stringify([...deps, tick]);
  const [doneKey, setDoneKey] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    fn()
      .then((d) => {
        if (!alive) return;
        setData(d);
        setError(null);
      })
      .catch((e) => alive && setError(e?.message ?? 'Something went wrong'))
      .finally(() => alive && setDoneKey(key));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return { data, setData, error: doneKey === key ? error : null, loading: doneKey !== key, reload: () => setTick((t) => t + 1) };
}

export const s = StyleSheet.create({
  header: { backgroundColor: '#fff', paddingHorizontal: 16, paddingBottom: 10, borderBottomWidth: 1, borderBottomColor: C.line },
  headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  headerTitle: { fontSize: 20, fontWeight: '700', color: C.text, marginTop: 10 },
  footer: { position: 'absolute', left: 0, right: 0, bottom: 0, paddingHorizontal: 16, paddingTop: 12, backgroundColor: '#fff', borderTopWidth: 1, borderTopColor: C.line, gap: 8 },
  card: { backgroundColor: C.card, borderRadius: R.lg, padding: 16, borderWidth: 1, borderColor: C.line, ...shadow },
  h: { fontSize: 18, fontWeight: '700', color: C.text },
  p: { fontSize: 14, lineHeight: 21, color: C.text },
  btn: { height: 50, borderRadius: 25, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingHorizontal: 18 },
  btnText: { fontSize: 16, fontWeight: '700' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 14, paddingVertical: 12 },
  rowTitle: { fontSize: 15, fontWeight: '600', color: C.text },
  rowSub: { fontSize: 13, color: C.sub, marginTop: 2 },
  label: { fontSize: 13, color: C.sub, fontWeight: '600' },
  input: { borderWidth: 1.5, borderRadius: R.md, paddingHorizontal: 14, paddingVertical: 12, fontSize: 15, color: C.text, backgroundColor: '#fff' },
  aiTag: { flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: C.skySoft, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
  scrim: { flex: 1, backgroundColor: 'rgba(16,24,40,0.45)' },
  sheet: { backgroundColor: '#fff', borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 20, gap: 12, maxHeight: '88%' },
  grabber: { width: 44, height: 5, borderRadius: 3, backgroundColor: C.line, alignSelf: 'center', marginBottom: 6 },
  sectionTitle: { fontSize: 17, fontWeight: '700', color: C.text },
});
