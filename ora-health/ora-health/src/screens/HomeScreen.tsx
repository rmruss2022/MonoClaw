import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ImageBackground,
  TouchableOpacity,
  Dimensions,
} from 'react-native';
import { theme } from '../theme';
import BottomNav from '../components/BottomNav';

const { width } = Dimensions.get('window');

export function HomeScreen() {
  const userName = 'Matt';
  const currentWeek = 5;
  const currentDay = 3;
  const totalDays = 7;
  const streakDays = 7;
  const totalPoints = 20;
  const xpPoints = 100;

  return (
    <View style={styles.container}>
      <ScrollView 
        style={styles.scrollView}
        showsVerticalScrollIndicator={false}
        bounces={true}
      >
        {/* Hero Section with Mediterranean Architecture */}
        <ImageBackground
          source={{ uri: 'https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=800' }}
          style={styles.hero}
          imageStyle={styles.heroImage}
        >
          <View style={styles.heroOverlay}>
            <View style={styles.header}>
              <Text style={styles.greeting}>Hi {userName}</Text>
              <View style={styles.badges}>
                <View style={styles.badge}>
                  <Text style={styles.badgeEmoji}>🔥</Text>
                  <Text style={styles.badgeText}>{streakDays}</Text>
                </View>
                <View style={styles.badge}>
                  <Text style={styles.badgeEmoji}>🏆</Text>
                  <Text style={styles.badgeText}>{totalPoints}</Text>
                </View>
              </View>
            </View>
          </View>
        </ImageBackground>

        {/* Content Cards */}
        <View style={styles.content}>
          {/* Self Compassion Card */}
          <View style={styles.compassionCard}>
            <View style={styles.compassionHeader}>
              <View style={styles.compassionTitleRow}>
                <View style={styles.medallion}>
                  <Text style={styles.medallionEmoji}>🧘</Text>
                </View>
                <View style={styles.compassionTitleContainer}>
                  <Text style={styles.compassionTitle}>Self Compassion</Text>
                  <Text style={styles.compassionSubtitle}>Day {currentDay}/{totalDays}</Text>
                </View>
              </View>
              <View style={styles.weekBadge}>
                <Text style={styles.weekBadgeText}>Week {currentWeek}</Text>
              </View>
            </View>

            {/* Affirmation */}
            <View style={styles.affirmationContainer}>
              <View style={styles.affirmationTag}>
                <Text style={styles.affirmationTagText}>Today's Affirmation</Text>
              </View>
              <Text style={styles.affirmationText}>I am kind to myself</Text>
              <Text style={styles.affirmationBody}>
                I embrace my journey with compassion, knowing I am enough as I am.
              </Text>
            </View>

            {/* Pagination */}
            <View style={styles.pagination}>
              <View style={[styles.dot, styles.dotActive]} />
              <View style={styles.dot} />
              <View style={styles.dot} />
            </View>
          </View>

          {/* Meditation Section */}
          <View style={styles.meditationCard}>
            <ImageBackground
              source={{ uri: 'https://images.unsplash.com/photo-1506126613408-eca07ce68773?w=800' }}
              style={styles.meditationImage}
              imageStyle={styles.meditationImageStyle}
            >
              <View style={styles.meditationOverlay}>
                <View style={styles.meditationContent}>
                  <View style={styles.meditationIcon}>
                    <Text style={styles.meditationIconText}>🧘</Text>
                  </View>
                  <Text style={styles.meditationTitle}>Meditation for today</Text>
                  <Text style={styles.meditationSubtitle}>Take a moment to center yourself</Text>
                  <View style={styles.xpBadge}>
                    <Text style={styles.xpBadgeText}>XP {xpPoints}</Text>
                  </View>
                </View>
              </View>
            </ImageBackground>
          </View>

          {/* Action Cards Row */}
          <View style={styles.actionCardsRow}>
            <TouchableOpacity style={styles.actionCard}>
              <ImageBackground
                source={{ uri: 'https://images.unsplash.com/photo-1506784983877-45594efa4cbe?w=400' }}
                style={styles.actionCardImage}
                imageStyle={styles.actionCardImageStyle}
              >
                <View style={styles.actionCardOverlay}>
                  <Text style={styles.actionCardTitle}>Plan your week</Text>
                  <View style={styles.actionCardArrow}>
                    <Text style={styles.actionCardArrowText}>→</Text>
                  </View>
                </View>
              </ImageBackground>
            </TouchableOpacity>

            <TouchableOpacity style={styles.actionCard}>
              <ImageBackground
                source={{ uri: 'https://images.unsplash.com/photo-1545389336-cf090694435e?w=400' }}
                style={styles.actionCardImage}
                imageStyle={styles.actionCardImageStyle}
              >
                <View style={styles.actionCardOverlay}>
                  <Text style={styles.actionCardTitle}>Workshops</Text>
                  <View style={styles.actionCardArrow}>
                    <Text style={styles.actionCardArrowText}>→</Text>
                  </View>
                </View>
              </ImageBackground>
            </TouchableOpacity>
          </View>

          {/* 7 Days Streak Card */}
          <View style={styles.streakCard}>
            <View style={styles.streakHeader}>
              <Text style={styles.streakTitle}>{streakDays} days streak</Text>
              <TouchableOpacity>
                <Text style={styles.viewHistoryLink}>View history</Text>
              </TouchableOpacity>
            </View>
            <Text style={styles.streakSubtitle}>Way to go {userName}</Text>
            
            <View style={styles.calendar}>
              <Text style={styles.calendarMonth}>Jan '25</Text>
              <View style={styles.calendarGrid}>
                {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day, index) => (
                  <View key={day} style={styles.calendarDay}>
                    <Text style={styles.calendarDayLabel}>{day}</Text>
                    <View style={[
                      styles.calendarDayCircle,
                      index < 3 && styles.calendarDayComplete,
                      index === 3 && styles.calendarDayToday,
                    ]}>
                      <Text style={[
                        styles.calendarDayNumber,
                        index < 3 && styles.calendarDayNumberComplete,
                      ]}>
                        {15 + index}
                      </Text>
                    </View>
                  </View>
                ))}
              </View>
            </View>
          </View>
        </View>
      </ScrollView>
      <BottomNav activeTab="Home" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.warmCream,
  },
  scrollView: {
    flex: 1,
  },
  
  // Hero
  hero: {
    height: 320,
    width: '100%',
  },
  heroImage: {
    borderBottomLeftRadius: theme.borderRadius.xl,
    borderBottomRightRadius: theme.borderRadius.xl,
  },
  heroOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.15)',
    borderBottomLeftRadius: theme.borderRadius.xl,
    borderBottomRightRadius: theme.borderRadius.xl,
    padding: theme.spacing.base,
    paddingTop: theme.spacing.md,
  },
  
  // Header
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  greeting: {
    fontSize: theme.typography.fontSize.heroLarge,
    fontWeight: '600',
    color: theme.colors.warmWhite,
  },
  badges: {
    flexDirection: 'row',
    gap: theme.spacing.sm,
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.colors.warmWhite,
    borderRadius: theme.borderRadius.pill,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.xs,
    gap: theme.spacing.xs,
  },
  badgeEmoji: {
    fontSize: 16,
  },
  badgeText: {
    fontSize: theme.typography.fontSize.body,
    fontWeight: '600',
    color: theme.colors.text,
  },
  
  // Content
  content: {
    paddingHorizontal: theme.spacing.base,
    marginTop: -theme.spacing.huge,
    paddingBottom: theme.spacing.huge,
  },
  
  // Compassion Card
  compassionCard: {
    backgroundColor: theme.colors.cardBg,
    borderRadius: theme.borderRadius.xl,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.base,
    ...theme.shadows.large,
  },
  compassionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: theme.spacing.lg,
  },
  compassionTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: theme.spacing.md,
  },
  medallion: {
    width: 56,
    height: 56,
    borderRadius: theme.borderRadius.circle,
    backgroundColor: theme.colors.backgroundLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  medallionEmoji: {
    fontSize: 28,
  },
  compassionTitleContainer: {
    flex: 1,
  },
  compassionTitle: {
    fontSize: theme.typography.fontSize.heading,
    fontWeight: '600',
    color: theme.colors.text,
    marginBottom: 2,
  },
  compassionSubtitle: {
    fontSize: theme.typography.fontSize.small,
    color: theme.colors.textSecondary,
  },
  weekBadge: {
    backgroundColor: theme.colors.mutedGold,
    borderRadius: theme.borderRadius.md,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.xs,
  },
  weekBadgeText: {
    fontSize: theme.typography.fontSize.small,
    fontWeight: '600',
    color: theme.colors.warmWhite,
  },
  
  // Affirmation
  affirmationContainer: {
    backgroundColor: theme.colors.warmBeige,
    borderRadius: theme.borderRadius.lg,
    padding: theme.spacing.base,
    marginBottom: theme.spacing.base,
  },
  affirmationTag: {
    backgroundColor: theme.colors.mutedGold,
    alignSelf: 'flex-start',
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.xs,
    borderRadius: theme.borderRadius.sm,
    marginBottom: theme.spacing.md,
  },
  affirmationTagText: {
    fontSize: theme.typography.fontSize.tiny,
    fontWeight: '600',
    color: theme.colors.warmWhite,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  affirmationText: {
    fontSize: theme.typography.fontSize.heading,
    fontWeight: '600',
    color: theme.colors.text,
    marginBottom: theme.spacing.sm,
  },
  affirmationBody: {
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.textSecondary,
    lineHeight: 22,
  },
  
  // Pagination
  pagination: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: theme.spacing.xs,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: theme.borderRadius.circle,
    backgroundColor: theme.colors.inactive,
  },
  dotActive: {
    backgroundColor: theme.colors.sage,
    width: 20,
  },
  
  // Meditation
  meditationCard: {
    marginBottom: theme.spacing.base,
    borderRadius: theme.borderRadius.xl,
    overflow: 'hidden',
    ...theme.shadows.medium,
  },
  meditationImage: {
    height: 280,
  },
  meditationImageStyle: {
    borderRadius: theme.borderRadius.xl,
  },
  meditationOverlay: {
    flex: 1,
    backgroundColor: 'rgba(139, 154, 107, 0.2)',
    justifyContent: 'flex-end',
    padding: theme.spacing.lg,
  },
  meditationContent: {
    alignItems: 'flex-start',
  },
  meditationIcon: {
    width: 48,
    height: 48,
    borderRadius: theme.borderRadius.circle,
    backgroundColor: theme.colors.warmWhite,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: theme.spacing.sm,
  },
  meditationIconText: {
    fontSize: 24,
  },
  meditationTitle: {
    fontSize: theme.typography.fontSize.headingLarge,
    fontWeight: '600',
    color: theme.colors.warmWhite,
    marginBottom: theme.spacing.xs,
  },
  meditationSubtitle: {
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.warmWhite,
    opacity: 0.9,
  },
  xpBadge: {
    position: 'absolute',
    top: 0,
    right: 0,
    backgroundColor: theme.colors.mutedGold,
    borderRadius: theme.borderRadius.md,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.xs,
  },
  xpBadgeText: {
    fontSize: theme.typography.fontSize.small,
    fontWeight: '600',
    color: theme.colors.warmWhite,
  },
  
  // Action Cards
  actionCardsRow: {
    flexDirection: 'row',
    gap: theme.spacing.base,
    marginBottom: theme.spacing.base,
  },
  actionCard: {
    flex: 1,
    height: 140,
    borderRadius: theme.borderRadius.lg,
    overflow: 'hidden',
    ...theme.shadows.small,
  },
  actionCardImage: {
    flex: 1,
  },
  actionCardImageStyle: {
    borderRadius: theme.borderRadius.lg,
  },
  actionCardOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.3)',
    padding: theme.spacing.base,
    justifyContent: 'space-between',
  },
  actionCardTitle: {
    fontSize: theme.typography.fontSize.heading,
    fontWeight: '600',
    color: theme.colors.warmWhite,
  },
  actionCardArrow: {
    width: 32,
    height: 32,
    borderRadius: theme.borderRadius.circle,
    backgroundColor: theme.colors.mutedGold,
    alignItems: 'center',
    justifyContent: 'center',
    alignSelf: 'flex-end',
  },
  actionCardArrowText: {
    fontSize: 18,
    color: theme.colors.warmWhite,
    fontWeight: '600',
  },
  
  // Streak Card
  streakCard: {
    backgroundColor: theme.colors.cardBg,
    borderRadius: theme.borderRadius.xl,
    padding: theme.spacing.lg,
    ...theme.shadows.medium,
  },
  streakHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing.xs,
  },
  streakTitle: {
    fontSize: theme.typography.fontSize.heading,
    fontWeight: '600',
    color: theme.colors.text,
  },
  viewHistoryLink: {
    fontSize: theme.typography.fontSize.small,
    color: theme.colors.sage,
    textDecorationLine: 'underline',
  },
  streakSubtitle: {
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.textSecondary,
    marginBottom: theme.spacing.lg,
  },
  
  // Calendar
  calendar: {
    marginTop: theme.spacing.base,
  },
  calendarMonth: {
    fontSize: theme.typography.fontSize.small,
    color: theme.colors.textTertiary,
    marginBottom: theme.spacing.md,
  },
  calendarGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  calendarDay: {
    alignItems: 'center',
    gap: theme.spacing.sm,
  },
  calendarDayLabel: {
    fontSize: theme.typography.fontSize.tiny,
    color: theme.colors.textTertiary,
    fontWeight: '500',
  },
  calendarDayCircle: {
    width: 40,
    height: 40,
    borderRadius: theme.borderRadius.circle,
    backgroundColor: theme.colors.backgroundLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  calendarDayComplete: {
    backgroundColor: theme.colors.categoryPurple,
  },
  calendarDayToday: {
    backgroundColor: theme.colors.inactive,
  },
  calendarDayNumber: {
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.text,
    fontWeight: '600',
  },
  calendarDayNumberComplete: {
    color: theme.colors.warmWhite,
  },
});
