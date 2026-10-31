import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useApp } from '@/lib/app-context';
import { C, shadow } from '@/lib/theme';
import type { IconName } from '@/ui/kit';

const BLUE = '#1C3F94';
const LINK = '#2F6FC4';
const TILE_ICON = '#1F4FA3';

type Tile = { icon: IconName; label: string; onPress?: () => void; badge?: string };

function TileItem({ t, width }: { t: Tile; width: number | `${number}%` }) {
  return (
    <Pressable style={[st.tile, { width }]} onPress={t.onPress} disabled={!t.onPress}>
      {t.badge ? (
        <View style={st.badge}>
          <Text style={st.badgeText}>{t.badge}</Text>
        </View>
      ) : null}
      <Ionicons name={t.icon} size={22} color={t.onPress ? C.navy : TILE_ICON} />
      <Text style={st.tileText}>{t.label}</Text>
    </Pressable>
  );
}

function BlockHead({ title, action }: { title: string; action: string }) {
  return (
    <View style={st.blockHead}>
      <Text style={st.blockTitle}>{title}</Text>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
        <Text style={{ color: LINK, fontSize: 14, fontWeight: '500' }}>{action}</Text>
        <Ionicons name="arrow-forward" size={15} color={LINK} />
      </View>
    </View>
  );
}

const QUICK: { icon: IconName; label: string }[] = [
  { icon: 'qr-code-outline', label: 'Scan any\nQR' },
  { icon: 'person-add-outline', label: 'Pay\nAnyone' },
  { icon: 'business-outline', label: 'To Bank &\nSelf A/c' },
  { icon: 'receipt-outline', label: 'Balance &\nHistory' },
];

const RECHARGE: Tile[] = [
  { icon: 'phone-portrait-outline', label: 'Mobile Recharge' },
  { icon: 'card-outline', label: 'Credit Card Bill', badge: 'Get ₹50' },
  { icon: 'bulb-outline', label: 'Electricity Bill' },
  { icon: 'car-outline', label: 'FASTag Recharge' },
  { icon: 'calendar-outline', label: 'Loan EMI Payment' },
];

const CHIPS: { icon: IconName; label: string; color: string }[] = [
  { icon: 'sparkles', label: 'Golden Diwali', color: '#C8791A' },
  { icon: 'gift-outline', label: 'Refer & Win ₹450', color: TILE_ICON },
  { icon: 'cash-outline', label: 'Cashback & Offers', color: TILE_ICON },
];

