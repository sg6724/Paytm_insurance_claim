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
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Alert, Pressable, Text, View } from 'react-native';

import { speechChunks, ttsUrl, upload } from '@/lib/api';
import { useApp } from '@/lib/app-context';
import { C } from '@/lib/theme';

const voiceProblem = (message: string) => Alert.alert('Voice', message);

// Only one voice plays at a time, and the mic silences it (talking over the assistant should just work).
let stopActiveSpeaker: (() => void) | null = null;

const SILENCE_MS = 1600; // stop on its own after this long quiet, once the user has said something
const MAX_MS = 28000; // Sarvam's live speech-to-text takes up to 30 seconds per clip
const LOUDER_DB = 12; // speech is this much louder than the room noise heard at the start

/**
 * Tap to talk. Recording stops by itself when the user goes quiet (or at 28 s), or on a second tap,
 * and the Sarvam transcript is handed to onText. Language is auto-detected, so people can speak in any
 * Indian language whatever the app is set to.
 */
export function useVoiceInput(onText: (t: string) => void) {
  const recorder = useAudioRecorder({ ...RecordingPresets.HIGH_QUALITY, isMeteringEnabled: true });
  const state = useAudioRecorderState(recorder, 150);
  const [busy, setBusy] = useState(false);
  const level = useRef({ floor: 0, heard: false, lastLoud: 0, startedAt: 0, stopping: false });

  async function start() {
    stopActiveSpeaker?.();
    try {
      const { granted } = await requestRecordingPermissionsAsync();
      if (!granted) return voiceProblem('Allow microphone access to speak.');
      await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
      level.current = { floor: 0, heard: false, lastLoud: Date.now(), startedAt: Date.now(), stopping: false };
    } catch (e: any) {
      voiceProblem(`Could not start the microphone. ${e?.message ?? ''}`);
    }
  }

  async function stop() {
    if (level.current.stopping) return;
    level.current.stopping = true;
    setBusy(true);
    try {
      await recorder.stop();
      await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: false });
      if (!recorder.uri) throw new Error('No recording was saved.');
      const out = await upload<{ transcript: string }>('/assistant/stt', { uri: recorder.uri, name: 'voice.m4a', type: 'audio/mp4' }, { lang: 'auto' });
      if (out.transcript?.trim()) onText(out.transcript.trim());
      else voiceProblem('We could not hear any words. Try again, a little closer to the phone.');
    } catch (e: any) {
      voiceProblem(e?.message ?? 'Could not hear that. Try again.');
    } finally {
      setBusy(false);
    }
  }

  // Auto-stop: learn the room's noise level for the first half second, then stop after a pause in speech.
  useEffect(() => {
    if (!state.isRecording) return;
    const l = level.current;
    const now = Date.now();
    const m = state.metering;
    if (typeof m === 'number') {
      if (now - l.startedAt < 500) l.floor = l.floor === 0 ? m : Math.min(l.floor, m);
      else if (m > l.floor + LOUDER_DB) {
        l.heard = true;
        l.lastLoud = now;
      }
    }
    const quietTooLong = l.heard && now - l.lastLoud > SILENCE_MS;
    if ((quietTooLong || state.durationMillis > MAX_MS) && !l.stopping) setTimeout(stop, 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.isRecording, state.metering, state.durationMillis]);

  return { recording: state.isRecording && !busy, busy, seconds: Math.floor((state.durationMillis ?? 0) / 1000), start, stop };
}

export function MicButton({ onText, size = 48 }: { onText: (t: string) => void; size?: number }) {
  const v = useVoiceInput(onText);
  return (
    <Pressable
      accessibilityLabel={v.recording ? 'Stop recording' : 'Speak'}
      onPress={() => (v.recording ? v.stop() : v.busy ? undefined : v.start())}
      style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: v.recording ? C.red : C.skySoft, alignItems: 'center', justifyContent: 'center' }}>
      {v.busy ? (
        <ActivityIndicator color={C.navy} />
      ) : v.recording ? (
        <Text style={{ color: '#fff', fontWeight: '800', fontSize: 13 }}>{v.seconds}s</Text>
      ) : (
        <Ionicons name="mic" size={size * 0.45} color={C.navy} />
      )}
    </Pressable>
  );
}

/**
 * Speaks text with Sarvam Bulbul. Long text is split into sentences: the first plays as soon as it is ready
 * while the rest are fetched in the background, so playback starts in about 2 seconds whatever the length.
 */
export function useSpeaker() {
  const { lang, ttsSupported } = useApp();
  const player = useAudioPlayer(null);
  const status = useAudioPlayerStatus(player);
  const queue = useRef<string[]>([]);
  const [speaking, setSpeaking] = useState(false);
  const [loading, setLoading] = useState(false);

  function stop() {
    queue.current = [];
    player.pause();
    setSpeaking(false);
    setLoading(false);
  }

  async function speak(text: string) {
    stopActiveSpeaker?.();
    stopActiveSpeaker = stop;
    const voice = ttsSupported ? lang : 'en-IN';
    const urls = speechChunks(text).map((c) => ttsUrl(c, voice));
    if (!urls.length) return;
    urls.slice(1).forEach((u) => fetch(u).catch(() => {})); // warm the server cache for the next sentences
    queue.current = urls.slice(1);
    setSpeaking(true);
    setLoading(true);
    try {
      await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: false });
      player.replace({ uri: urls[0] });
      player.play();
    } catch (e: any) {
      stop();
      voiceProblem(`Could not play this. ${e?.message ?? ''}`);
    }
  }

  // Next sentence when one finishes; done when the queue is empty.
  useEffect(() => {
    const t = setTimeout(() => {
      if (status.playing) setLoading(false);
      if (!status.didJustFinish || !speaking) return;
      const next = queue.current.shift();
      if (next) {
        player.replace({ uri: next });
        player.play();
      } else {
        setSpeaking(false);
      }
    }, 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status.didJustFinish, status.playing]);

  useEffect(() => () => {
    if (stopActiveSpeaker === stop) stopActiveSpeaker = null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { speak, stop, speaking, loading, ttsSupported };
}

/** Plays Sarvam Bulbul speech for a text in the current language. */
export function ListenButton({ text, label = 'Listen' }: { text: string; label?: string }) {
  const s = useSpeaker();
  return (
    <Pressable
      onPress={() => (s.speaking ? s.stop() : s.speak(text))}
      style={{ flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: C.skySoft, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 99, alignSelf: 'flex-start' }}>
      {s.loading ? <ActivityIndicator size="small" color={C.navy} /> : <Ionicons name={s.speaking ? 'stop' : 'volume-high'} size={16} color={C.navy} />}
      <Text style={{ color: C.navy, fontWeight: '700', fontSize: 13 }}>{s.speaking ? 'Stop' : label}</Text>
      {!s.ttsSupported ? <Text style={{ color: C.sub, fontSize: 11 }}>(English voice)</Text> : null}
    </Pressable>
  );
}

export function VoiceHint() {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
      <Ionicons name="mic-outline" size={14} color={C.sub} />
      <Text style={{ color: C.sub, fontSize: 12, flex: 1 }}>Tap the mic and speak in any Indian language. It stops when you pause, and the reply is read out.</Text>
    </View>
  );
}
