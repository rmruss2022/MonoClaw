/**
 * Pillar detail — the journeys (or seeded aspects) inside a pillar. Open pillars
 * let you add your own journey; structured pillars come pre-filled.
 */
import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { StackNavigationProp } from '@react-navigation/stack';
import { theme } from '../../theme';
import { useLifeOS } from '../../lifeos/store';
import { Journey } from '../../lifeos/types';
import { LifeOSStackParamList } from '../../navigation/LifeOSNavigator';

type Nav = StackNavigationProp<LifeOSStackParamList, 'Pillar'>;
type Rt = RouteProp<LifeOSStackParamList, 'Pillar'>;

const summary = (j: Journey): string => {
  const cycle = j.cycles.find((c) => c.id === j.activeCycleId);
  if (cycle) {
    const done = cycle.milestones.filter((m) => m.done).length;
    return `Roadmap ${cycle.number} · ${done}/${cycle.milestones.length} done`;
  }
  const closed = j.cycles.filter((c) => c.status === 'closed').length;
  if (closed > 0) return `${closed} cycle${closed === 1 ? '' : 's'} complete · ready to revamp`;
  if (j.topics.length) return `${j.topics.length} topics · not started`;
  return 'Fresh — build your cloud';
};

export const PillarScreen: React.FC = () => {
  const navigation = useNavigation<Nav>();
  const { params } = useRoute<Rt>();
  const { state, dispatch } = useLifeOS();
  const pillar = state.pillars.find((p) => p.id === params.pillarId);

  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState('');
  const [goal, setGoal] = useState('');

  if (!pillar) {
    return (
      <SafeAreaView style={styles.container}>
        <Text style={styles.missing}>Pillar not found.</Text>
      </SafeAreaView>
    );
  }

  const submit = () => {
    if (!title.trim()) return;
    dispatch({
      type: 'addJourney',
      pillarId: pillar.id,
      title: title.trim(),
      emoji: '✨',
      goal: goal.trim() || 'Grow in this area',
    });
    setTitle('');
    setGoal('');
    setAdding(false);
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.back}>
          <Text style={styles.backText}>← Life OS</Text>
        </TouchableOpacity>

        <View style={styles.header}>
          <View style={[styles.iconWrap, { backgroundColor: pillar.color + '22' }]}>
            <Text style={styles.icon}>{pillar.emoji}</Text>
          </View>
          <View style={styles.headerText}>
            <Text style={styles.title}>{pillar.name}</Text>
            <Text style={styles.blurb}>{pillar.blurb}</Text>
          </View>
        </View>

        {pillar.journeys.map((j) => (
          <TouchableOpacity
            key={j.id}
            style={styles.journeyCard}
            activeOpacity={0.85}
            onPress={() => navigation.navigate('Journey', { journeyId: j.id })}
          >
            <Text style={styles.journeyEmoji}>{j.emoji}</Text>
            <View style={styles.journeyBody}>
              <Text style={styles.journeyTitle}>{j.title}</Text>
              <Text style={styles.journeyGoal} numberOfLines={1}>
                {j.goal}
              </Text>
              <Text style={styles.journeySummary}>{summary(j)}</Text>
            </View>
            <Text style={styles.chevron}>›</Text>
          </TouchableOpacity>
        ))}

        {pillar.journeys.length === 0 && !adding && (
          <Text style={styles.empty}>No journeys yet. Add your first one below.</Text>
        )}

        {pillar.kind === 'open' &&
          (adding ? (
            <View style={styles.addForm}>
              <Text style={styles.addLabel}>New journey</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. Guitar, Running, Spanish…"
                placeholderTextColor={theme.colors.textLight}
                value={title}
                onChangeText={setTitle}
              />
              <TextInput
                style={styles.input}
                placeholder="Where do you want to get to?"
                placeholderTextColor={theme.colors.textLight}
                value={goal}
                onChangeText={setGoal}
              />
              <View style={styles.addActions}>
                <TouchableOpacity onPress={() => setAdding(false)} style={styles.ghostBtn}>
                  <Text style={styles.ghostBtnText}>Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={submit} style={styles.primaryBtn}>
                  <Text style={styles.primaryBtnText}>Create</Text>
                </TouchableOpacity>
              </View>
            </View>
          ) : (
            <TouchableOpacity style={styles.addBtn} onPress={() => setAdding(true)}>
              <Text style={styles.addBtnText}>+ Add a journey</Text>
            </TouchableOpacity>
          ))}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.warmCream },
  content: { padding: theme.spacing.base, paddingBottom: theme.spacing.huge },
  missing: { padding: theme.spacing.xl, color: theme.colors.textSecondary },
  back: { marginBottom: theme.spacing.md },
  backText: {
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.sage,
    fontWeight: theme.typography.fontWeight.semibold,
  },
  header: { flexDirection: 'row', alignItems: 'center', marginBottom: theme.spacing.lg, gap: theme.spacing.md },
  iconWrap: {
    width: 64,
    height: 64,
    borderRadius: theme.borderRadius.circle,
    alignItems: 'center',
    justifyContent: 'center',
  },
  icon: { fontSize: 32 },
  headerText: { flex: 1 },
  title: {
    fontSize: theme.typography.fontSize.hero,
    fontWeight: theme.typography.fontWeight.bold,
    color: theme.colors.text,
  },
  blurb: { fontSize: theme.typography.fontSize.small, color: theme.colors.textSecondary, marginTop: 2 },
  journeyCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.colors.cardBg,
    borderRadius: theme.borderRadius.lg,
    borderWidth: 1,
    borderColor: theme.colors.borderLight,
    padding: theme.spacing.base,
    marginBottom: theme.spacing.md,
    gap: theme.spacing.md,
    ...theme.shadows.card,
  },
  journeyEmoji: { fontSize: 30 },
  journeyBody: { flex: 1 },
  journeyTitle: {
    fontSize: theme.typography.fontSize.bodyLarge,
    fontWeight: theme.typography.fontWeight.semibold,
    color: theme.colors.text,
  },
  journeyGoal: { fontSize: theme.typography.fontSize.small, color: theme.colors.textSecondary, marginTop: 1 },
  journeySummary: {
    fontSize: theme.typography.fontSize.tiny,
    color: theme.colors.sage,
    fontWeight: theme.typography.fontWeight.medium,
    marginTop: theme.spacing.xs,
  },
  chevron: { fontSize: 28, color: theme.colors.textLight },
  empty: {
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.textTertiary,
    textAlign: 'center',
    marginVertical: theme.spacing.lg,
  },
  addBtn: {
    borderWidth: 1.5,
    borderColor: theme.colors.sage,
    borderStyle: 'dashed',
    borderRadius: theme.borderRadius.lg,
    padding: theme.spacing.base,
    alignItems: 'center',
    marginTop: theme.spacing.sm,
  },
  addBtnText: {
    color: theme.colors.sage,
    fontWeight: theme.typography.fontWeight.semibold,
    fontSize: theme.typography.fontSize.body,
  },
  addForm: {
    backgroundColor: theme.colors.cardBg,
    borderRadius: theme.borderRadius.lg,
    borderWidth: 1,
    borderColor: theme.colors.borderLight,
    padding: theme.spacing.base,
    marginTop: theme.spacing.sm,
    ...theme.shadows.card,
  },
  addLabel: {
    fontSize: theme.typography.fontSize.small,
    fontWeight: theme.typography.fontWeight.bold,
    color: theme.colors.textSecondary,
    marginBottom: theme.spacing.sm,
  },
  input: {
    backgroundColor: theme.colors.backgroundLight,
    borderRadius: theme.borderRadius.md,
    borderWidth: 1,
    borderColor: theme.colors.border,
    paddingHorizontal: theme.spacing.base,
    paddingVertical: theme.spacing.md,
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.text,
    marginBottom: theme.spacing.sm,
  },
  addActions: { flexDirection: 'row', justifyContent: 'flex-end', gap: theme.spacing.sm, marginTop: theme.spacing.xs },
  ghostBtn: { paddingHorizontal: theme.spacing.base, paddingVertical: theme.spacing.sm },
  ghostBtnText: { color: theme.colors.textSecondary, fontWeight: theme.typography.fontWeight.semibold },
  primaryBtn: {
    backgroundColor: theme.colors.sage,
    borderRadius: theme.borderRadius.pill,
    paddingHorizontal: theme.spacing.lg,
    paddingVertical: theme.spacing.sm,
  },
  primaryBtnText: { color: theme.colors.warmWhite, fontWeight: theme.typography.fontWeight.semibold },
});