/** Paytm home as it looks today. Claimezy is reached the way users would find it: the Health Insurance tile under Financial Services. */
export default function Home() {
  const insets = useSafeAreaInsets();
  const { t } = useApp();
  const goInsurance = () => router.push('/insurance');
  return (
    <View style={{ flex: 1, backgroundColor: st.page.backgroundColor }}>
      <ScrollView contentContainerStyle={{ paddingTop: insets.top + 10, paddingHorizontal: 12, paddingBottom: 110, gap: 12 }} showsVerticalScrollIndicator={false}>
        <View style={st.top}>
          <Pressable style={st.avatar} onPress={() => router.push('/settings')} accessibilityLabel="Profile and language">
            <Text style={{ color: '#2E7D74', fontSize: 14 }}>JO</Text>
          </Pressable>
          <View style={{ flex: 1, marginLeft: 8 }}>
            <Text style={st.logoTop}>GOLDEN</Text>
            <Text style={st.logoBottom}>DIWALI</Text>
          </View>
          <Ionicons name="notifications-outline" size={26} color="#111" />
        </View>

        <View style={st.search}>
          <Ionicons name="search-outline" size={19} color="#333" />
          <Text style={{ color: '#7A7F87', fontSize: 14 }}>{t('searchPay')}</Text>
        </View>

        <View style={st.quick}>
          {QUICK.map((q) => (
            <View key={q.label} style={{ width: '25%', alignItems: 'center', gap: 8 }}>
              <View style={st.quickIcon}>
                <Ionicons name={q.icon} size={22} color="#fff" />
              </View>
              <Text style={st.quickText}>{q.label}</Text>
            </View>
          ))}
        </View>

        <View style={st.block}>
          <BlockHead title="Recharge & Bills" action="View All" />
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingTop: 12 }}>
            {RECHARGE.map((x) => (
              <TileItem key={x.label} t={x} width={72} />
            ))}
          </ScrollView>
          <View style={st.dots}>
            <View style={st.dotOn} />
          </View>
        </View>

        <View style={st.offer}>
          <Text style={{ fontSize: 32 }}>🎁</Text>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 15, fontWeight: '700', color: '#151515' }}>Exclusive offer for You!</Text>
            <Text style={{ fontSize: 12, color: '#333', marginTop: 3 }}>Claim your exclusive reward</Text>
          </View>
          <Ionicons name="chevron-forward" size={22} color="#222" />
        </View>

        <View style={{ flexDirection: 'row', gap: 10 }}>
          <View style={[st.promo, { flex: 1, justifyContent: 'space-between', paddingVertical: 14 }]}>
            <Ionicons name="calendar-outline" size={22} color="#8A8F98" />
            <View style={{ marginTop: 40 }}>
              <Text style={{ fontSize: 14, color: '#151515' }}>Postpaid Offer</Text>
              <Text style={{ fontSize: 12, color: '#7A7F87', marginTop: 3, lineHeight: 16 }}>Pay & Earn 11,000 Gold Coins — Activate Now</Text>
            </View>
          </View>
          <View style={{ flex: 1, gap: 10 }}>
            <View style={[st.promo, st.promoRow]}>
              <Ionicons name="airplane-outline" size={20} color="#6B7280" />
              <Text style={st.promoText}>Get Gold* on Flights</Text>
            </View>
            <View style={[st.promo, st.promoRow]}>
              <Ionicons name="people-outline" size={20} color="#6B7280" />
              <Text style={st.promoText}>Refer & Win ₹450</Text>
            </View>
          </View>
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 10 }} style={{ marginRight: -12 }}>
          {CHIPS.map((c) => (
            <View key={c.label} style={st.chip}>
              <Ionicons name={c.icon} size={15} color={c.color} />
              <Text style={{ fontSize: 12, color: '#222' }}>{c.label}</Text>
            </View>
          ))}
        </ScrollView>

        <View style={st.banner}>
          <View>
            <View style={st.bannerPaytm}>
              <Text style={{ fontWeight: '900', fontSize: 12 }}>
                <Text style={{ color: C.navy }}>pay</Text>
                <Text style={{ color: C.sky }}>tm</Text>
              </Text>
            </View>
            <Text style={st.bannerGold}>GOLDEN{'\n'}DIWALI</Text>
          </View>
          <View style={{ flex: 1, alignItems: 'flex-end' }}>
            <Text style={{ color: '#fff', fontSize: 13, fontWeight: '600' }}>Pay using Paytm</Text>
            <Text style={{ color: '#FFD76A', fontSize: 14, fontWeight: '800', marginTop: 2 }}>Win Gold Every Hour</Text>
            <View style={st.bannerBtn}>
              <Text style={{ fontWeight: '700', fontSize: 13, color: '#111' }}>Pay Now →</Text>
            </View>
          </View>
        </View>

        <View style={st.block}>
          <BlockHead title={t('financialServices')} action={t('viewAll')} />
          <View style={st.grid}>
            {[
              { icon: 'cash-outline', label: 'Loan' },
              { icon: 'bar-chart-outline', label: 'Mutual Fund', badge: 'SIP @ ₹21' },
              { icon: 'car-sport-outline', label: 'Car Insurance' },
              { icon: 'bicycle-outline', label: 'Bike Insurance' },
              { icon: 'wallet-outline', label: 'Paytm Postpaid' },
              { icon: 'trending-up-outline', label: 'Stocks' },
              { icon: 'card-outline', label: 'Get Credit Card' },
              { icon: 'heart-outline', label: t('healthInsurance'), onPress: goInsurance, badge: 'Claims' },
            ].map((x) => (
              <TileItem key={x.label} t={x as Tile} width="25%" />
            ))}
          </View>
        </View>
      </ScrollView>

      <View style={[st.scanWrap, { bottom: insets.bottom + 14 }]}>
        <View style={st.scan}>
          <Ionicons name="qr-code-outline" size={19} color="#fff" />
          <Text style={{ color: '#fff', fontSize: 17 }}>Scan QR</Text>
        </View>
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  page: { backgroundColor: '#F5F7FA' },
  top: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 4 },
  avatar: { width: 38, height: 38, borderRadius: 19, backgroundColor: '#C9F2E7', alignItems: 'center', justifyContent: 'center' },
  logoTop: { fontSize: 15, fontWeight: '900', color: '#E8A317', letterSpacing: 0.3, lineHeight: 16, textShadowColor: '#A8211B', textShadowRadius: 1, textShadowOffset: { width: 0.5, height: 1 } },
  logoBottom: { fontSize: 12, fontWeight: '900', color: '#C8341F', letterSpacing: 0.3, lineHeight: 13, marginLeft: 8 },
  search: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#fff', borderRadius: 22, paddingHorizontal: 14, height: 44 },
  quick: { flexDirection: 'row', paddingVertical: 8 },
  quickIcon: { width: 44, height: 44, borderRadius: 22, backgroundColor: BLUE, alignItems: 'center', justifyContent: 'center' },
  quickText: { fontSize: 12, color: '#333', textAlign: 'center', lineHeight: 16, letterSpacing: 0.2 },
  block: { backgroundColor: '#fff', borderRadius: 18, paddingHorizontal: 16, paddingTop: 16, paddingBottom: 12 },
  blockHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  blockTitle: { fontSize: 19, fontWeight: '700', color: '#1B1B1B' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', rowGap: 18, paddingTop: 18 },
  tile: { alignItems: 'center', gap: 6, paddingHorizontal: 2 },
  tileText: { fontSize: 12, color: '#333', textAlign: 'center', lineHeight: 15 },
  badge: { position: 'absolute', top: -13, backgroundColor: '#FFD84D', paddingHorizontal: 6, paddingVertical: 1, borderRadius: 5, zIndex: 1 },
  badgeText: { fontSize: 10, fontWeight: '600', color: '#222' },
  dots: { alignSelf: 'center', width: 30, height: 6, borderRadius: 3, backgroundColor: '#EBDDE0', marginTop: 12, overflow: 'hidden' },
  dotOn: { width: 16, height: 6, borderRadius: 3, backgroundColor: '#6F7680' },
  offer: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#D6EEF6', borderRadius: 28, paddingHorizontal: 14, paddingVertical: 8 },
  promo: { backgroundColor: '#fff', borderRadius: 18, paddingHorizontal: 16 },
  promoRow: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 72 },
  promoText: { flex: 1, fontSize: 13, color: '#333' },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#fff', borderRadius: 18, paddingHorizontal: 12, height: 36 },
  banner: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#2F4FB5', borderRadius: 18, padding: 16, minHeight: 140 },
  bannerPaytm: { backgroundColor: '#fff', alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6, marginBottom: 6 },
  bannerGold: { fontSize: 22, fontWeight: '900', color: '#FFC83A', lineHeight: 24, textShadowColor: '#A8211B', textShadowRadius: 1, textShadowOffset: { width: 1, height: 1.5 } },
  bannerBtn: { backgroundColor: '#fff', borderRadius: 20, paddingHorizontal: 16, paddingVertical: 8, marginTop: 10 },
  scanWrap: { position: 'absolute', left: 0, right: 0, alignItems: 'center' },
  scan: { flexDirection: 'row', gap: 10, alignItems: 'center', backgroundColor: '#0A2D6B', paddingHorizontal: 22, height: 48, borderRadius: 24, borderWidth: 1.5, borderColor: '#3FA7E0', ...shadow, elevation: 6 },
});
