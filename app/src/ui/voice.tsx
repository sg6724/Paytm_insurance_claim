import Ionicons from '@expo/vector-icons/Ionicons';
import {
  RecordingPresets,
  requestRecordingPermissionsAsync,
  setAudioModeAsync,
  useAudioPlayer,
  useAudioPlayerStatus,
  useAudioRecorder,
  useAudioRecorderState,
} from 'expo-audio';
import { useState } from 'react';
import { ActivityIndicator, Alert, Pressable, Text, View } from 'react-native';

import { API_BASE, ttsUrl, upload } from '@/lib/api';
import { useApp } from '@/lib/app-context';
import { C } from '@/lib/theme';

const voiceProblem = (message: string) => Alert.alert('Voice', message);

/** Hold-free mic: tap to record, tap to stop; returns the Sarvam transcript. */
export function useVoiceInput() {
  const { lang } = useApp();
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const state = useAudioRecorderState(recorder);
  const [busy, setBusy] = useState(false);

  async function start() {
    try {
      const { granted } = await requestRecordingPermissionsAsync();
      if (!granted) return voiceProblem('Allow microphone access to speak.');
      await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
    } catch (e: any) {
      voiceProblem(`Could not start the microphone. ${e?.message ?? ''}`);
    }
  }

  async function stop(): Promise<string | null> {
    setBusy(true);
    try {
      await recorder.stop();
      await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: false });
      if (!recorder.uri) throw new Error('No recording was saved.');
      const out = await upload<{ transcript: string }>('/assistant/stt', { uri: recorder.uri, name: 'voice.m4a', type: 'audio/mp4' }, { lang });
      if (!out.transcript) voiceProblem('We could not hear any words. Try again, a little closer to the phone.');
      return out.transcript || null;
    } catch (e: any) {
      voiceProblem(e?.message === 'Network request failed' ? `Can't reach the server at ${API_BASE}.` : (e?.message ?? 'Could not hear that. Try again.'));
      return null;
    } finally {
      setBusy(false);
    }
  }

  return { recording: state.isRecording, busy, start, stop };
}

export function MicButton({ onText, size = 48 }: { onText: (t: string) => void; size?: number }) {
  const v = useVoiceInput();
  return (
    <Pressable
      accessibilityLabel={v.recording ? 'Stop recording' : 'Speak'}
      onPress={async () => {
        if (v.recording) {
          const t = await v.stop();
          if (t) onText(t);
        } else {
          await v.start();
        }
      }}
      style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: v.recording ? C.red : C.skySoft, alignItems: 'center', justifyContent: 'center' }}>
      {v.busy ? <ActivityIndicator color={C.navy} /> : <Ionicons name={v.recording ? 'stop' : 'mic'} size={size * 0.45} color={v.recording ? '#fff' : C.navy} />}
    </Pressable>
  );
}

/** Plays Sarvam Bulbul speech for a text in the current language. */
export function ListenButton({ text, label = 'Listen' }: { text: string; label?: string }) {
  const { lang, ttsSupported } = useApp();
  const player = useAudioPlayer(null);
  const status = useAudioPlayerStatus(player);
  const [loading, setLoading] = useState(false);
  const clean = text.replace(/[*#_`>]/g, '').replace(/\n+/g, '. ');
  const playing = status.playing;
  return (
    <Pressable
      onPress={async () => {
        if (playing) {
          player.pause();
          return;
        }
        setLoading(true);
        try {
          await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: false });
          player.replace({ uri: ttsUrl(clean, ttsSupported ? lang : 'en-IN') });
          player.play();
        } catch (e: any) {
          voiceProblem(`Could not play this. ${e?.message ?? ''}`);
        } finally {
          setTimeout(() => setLoading(false), 600);
        }
      }}
      style={{ flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: C.skySoft, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 99, alignSelf: 'flex-start' }}>
      {loading && !playing ? <ActivityIndicator size="small" color={C.navy} /> : <Ionicons name={playing ? 'pause' : 'volume-high'} size={16} color={C.navy} />}
      <Text style={{ color: C.navy, fontWeight: '700', fontSize: 13 }}>{playing ? 'Pause' : label}</Text>
      {!ttsSupported ? <Text style={{ color: C.sub, fontSize: 11 }}>(English voice)</Text> : null}
    </Pressable>
  );
}

export function VoiceHint() {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
      <Ionicons name="mic-outline" size={14} color={C.sub} />
      <Text style={{ color: C.sub, fontSize: 12 }}>Tap the mic, speak in any Indian language, tap again to stop.</Text>
    </View>
  );
}
