/**
 * Practice — an agent-guided session for the journey's active roadmap. Ora
 * coaches through the milestones you haven't finished yet.
 */
import React, { useEffect, useRef, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { StackNavigationProp } from '@react-navigation/stack';
import { theme } from '../../theme';
import { useLifeOS } from '../../lifeos/store';
import { ChatMessage } from '../../services/api';
import { CoachContext, openingLine, sendPractice } from '../../lifeos/coach';
import { LifeOSStackParamList } from '../../navigation/LifeOSNavigator';

type Nav = StackNavigationProp<LifeOSStackParamList, 'Practice'>;
type Rt = RouteProp<LifeOSStackParamList, 'Practice'>;

export const PracticeScreen: React.FC = () => {
  const navigation = useNavigation<Nav>();
  const { params } = useRoute<Rt>();
  const { getJourney, getActiveCycle } = useLifeOS();
  const journey = getJourney(params.journeyId);
  const cycle = journey ? getActiveCycle(journey) : undefined;

  const focus = (cycle?.milestones ?? []).filter((m) => !m.done).map((m) => m.title);
  const ctx: CoachContext = {
    journeyTitle: journey?.title ?? 'your journey',
    goal: journey?.goal ?? 'your goal',
    focus: focus.length ? focus : (cycle?.milestones ?? []).map((m) => m.title),
  };

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<ScrollView>(null);

  // Seed the opening coaching line once.
  useEffect(() => {
    setMessages([
      { role: 'assistant', content: openingLine(ctx), timestamp: new Date().toISOString() },
    ]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.journeyId]);

  const send = async (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg: ChatMessage = { role: 'user', content: text, timestamp: new Date().toISOString() };
    const history = [...messages, userMsg];
    setMessages(history);
    setInput('');
    setLoading(true);
    try {
      const reply = await sendPractice(ctx, text, messages);
      setMessages((prev) => [...prev, reply]);
    } finally {
      setLoading(false);
      setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.flex}
      >
        <View style={styles.header}>
          <TouchableOpacity onPress={() => navigation.goBack()}>
            <Text style={styles.backText}>← Roadmap</Text>
          </TouchableOpacity>
          <Text style={styles.title} numberOfLines={1}>
            {journey?.emoji} {journey?.title} · Practice
          </Text>
        </View>

        {ctx.focus.length > 0 && (
          <View style={styles.focusBar}>
            <Text style={styles.focusLabel}>Focus:</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.focusChips}>
              {ctx.focus.map((f) => (
                <View key={f} style={styles.chip}>
                  <Text style={styles.chipText}>{f}</Text>
                </View>
              ))}
            </ScrollView>
          </View>
        )}

        <ScrollView
          ref={scrollRef}
          style={styles.messages}
          contentContainerStyle={styles.messagesContent}
          showsVerticalScrollIndicator={false}
        >
          {messages.map((m, i) => (
            <View
              key={i}
              style={[styles.bubble, m.role === 'user' ? styles.userBubble : styles.aiBubble]}
            >
              <Text style={[styles.bubbleText, m.role === 'user' ? styles.userText : styles.aiText]}>
                {m.content}
              </Text>
            </View>
          ))}
          {loading && (
            <View style={[styles.bubble, styles.aiBubble]}>
              <ActivityIndicator size="small" color={theme.colors.sage} />
            </View>
          )}
        </ScrollView>

        <View style={styles.inputContainer}>
          <View style={styles.inputWrapper}>
            <TextInput
              style={styles.input}
              value={input}
              onChangeText={setInput}
              placeholder="Tell Ora where you're at…"
              placeholderTextColor={theme.colors.textLight}
              multiline
              editable={!loading}
            />
            <TouchableOpacity
              style={[styles.send, (!input.trim() || loading) && styles.sendDisabled]}
              onPress={() => send(input)}
              disabled={!input.trim() || loading}
            >
              <Text style={styles.sendText}>↑</Text>
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.colors.warmCream },
  flex: { flex: 1 },
  header: {
    paddingHorizontal: theme.spacing.base,
    paddingVertical: theme.spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.borderLight,
    backgroundColor: theme.colors.warmWhite,
    gap: 2,
  },
  backText: { fontSize: theme.typography.fontSize.small, color: theme.colors.sage, fontWeight: theme.typography.fontWeight.semibold },
  title: { fontSize: theme.typography.fontSize.bodyLarge, fontWeight: theme.typography.fontWeight.bold, color: theme.colors.text },

  focusBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: theme.spacing.base,
    paddingVertical: theme.spacing.sm,
    gap: theme.spacing.sm,
    backgroundColor: theme.colors.backgroundLight,
  },
  focusLabel: { fontSize: theme.typography.fontSize.tiny, color: theme.colors.textTertiary, fontWeight: theme.typography.fontWeight.bold },
  focusChips: { gap: theme.spacing.sm, paddingRight: theme.spacing.base },
  chip: { backgroundColor: theme.colors.weekBadge, borderRadius: theme.borderRadius.pill, paddingHorizontal: theme.spacing.md, paddingVertical: 4 },
  chipText: { fontSize: theme.typography.fontSize.tiny, color: theme.colors.oliveGreen, fontWeight: theme.typography.fontWeight.semibold },

  messages: { flex: 1 },
  messagesContent: { padding: theme.spacing.base },
  bubble: { maxWidth: '85%', padding: theme.spacing.base, borderRadius: theme.borderRadius.lg, marginBottom: theme.spacing.md },
  userBubble: { alignSelf: 'flex-end', backgroundColor: theme.colors.sage, borderBottomRightRadius: theme.borderRadius.xs },
  aiBubble: { alignSelf: 'flex-start', backgroundColor: theme.colors.cardBg, borderWidth: 1, borderColor: theme.colors.borderLight, borderBottomLeftRadius: theme.borderRadius.xs },
  bubbleText: { fontSize: theme.typography.fontSize.body, lineHeight: 22 },
  userText: { color: theme.colors.warmWhite },
  aiText: { color: theme.colors.text },

  inputContainer: { padding: theme.spacing.base, backgroundColor: theme.colors.warmWhite, borderTopWidth: 1, borderTopColor: theme.colors.borderLight },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: theme.colors.cardBg,
    borderRadius: theme.borderRadius.xxl,
    borderWidth: 1,
    borderColor: theme.colors.border,
    paddingHorizontal: theme.spacing.base,
    paddingVertical: theme.spacing.sm,
  },
  input: { flex: 1, fontSize: theme.typography.fontSize.body, color: theme.colors.text, maxHeight: 100, paddingTop: theme.spacing.xs },
  send: { width: 32, height: 32, borderRadius: theme.borderRadius.circle, backgroundColor: theme.colors.sage, alignItems: 'center', justifyContent: 'center', marginLeft: theme.spacing.sm },
  sendDisabled: { backgroundColor: theme.colors.borderLight, opacity: 0.5 },
  sendText: { fontSize: 20, color: theme.colors.warmWhite, fontWeight: theme.typography.fontWeight.bold },
});
