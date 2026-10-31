import { Image } from 'react-native';

const SOURCE = require('../../assets/images/assistant-avatar.png');

export function AssistantAvatar({ size = 40 }: { size?: number }) {
  return <Image source={SOURCE} accessibilityLabel="Claimezy assistant" style={{ width: size, height: size, borderRadius: size * 0.24 }} />;
}
