import { useLocalSearchParams } from 'expo-router';
import { ScrollView, Text, View } from 'react-native';

import { get } from '@/lib/api';
import { C } from '@/lib/theme';
import { Card, Header, Loading, Pill, Screen, useAsync } from '@/ui/kit';

export default function Fhir() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const q = useAsync(() => get(`/claims/${id}/fhir`), [id]);
  const types = (q.data?.entry ?? []).map((e: any) => e.resource.resourceType);
  return (
    <View style={{ flex: 1 }}>
      <Header title="NHCX claim pack" sub="" />
      <Screen>
        <Text style={{ color: C.sub }}>Your claim as a FHIR R4 bundle following the NRCeS ClaimBundle profile used by the National Health Claims Exchange. Insurers can process it without retyping.</Text>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          {[...new Set(types)].map((t: any) => (
            <Pill key={t} text={`${t} × ${types.filter((x: string) => x === t).length}`} />
          ))}
        </View>
        {q.loading ? <Loading /> : null}
        {q.data ? (
          <Card style={{ backgroundColor: '#0B1F3A', borderColor: '#0B1F3A' }}>
            <ScrollView horizontal>
              <Text style={{ fontFamily: 'monospace', fontSize: 11, color: '#CFE6F7' }}>{JSON.stringify(q.data, null, 2)}</Text>
            </ScrollView>
          </Card>
        ) : null}
      </Screen>
    </View>
  );
}
