import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useApp } from '@/lib/app-context';
import { C, shadow } from '@/lib/theme';
import type { IconName } from '@/ui/kit';

type Tile = { icon: IconName; label: string; onPress?: () => void; badge?: string };

function Grid({ title, tiles, action }: { title: string; tiles: Tile[]; action?: string }) {
  return (
    <View style={st.block}>
      <View style={st.blockHead}>
        <Text style={st.blockTitle}>{title}</Text>
        {action ? <Text style={{ color: C.sky, fontWeight: '600' }}>{action} →</Text> : null}
      </View>
      <View style={st.grid}>
        {tiles.map((t) => (
          <Pressable key={t.label} style={st.tile} onPress={t.onPress} disabled={!t.onPress}>
            {t.badge ? (
              <View style={st.badge}>
                <Text style={st.badgeText}>{t.badge}</Text>
              </View>
            ) : null}
            <Ionicons name={t.icon} size={26} color={t.onPress ? C.navy : '#3B6BB1'} />
            <Text style={st.tileText}>{t.label}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

/** Paytm-style home: the same grid users already know, with the Health Insurance tile as the way in. */
export default function Home() {
  const insets = useSafeAreaInsets();
  const { t } = useApp();
  const goInsurance = () => router.push('/insurance');
  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <View style={[st.top, { paddingTop: insets.top + 8 }]}>
        <View style={st.avatar}>
          <Text style={{ color: C.navy, fontWeight: '700' }}>SK</Text>
        </View>
        <View style={st.search}>
          <Ionicons name="search" size={18} color={C.sub} />
          <Text style={{ color: C.sub }}>{t('searchPay')}</Text>
        </View>
        <Pressable onPress={() => router.push('/settings')} hitSlop={10}>
          <Ionicons name="language" size={24} color={C.navy} />
        </Pressable>
      </View>
      <ScrollView contentContainerStyle={{ padding: 12, gap: 12, paddingBottom: 120 }}>
        <Grid
          title="Recharge & Bills"
          action="View All"
          tiles={[
            { icon: 'phone-portrait-outline', label: 'Mobile Recharge' },
            { icon: 'card-outline', label: 'Credit Card Bill' },
            { icon: 'bulb-outline', label: 'Electricity Bill' },
            { icon: 'car-outline', label: 'FASTag Recharge' },
          ]}
        />
        <Grid
          title={t('financialServices')}
          action={t('viewAll')}
          tiles={[
            { icon: 'cash-outline', label: 'Loan' },
            { icon: 'bar-chart-outline', label: 'Mutual Fund', badge: 'SIP @ ₹21' },
            { icon: 'car-sport-outline', label: 'Car Insurance' },
            { icon: 'bicycle-outline', label: 'Bike Insurance' },
            { icon: 'wallet-outline', label: 'Paytm Postpaid' },
            { icon: 'trending-up-outline', label: 'Stocks' },
            { icon: 'card-outline', label: 'Get Credit Card' },
            { icon: 'heart-outline', label: t('healthInsurance'), onPress: goInsurance, badge: 'Claims' },
          ]}
        />
        <Grid
          title="Travel & Tickets"
          tiles={[
            { icon: 'airplane-outline', label: 'Flight' },
            { icon: 'train-outline', label: 'Train' },
            { icon: 'bus-outline', label: 'Bus' },
            { icon: 'subway-outline', label: 'Metro' },
          ]}
        />
      </ScrollView>
      <View style={[st.scanWrap, { bottom: insets.bottom + 20 }]}>
        <View style={st.scan}>
          <Ionicons name="scan" size={20} color="#fff" />
          <Text style={{ color: '#fff', fontWeight: '700', fontSize: 16 }}>Scan QR</Text>
        </View>
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  top: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 12, paddingBottom: 10, backgroundColor: C.bg },
  avatar: { width: 38, height: 38, borderRadius: 19, backgroundColor: '#CFF5EC', alignItems: 'center', justifyContent: 'center' },
  search: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#fff', borderRadius: 22, paddingHorizontal: 14, height: 44 },
  block: { backgroundColor: '#fff', borderRadius: 16, padding: 14, ...shadow },
  blockHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  blockTitle: { fontSize: 18, fontWeight: '700', color: C.text },
  grid: { flexDirection: 'row', flexWrap: 'wrap', rowGap: 16 },
  tile: { width: '25%', alignItems: 'center', gap: 6, paddingHorizontal: 2 },
  tileText: { fontSize: 12, color: C.text, textAlign: 'center' },
  badge: { position: 'absolute', top: -10, backgroundColor: '#FFD43B', paddingHorizontal: 5, borderRadius: 4, zIndex: 1 },
  badgeText: { fontSize: 8, fontWeight: '800', color: C.text },
  scanWrap: { position: 'absolute', left: 0, right: 0, alignItems: 'center' },
  scan: { flexDirection: 'row', gap: 8, alignItems: 'center', backgroundColor: C.navy, paddingHorizontal: 22, height: 50, borderRadius: 25, ...shadow, elevation: 6 },
});
