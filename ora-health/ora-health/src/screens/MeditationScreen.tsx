import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { theme } from '../theme';
import { Card } from '../components/Card';
import { Badge } from '../components/Badge';
import { meditationAPI, Meditation } from '../services/api';

const CATEGORIES = [
  { id: 'all', label: 'All', icon: '✨' },
  { id: 'breathwork', label: 'Breathe', icon: '🌬️' },
  { id: 'guided', label: 'Guided', icon: '🎧' },
  { id: 'mindful', label: 'Mindful', icon: '🧘' },
  { id: 'sleep', label: 'Sleep', icon: '🌙' },
];

export const MeditationScreen: React.FC = () => {
  const [meditations, setMeditations] = useState<Meditation[]>([]);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadMeditations();
  }, [selectedCategory]);

  const loadMeditations = async () => {
    try {
      setLoading(true);
      const data = selectedCategory === 'all'
        ? await meditationAPI.getAll()
        : await meditationAPI.getByCategory(selectedCategory);
      setMeditations(data);
    } catch (error) {
      console.error('Failed to load meditations:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredMeditations = selectedCategory === 'all' 
    ? meditations 
    : meditations.filter(m => m.category === selectedCategory);

  const featuredMeditation = meditations.length > 0 ? meditations[0] : null;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>Find Calm</Text>
          <Text style={styles.subtitle}>Take a moment to center yourself</Text>
        </View>

        {/* Featured Meditation */}
        {featuredMeditation && (
          <Card elevated style={styles.featured}>
            <Badge label="Today's Practice" color={theme.colors.sage} size="small" style={styles.featuredBadge} />
            
            <View style={styles.featuredContent}>
              <View style={styles.featuredImage}>
                <Text style={styles.featuredEmoji}>{featuredMeditation.icon}</Text>
              </View>
              
              <View style={styles.featuredInfo}>
                <Text style={styles.featuredTitle}>{featuredMeditation.title}</Text>
                <Text style={styles.featuredDescription}>{featuredMeditation.description}</Text>
                <View style={styles.featuredMeta}>
                  <Text style={styles.featuredDuration}>{featuredMeditation.duration} min</Text>
                  <Badge 
                    label={featuredMeditation.category} 
                    color={theme.colors.sage} 
                    size="small"
                  />
                </View>
              </View>
            </View>
            
            <TouchableOpacity style={styles.featuredButton} activeOpacity={0.8}>
              <Text style={styles.featuredButtonText}>Begin Practice</Text>
              <Text style={styles.featuredButtonIcon}>▶</Text>
            </TouchableOpacity>
          </Card>
        )}

        {/* Category Filter */}
        <View style={styles.categories}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.categoriesContent}>
            {CATEGORIES.map(cat => (
              <TouchableOpacity
                key={cat.id}
                onPress={() => setSelectedCategory(cat.id)}
                activeOpacity={0.7}
              >
                <View style={[
                  styles.categoryChip,
                  selectedCategory === cat.id && styles.categoryChipActive
                ]}>
                  <Text style={styles.categoryIcon}>{cat.icon}</Text>
                  <Text style={[
                    styles.categoryLabel,
                    selectedCategory === cat.id && styles.categoryLabelActive
                  ]}>
                    {cat.label}
                  </Text>
                </View>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>

        {/* Meditation Grid */}
        {loading ? (
          <View style={styles.loading}>
            <ActivityIndicator size="large" color={theme.colors.sage} />
          </View>
        ) : (
          <View style={styles.grid}>
            {filteredMeditations.map((meditation) => (
              <TouchableOpacity
                key={meditation.id}
                style={styles.card}
                activeOpacity={0.8}
              >
                <View style={styles.cardImage}>
                  <Text style={styles.cardEmoji}>{meditation.icon}</Text>
                </View>
                
                <View style={styles.cardContent}>
                  <Text style={styles.cardTitle}>{meditation.title}</Text>
                  <Text style={styles.cardDescription} numberOfLines={2}>
                    {meditation.description}
                  </Text>
                  
                  <View style={styles.cardFooter}>
                    <Text style={styles.cardDuration}>{meditation.duration} min</Text>
                    <TouchableOpacity style={styles.cardPlay}>
                      <Text style={styles.cardPlayIcon}>▶</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* Empty State */}
        {!loading && filteredMeditations.length === 0 && (
          <View style={styles.empty}>
            <Text style={styles.emptyEmoji}>🌿</Text>
            <Text style={styles.emptyText}>No meditations found</Text>
            <Text style={styles.emptySubtext}>Try selecting a different category</Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.warmCream,
  },
  
  // Header
  header: {
    padding: theme.spacing.base,
    paddingTop: theme.spacing.md,
  },
  title: {
    fontSize: theme.typography.fontSize.hero,
    fontWeight: theme.typography.fontWeight.bold,
    color: theme.colors.text,
    marginBottom: theme.spacing.xs,
  },
  subtitle: {
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.textSecondary,
  },
  
  // Featured Card
  featured: {
    margin: theme.spacing.base,
  },
  featuredBadge: {
    marginBottom: theme.spacing.base,
  },
  featuredContent: {
    flexDirection: 'row',
    marginBottom: theme.spacing.lg,
  },
  featuredImage: {
    width: 100,
    height: 100,
    borderRadius: theme.borderRadius.circle,
    backgroundColor: theme.colors.sage + '30',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: theme.spacing.base,
  },
  featuredEmoji: {
    fontSize: 48,
  },
  featuredInfo: {
    flex: 1,
  },
  featuredTitle: {
    fontSize: theme.typography.fontSize.headingLarge,
    fontWeight: theme.typography.fontWeight.semibold,
    color: theme.colors.text,
    marginBottom: theme.spacing.xs,
  },
  featuredDescription: {
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.textSecondary,
    marginBottom: theme.spacing.md,
    lineHeight: 22,
  },
  featuredMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: theme.spacing.sm,
  },
  featuredDuration: {
    fontSize: theme.typography.fontSize.small,
    color: theme.colors.textTertiary,
    fontWeight: theme.typography.fontWeight.medium,
  },
  featuredButton: {
    backgroundColor: theme.colors.sage,
    borderRadius: theme.borderRadius.xxl,
    paddingVertical: theme.spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    ...theme.shadows.small,
  },
  featuredButtonText: {
    fontSize: theme.typography.fontSize.body,
    fontWeight: theme.typography.fontWeight.semibold,
    color: theme.colors.warmWhite,
    marginRight: theme.spacing.sm,
  },
  featuredButtonIcon: {
    fontSize: 14,
    color: theme.colors.warmWhite,
  },
  
  // Categories
  categories: {
    marginBottom: theme.spacing.lg,
  },
  categoriesContent: {
    paddingHorizontal: theme.spacing.base,
    gap: theme.spacing.sm,
  },
  categoryChip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.colors.cardBg,
    paddingHorizontal: theme.spacing.base,
    paddingVertical: theme.spacing.sm,
    borderRadius: theme.borderRadius.pill,
    borderWidth: 1,
    borderColor: theme.colors.borderLight,
  },
  categoryChipActive: {
    backgroundColor: theme.colors.sage,
    borderColor: theme.colors.sage,
  },
  categoryIcon: {
    fontSize: 16,
    marginRight: theme.spacing.xs,
  },
  categoryLabel: {
    fontSize: theme.typography.fontSize.body,
    fontWeight: theme.typography.fontWeight.medium,
    color: theme.colors.text,
  },
  categoryLabelActive: {
    color: theme.colors.warmWhite,
  },
  
  // Grid
  grid: {
    padding: theme.spacing.base,
    paddingTop: 0,
    gap: theme.spacing.base,
  },
  card: {
    backgroundColor: theme.colors.cardBg,
    borderRadius: theme.borderRadius.lg,
    overflow: 'hidden',
    marginBottom: theme.spacing.base,
    ...theme.shadows.small,
  },
  cardImage: {
    height: 140,
    backgroundColor: theme.colors.warmBeige,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardEmoji: {
    fontSize: 48,
  },
  cardContent: {
    padding: theme.spacing.base,
  },
  cardTitle: {
    fontSize: theme.typography.fontSize.heading,
    fontWeight: theme.typography.fontWeight.semibold,
    color: theme.colors.text,
    marginBottom: theme.spacing.xs,
  },
  cardDescription: {
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.textSecondary,
    marginBottom: theme.spacing.md,
    lineHeight: 22,
  },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardDuration: {
    fontSize: theme.typography.fontSize.small,
    color: theme.colors.textTertiary,
    fontWeight: theme.typography.fontWeight.medium,
  },
  cardPlay: {
    width: 36,
    height: 36,
    borderRadius: theme.borderRadius.circle,
    backgroundColor: theme.colors.sage,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardPlayIcon: {
    fontSize: 12,
    color: theme.colors.warmWhite,
    marginLeft: 2,
  },
  
  // Loading & Empty
  loading: {
    padding: theme.spacing.xxxl,
    alignItems: 'center',
  },
  empty: {
    padding: theme.spacing.xxxl,
    alignItems: 'center',
  },
  emptyEmoji: {
    fontSize: 64,
    marginBottom: theme.spacing.base,
  },
  emptyText: {
    fontSize: theme.typography.fontSize.heading,
    fontWeight: theme.typography.fontWeight.semibold,
    color: theme.colors.text,
    marginBottom: theme.spacing.xs,
  },
  emptySubtext: {
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.textSecondary,
  },
});
