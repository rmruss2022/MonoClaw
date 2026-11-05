/**
 * Journey detail — the heart of Life OS.
 *
 *  • Cloud tab: pick topics from the constellation, add your own, then build a
 *    roadmap from your picks.
 *  • Roadmap tab: work the milestones, practice each with Ora, then close the
 *    cycle with a reflection and revamp for another pass.
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
import { LinearGradient } from 'expo-linear-gradient';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { StackNavigationProp } from '@react-navigation/stack';
import { theme } from '../../theme';

const gradFill = { ...StyleSheet.absoluteFillObject } as const;
import { useLifeOS } from '../../lifeos/store';
import { TopicCloud } from '../../lifeos/TopicCloud';
import { LifeOSStackParamList } from '../../navigation/LifeOSNavigator';

type Nav = StackNavigationProp<LifeOSStackParamList, 'Journey'>;
type Rt = RouteProp<LifeOSStackParamList, 'Journey'>;

export const JourneyScreen: React.FC = () => {
  const navigation = useNavigation<Nav>();
  const { params } = useRoute<Rt>();
  const { getJourney, getActiveCycle, state, dispatch } = useLifeOS();
  const journey = getJourney(params.journeyId);

  const [tab, setTab] = useState<'cloud' | 'roadmap'>('cloud');
  const [newTopic, setNewTopic] = useState('');
  const [closing, setClosing] = useState(false);
  const [reflection, setReflection] = useState('');

  if (!journey) {
    return (
      <SafeAreaView style={styles.container}>
        <Text style={styles.missing}>Journey not found.</Text>
      </SafeAreaView>
    );
  }

  const pillar = state.pillars.find((p) => p.id === journey.pillarId);
  const accent = pillar?.color ?? theme.colors.sage;
  const cycle = getActiveCycle(journey);
  const selectedCount = journey.topics.filter((t) => t.status === 'selected').length;
  const closedCycles = journey.cycles.filter((c) => c.status === 'closed');

  const addTopic = () => {
    if (!newTopic.trim()) return;
    dispatch({ type: 'addTopic', journeyId: journey.id, label: newTopic.trim() });
    setNewTopic('');
  };

  const build = () => {
    dispatch({ type: 'buildRoadmap', journeyId: journey.id });
    setTab('roadmap');
  };

  const closeCycle = () => {
    dispatch({ type: 'closeCycle', journeyId: journey.id, reflection: reflection.trim() });
    setReflection('');
    setClosing(false);
    setTab('cloud');
  };

  const doneCount = cycle ? cycle.milestones.filter((m) => m.done).length : 0;
  const progress = cycle && cycle.milestones.length ? doneCount / cycle.milestones.length : 0;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.back}>
          <Text style={styles.backText}>← Back</Text>
        </TouchableOpacity>

        <View style={styles.header}>
          <Text style={styles.emoji}>{journey.emoji}</Text>
          <View style={styles.headerText}>
            <Text style={styles.title}>{journey.title}</Text>
            <Text style={styles.goal}>🎯 {journey.goal}</Text>
          </View>
        </View>

        {/* Segmented control */}
        <View style={styles.segment}>
          {(['cloud', 'roadmap'] as const).map((t) => (
            <TouchableOpacity
              key={t}
              style={[styles.segmentBtn, tab === t && styles.segmentBtnActive]}
              onPress={() => setTab(t)}
            >
              <Text style={[styles.segmentText, tab === t && styles.segmentTextActive]}>
                {t === 'cloud' ? 'Topic Cloud' : 'Roadmap'}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {tab === 'cloud' ? (
          <>
            <Text style={styles.hint}>
              {cycle
                ? 'These topics are in your active roadmap. Revamp the cycle to pick a new set.'
                : 'Tap topics you want to work on, then build a roadmap from your picks.'}
            </Text>

            <TopicCloud
              topics={journey.topics}
              centerEmoji={journey.emoji}
              centerLabel={journey.title}
              accent={accent}
              onToggle={(topicId) =>
                dispatch({ type: 'toggleTopic', journeyId: journey.id, topicId })
              }
            />

            <View style={styles.addTopicRow}>
              <TextInput
                style={styles.topicInput}
                placeholder="Add a topic…"
                placeholderTextColor={theme.colors.textLight}
                value={newTopic}
                onChangeText={setNewTopic}
                onSubmitEditing={addTopic}
                returnKeyType="done"
              />
              <TouchableOpacity style={styles.addTopicBtn} onPress={addTopic}>
                <Text style={styles.addTopicBtnText}>+</Text>
              </TouchableOpacity>
            </View>

            {!cycle && (
              <TouchableOpacity
                style={[styles.cta, selectedCount === 0 && styles.ctaDisabled]}
                disabled={selectedCount === 0}
                onPress={build}
              >
                {selectedCount > 0 && (
                  <LinearGradient colors={theme.gradients.purple as unknown as string[]}
                    start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={gradFill} />
                )}
                <Text style={styles.ctaText}>
                  {selectedCount === 0
                    ? 'Pick topics to build a roadmap'
                    : `Build roadmap from ${selectedCount} pick${selectedCount === 1 ? '' : 's'} →`}
                </Text>
              </TouchableOpacity>
            )}
          </>
        ) : (
          <>
            {cycle ? (
              <>
                <View style={styles.progressHeader}>
                  <Text style={styles.roadmapTitle}>Roadmap · Cycle {cycle.number}</Text>
                  <Text style={styles.progressText}>
                    {doneCount}/{cycle.milestones.length}
                  </Text>
                </View>
                <View style={styles.progressTrack}>
                  <View style={[styles.progressFill, { width: `${progress * 100}%`, backgroundColor: accent }]} />
                </View>

                {cycle.milestones.map((m, i) => (
                  <View key={m.id} style={styles.milestone}>
                    <TouchableOpacity
                      style={[styles.checkbox, m.done && { backgroundColor: accent, borderColor: accent }]}
                      onPress={() =>
                        dispatch({ type: 'toggleMilestone', journeyId: journey.id, milestoneId: m.id })
                      }
                    >
                      {m.done && <Text style={styles.checkboxTick}>✓</Text>}
                    </TouchableOpacity>
                    <View style={styles.milestoneBody}>
                      <Text style={[styles.milestoneTitle, m.done && styles.milestoneDone]}>
                        {i + 1}. {m.title}
                      </Text>
                      {!!m.notes && <Text style={styles.milestoneNotes}>{m.notes}</Text>}
                    </View>
                  </View>
                ))}

                <TouchableOpacity
                  style={styles.practiceBtn}
                  onPress={() => navigation.navigate('Practice', { journeyId: journey.id })}
                >
                  <LinearGradient colors={theme.gradients.signature as unknown as string[]}
                    start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={gradFill} />
                  <Text style={styles.practiceBtnText}>✨ Practice with Ora</Text>
                </TouchableOpacity>

                {closing ? (
                  <View style={styles.closeForm}>
                    <Text style={styles.addLabel}>Close out — what shifted this cycle?</Text>
                    <TextInput
                      style={[styles.topicInput, styles.reflectionInput]}
                      placeholder="A sentence of reflection…"
                      placeholderTextColor={theme.colors.textLight}
                      value={reflection}
                      onChangeText={setReflection}
                      multiline
                    />
                    <View style={styles.addActions}>
                      <TouchableOpacity onPress={() => setClosing(false)} style={styles.ghostBtn}>
                        <Text style={styles.ghostBtnText}>Not yet</Text>
                      </TouchableOpacity>
                      <TouchableOpacity onPress={closeCycle} style={styles.primaryBtn}>
                        <Text style={styles.primaryBtnText}>Close cycle</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ) : (
                  <TouchableOpacity style={styles.closeBtn} onPress={() => setClosing(true)}>
                    <Text style={styles.closeBtnText}>Close out this cycle</Text>
                  </TouchableOpacity>
                )}
              </>
            ) : (
              <View style={styles.emptyRoadmap}>
                <Text style={styles.emptyRoadmapText}>
                  {closedCycles.length
                    ? 'This cycle is complete. Revamp to pick a fresh set of topics and go again.'
                    : 'No active roadmap yet. Head to the Topic Cloud and pick what to work on.'}
                </Text>
                {closedCycles.length > 0 && (
                  <TouchableOpacity
                    style={styles.cta}
                    onPress={() => {
                      dispatch({ type: 'revamp', journeyId: journey.id });
                      setTab('cloud');
                    }}
                  >
                    <LinearGradient colors={theme.gradients.purple as unknown as string[]}
                      start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={gradFill} />
                    <Text style={styles.ctaText}>🔄 Revamp & go again</Text>
                  </TouchableOpacity>
                )}
              </View>
            )}

            {/* History of closed cycles */}
            {closedCycles.length > 0 && (
              <View style={styles.history}>
                <Text style={styles.historyTitle}>Past cycles</Text>
                {closedCycles.map((c) => (
                  <View key={c.id} style={styles.historyItem}>
                    <Text style={styles.historyCycle}>Cycle {c.number}</Text>
                    <Text style={styles.historyMeta}>
                      {c.milestones.filter((m) => m.done).length}/{c.milestones.length} completed
                    </Text>
                    {!!c.reflection && <Text style={styles.historyReflection}>“{c.reflection}”</Text>}
                  </View>
                ))}
              </View>
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.warmCream },
  content: { padding: theme.spacing.base, paddingBottom: theme.spacing.huge },
  missing: { padding: theme.spacing.xl, color: theme.colors.textSecondary },
  back: { marginBottom: theme.spacing.sm },
  backText: {
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.sage,
    fontWeight: theme.typography.fontWeight.semibold,
  },
  header: { flexDirection: 'row', alignItems: 'center', gap: theme.spacing.md, marginBottom: theme.spacing.base },
  emoji: { fontSize: 40 },
  headerText: { flex: 1 },
  title: {
    fontSize: theme.typography.fontSize.hero,
    fontWeight: theme.typography.fontWeight.bold,
    color: theme.colors.text,
  },
  goal: { fontSize: theme.typography.fontSize.small, color: theme.colors.textSecondary, marginTop: 2 },

  segment: {
    flexDirection: 'row',
    backgroundColor: theme.colors.warmBeige,
    borderRadius: theme.borderRadius.pill,
    padding: 4,
    marginBottom: theme.spacing.base,
  },
  segmentBtn: { flex: 1, paddingVertical: theme.spacing.sm, borderRadius: theme.borderRadius.pill, alignItems: 'center' },
  segmentBtnActive: { backgroundColor: theme.colors.cardBg, ...theme.shadows.small },
  segmentText: { fontSize: theme.typography.fontSize.small, color: theme.colors.textSecondary, fontWeight: theme.typography.fontWeight.semibold },
  segmentTextActive: { color: theme.colors.text },

  hint: {
    fontSize: theme.typography.fontSize.small,
    color: theme.colors.textTertiary,
    textAlign: 'center',
    marginBottom: theme.spacing.xs,
    lineHeight: 18,
  },

  addTopicRow: { flexDirection: 'row', gap: theme.spacing.sm, marginTop: theme.spacing.sm },
  topicInput: {
    flex: 1,
    backgroundColor: theme.colors.cardBg,
    borderRadius: theme.borderRadius.md,
    borderWidth: 1,
    borderColor: theme.colors.border,
    paddingHorizontal: theme.spacing.base,
    paddingVertical: theme.spacing.md,
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.text,
  },
  addTopicBtn: {
    width: 48,
    borderRadius: theme.borderRadius.md,
    backgroundColor: theme.colors.sage,
    alignItems: 'center',
    justifyContent: 'center',
  },
  addTopicBtnText: { fontSize: 24, color: theme.colors.warmWhite, fontWeight: theme.typography.fontWeight.bold },

  cta: {
    backgroundColor: theme.colors.sage,
    borderRadius: theme.borderRadius.pill,
    paddingVertical: theme.spacing.base,
    alignItems: 'center',
    marginTop: theme.spacing.base,
    overflow: 'hidden',
    ...theme.shadows.small,
  },
  ctaDisabled: { backgroundColor: theme.colors.inactive },
  ctaText: { color: theme.colors.warmWhite, fontWeight: theme.typography.fontWeight.bold, fontSize: theme.typography.fontSize.body },

  progressHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: theme.spacing.sm },
  roadmapTitle: { fontSize: theme.typography.fontSize.heading, fontWeight: theme.typography.fontWeight.semibold, color: theme.colors.text },
  progressText: { fontSize: theme.typography.fontSize.body, fontWeight: theme.typography.fontWeight.bold, color: theme.colors.sage },
  progressTrack: {
    height: 8,
    borderRadius: 4,
    backgroundColor: theme.colors.warmBeige,
    overflow: 'hidden',
    marginBottom: theme.spacing.base,
  },
  progressFill: { height: '100%', borderRadius: 4 },

  milestone: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: theme.colors.cardBg,
    borderRadius: theme.borderRadius.md,
    borderWidth: 1,
    borderColor: theme.colors.borderLight,
    padding: theme.spacing.base,
    marginBottom: theme.spacing.sm,
    gap: theme.spacing.md,
  },
  checkbox: {
    width: 26,
    height: 26,
    borderRadius: theme.borderRadius.circle,
    borderWidth: 2,
    borderColor: theme.colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  checkboxTick: { color: theme.colors.warmWhite, fontSize: 14, fontWeight: theme.typography.fontWeight.bold },
  milestoneBody: { flex: 1 },
  milestoneTitle: { fontSize: theme.typography.fontSize.body, color: theme.colors.text, fontWeight: theme.typography.fontWeight.medium },
  milestoneDone: { textDecorationLine: 'line-through', color: theme.colors.textTertiary },
  milestoneNotes: { fontSize: theme.typography.fontSize.small, color: theme.colors.textSecondary, marginTop: theme.spacing.xs, fontStyle: 'italic' },

  practiceBtn: {
    backgroundColor: theme.colors.mutedGold,
    borderRadius: theme.borderRadius.pill,
    paddingVertical: theme.spacing.base,
    alignItems: 'center',
    marginTop: theme.spacing.md,
    overflow: 'hidden',
    ...theme.shadows.small,
  },
  practiceBtnText: { color: theme.colors.text, fontWeight: theme.typography.fontWeight.bold, fontSize: theme.typography.fontSize.body },

  closeBtn: { alignItems: 'center', paddingVertical: theme.spacing.base, marginTop: theme.spacing.sm },
  closeBtnText: { color: theme.colors.textSecondary, fontWeight: theme.typography.fontWeight.semibold, textDecorationLine: 'underline' },
  closeForm: {
    backgroundColor: theme.colors.cardBg,
    borderRadius: theme.borderRadius.lg,
    borderWidth: 1,
    borderColor: theme.colors.borderLight,
    padding: theme.spacing.base,
    marginTop: theme.spacing.md,
    ...theme.shadows.card,
  },
  reflectionInput: { minHeight: 64, textAlignVertical: 'top' },
  addLabel: { fontSize: theme.typography.fontSize.small, fontWeight: theme.typography.fontWeight.bold, color: theme.colors.textSecondary, marginBottom: theme.spacing.sm },
  addActions: { flexDirection: 'row', justifyContent: 'flex-end', gap: theme.spacing.sm, marginTop: theme.spacing.sm },
  ghostBtn: { paddingHorizontal: theme.spacing.base, paddingVertical: theme.spacing.sm },
  ghostBtnText: { color: theme.colors.textSecondary, fontWeight: theme.typography.fontWeight.semibold },
  primaryBtn: { backgroundColor: theme.colors.sage, borderRadius: theme.borderRadius.pill, paddingHorizontal: theme.spacing.lg, paddingVertical: theme.spacing.sm },
  primaryBtnText: { color: theme.colors.warmWhite, fontWeight: theme.typography.fontWeight.semibold },

  emptyRoadmap: { alignItems: 'center', paddingVertical: theme.spacing.lg },
  emptyRoadmapText: {
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.textTertiary,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: theme.spacing.base,
  },

  history: { marginTop: theme.spacing.xl },
  historyTitle: { fontSize: theme.typography.fontSize.small, fontWeight: theme.typography.fontWeight.bold, color: theme.colors.textSecondary, marginBottom: theme.spacing.sm, textTransform: 'uppercase', letterSpacing: 0.5 },
  historyItem: {
    backgroundColor: theme.colors.backgroundLight,
    borderRadius: theme.borderRadius.md,
    padding: theme.spacing.md,
    marginBottom: theme.spacing.sm,
  },
  historyCycle: { fontSize: theme.typography.fontSize.body, fontWeight: theme.typography.fontWeight.semibold, color: theme.colors.text },
  historyMeta: { fontSize: theme.typography.fontSize.small, color: theme.colors.textSecondary, marginTop: 1 },
  historyReflection: { fontSize: theme.typography.fontSize.small, color: theme.colors.textSecondary, fontStyle: 'italic', marginTop: theme.spacing.xs },
});
