/**
 * Life OS dashboard — the map of pillars that "gets filled out".
 */
import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { useNavigation } from '@react-navigation/native';
import { StackNavigationProp } from '@react-navigation/stack';
import { theme } from '../../theme';
import { useLifeOS } from '../../lifeos/store';
import { Pillar } from '../../lifeos/types';
import { LifeOSStackParamList } from '../../navigation/LifeOSNavigator';

type Nav = StackNavigationProp<LifeOSStackParamList, 'LifeOSHome'>;

const journeyProgress = (p: Pillar): { active: number; total: number } => {
  let active = 0;
  p.journeys.forEach((j) => {
    if (j.activeCycleId) active += 1;
  });
  return { active, total: p.journeys.length };
};

export const LifeOSScreen: React.FC = () => {
  const navigation = useNavigation<Nav>();
  const { state } = useLifeOS();

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <Text style={styles.kicker}>YOUR LIFE OS</Text>
        <Text style={styles.title}>The map of your life</Text>
        <Text style={styles.subtitle}>
          Pick a pillar, grow a journey, and let Ora walk it with you.
        </Text>

        <View style={styles.grid}>
          {state.pillars.map((p) => {
            const { active, total } = journeyProgress(p);
            return (
              <TouchableOpacity
                key={p.id}
                style={styles.card}
                activeOpacity={0.85}
                onPress={() => navigation.navigate('Pillar', { pillarId: p.id })}
              >
                <LinearGradient
                  colors={theme.gradients.signature as unknown as string[]}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 1 }}
                  style={styles.iconWrap}
                >
                  <Text style={styles.icon}>{p.emoji}</Text>
                </LinearGradient>
                <Text style={styles.cardTitle}>{p.name}</Text>
                <Text style={styles.cardBlurb} numberOfLines={2}>
                  {p.blurb}
                </Text>
                <View style={styles.cardFooter}>
                  {p.kind === 'structured' && (
                    <View style={styles.pillarTag}>
                      <Text style={styles.pillarTagText}>Pillar</Text>
                    </View>
                  )}
                  <Text style={styles.count}>
                    {total === 0
                      ? 'Empty'
                      : `${total} journey${total === 1 ? '' : 's'}${active ? ` · ${active} active` : ''}`}
                  </Text>
                </View>
              </TouchableOpacity>
            );
          })}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.warmCream },
  content: { padding: theme.spacing.base, paddingBottom: theme.spacing.huge },
  kicker: {
    fontSize: theme.typography.fontSize.tiny,
    fontWeight: theme.typography.fontWeight.bold,
    color: theme.colors.sage,
    letterSpacing: 1.5,
    marginBottom: theme.spacing.xs,
  },
  title: {
    fontSize: theme.typography.fontSize.heroLarge,
    fontWeight: theme.typography.fontWeight.bold,
    color: theme.colors.text,
  },
  subtitle: {
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.textSecondary,
    marginTop: theme.spacing.xs,
    marginBottom: theme.spacing.lg,
    lineHeight: 22,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  card: {
    width: '48%',
    backgroundColor: theme.colors.cardBg,
    borderRadius: theme.borderRadius.lg,
    borderWidth: 1,
    borderColor: theme.colors.borderLight,
    padding: theme.spacing.base,
    marginBottom: theme.spacing.base,
    ...theme.shadows.card,
  },
  iconWrap: {
    width: 48,
    height: 48,
    borderRadius: theme.borderRadius.circle,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: theme.spacing.md,
  },
  icon: { fontSize: 24 },
  cardTitle: {
    fontSize: theme.typography.fontSize.bodyLarge,
    fontWeight: theme.typography.fontWeight.semibold,
    color: theme.colors.text,
    marginBottom: 2,
  },
  cardBlurb: {
    fontSize: theme.typography.fontSize.small,
    color: theme.colors.textSecondary,
    lineHeight: 18,
    minHeight: 36,
  },
  cardFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: theme.spacing.md,
    gap: theme.spacing.sm,
  },
  pillarTag: {
    backgroundColor: theme.colors.weekBadge,
    borderRadius: theme.borderRadius.sm,
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: 2,
  },
  pillarTagText: {
    fontSize: 10,
    fontWeight: theme.typography.fontWeight.bold,
    color: theme.colors.oliveGreen,
  },
  count: {
    fontSize: theme.typography.fontSize.tiny,
    color: theme.colors.textTertiary,
    fontWeight: theme.typography.fontWeight.medium,
  },
});
