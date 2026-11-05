/**
 * TopicCloud — a constellation of topic bubbles around a central goal core.
 *
 * Tap a bubble to select/deselect it for the roadmap. Bubble size reflects the
 * topic's weight; color reflects its status. Positions are computed
 * deterministically (rings + gentle jitter) so the layout is stable across
 * renders without any layout library. Gradients mirror the app's signature
 * lavender→pink aurora system.
 */
import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Dimensions } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { theme } from '../theme';
import { Topic } from './types';

const CANVAS_H = 380;
const H_PADDING = theme.spacing.base * 2;

interface TopicCloudProps {
  topics: Topic[];
  centerEmoji: string;
  centerLabel: string;
  accent: string;
  onToggle: (topicId: string) => void;
}

const bubbleSize = (weight: number) => 52 + weight * 9; // w1=61, w2=70, w3=79

// Gradient fill per status (null = plain white bubble).
const gradientFor = (status: Topic['status']): readonly string[] | null => {
  switch (status) {
    case 'selected':
      return theme.gradients.pink;
    case 'in_progress':
      return theme.gradients.purple;
    case 'done':
      return theme.gradients.purple;
    default:
      return null;
  }
};

const borderFor = (status: Topic['status']) => {
  switch (status) {
    case 'selected':
      return theme.colors.mutedGold;
    case 'in_progress':
    case 'done':
      return theme.colors.sage;
    default:
      return theme.colors.border;
  }
};

export const TopicCloud: React.FC<TopicCloudProps> = ({
  topics,
  centerEmoji,
  centerLabel,
  accent,
  onToggle,
}) => {
  const width = Dimensions.get('window').width - H_PADDING;
  const cx = width / 2;
  const cy = CANVAS_H / 2;

  const n = topics.length;
  const innerCount = Math.min(n, n <= 6 ? n : Math.ceil(n / 2));
  const rInner = Math.min(width, CANVAS_H) * 0.32;
  const rOuter = Math.min(width, CANVAS_H) * 0.46;

  return (
    <View style={[styles.canvas, { width, height: CANVAS_H }]}>
      {/* Center goal core — signature lavender→pink gradient */}
      <View style={[styles.coreWrap, { left: cx - 46, top: cy - 46, borderColor: accent }]}>
        <LinearGradient
          colors={theme.gradients.signature as unknown as string[]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.coreFill}
        >
          <Text style={styles.coreEmoji}>{centerEmoji}</Text>
          <Text style={styles.coreLabel} numberOfLines={2}>
            {centerLabel}
          </Text>
        </LinearGradient>
      </View>

      {topics.map((topic, i) => {
        const onInner = i < innerCount;
        const ringCount = onInner ? innerCount : Math.max(1, n - innerCount);
        const ringIndex = onInner ? i : i - innerCount;
        const radius = onInner ? rInner : rOuter;
        const angleOffset = onInner ? -Math.PI / 2 : -Math.PI / 2 + Math.PI / ringCount;
        const angle = angleOffset + (ringCount === 1 ? 0 : (2 * Math.PI * ringIndex) / ringCount);
        const jitter = Math.sin(i * 1.7) * 8;

        const size = bubbleSize(topic.weight);
        const x = cx + radius * Math.cos(angle) - size / 2;
        const y = cy + (radius + jitter) * Math.sin(angle) - size / 2;
        const grad = gradientFor(topic.status);
        const isPlain = grad === null;
        const textColor = isPlain ? theme.colors.textSecondary : theme.colors.warmWhite;

        return (
          <TouchableOpacity
            key={topic.id}
            activeOpacity={0.8}
            onPress={() => onToggle(topic.id)}
            style={[
              styles.bubble,
              {
                width: size,
                height: size,
                borderRadius: size / 2,
                left: Math.max(0, Math.min(width - size, x)),
                top: Math.max(0, Math.min(CANVAS_H - size, y)),
                backgroundColor: isPlain ? theme.colors.warmWhite : 'transparent',
                borderColor: borderFor(topic.status),
              },
            ]}
          >
            {grad && (
              <LinearGradient
                colors={grad as unknown as string[]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
                style={[StyleSheet.absoluteFillObject, { borderRadius: size / 2 }]}
              />
            )}
            {topic.status === 'done' && <Text style={styles.check}>✓</Text>}
            <Text style={[styles.bubbleText, { color: textColor }]} numberOfLines={3}>
              {topic.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
};

const styles = StyleSheet.create({
  canvas: {
    alignSelf: 'center',
    position: 'relative',
    marginVertical: theme.spacing.sm,
  },
  coreWrap: {
    position: 'absolute',
    width: 92,
    height: 92,
    borderRadius: 46,
    borderWidth: 2,
    overflow: 'hidden',
    zIndex: 2,
    ...theme.shadows.medium,
  },
  coreFill: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: theme.spacing.xs,
  },
  coreEmoji: {
    fontSize: 26,
    marginBottom: 2,
  },
  coreLabel: {
    fontSize: 10,
    fontWeight: theme.typography.fontWeight.semibold,
    color: theme.colors.text,
    textAlign: 'center',
  },
  bubble: {
    position: 'absolute',
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 6,
    overflow: 'hidden',
    ...theme.shadows.small,
  },
  bubbleText: {
    fontSize: 11,
    fontWeight: theme.typography.fontWeight.semibold,
    textAlign: 'center',
  },
  check: {
    position: 'absolute',
    top: 6,
    right: 8,
    fontSize: 12,
    color: theme.colors.warmWhite,
    fontWeight: theme.typography.fontWeight.bold,
  },
});
