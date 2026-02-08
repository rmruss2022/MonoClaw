import React, { useState, useEffect } from 'react';
import { 
  View, Text, StyleSheet, ScrollView, TouchableOpacity, 
  ActivityIndicator, RefreshControl 
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { theme } from '../theme';
import { Card } from '../components/Card';
import { Badge } from '../components/Badge';
import { communityAPI, Category, Post } from '../services/api';

const TABS = ['Feed', 'Inbox', 'Groups', 'Profile'];

export const CommunityScreen: React.FC = () => {
  const [activeTab, setActiveTab] = useState('Feed');
  const [categories, setCategories] = useState<Category[]>([]);
  const [posts, setPosts] = useState<Post[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [categoriesData, postsData] = await Promise.all([
        communityAPI.getCategories(),
        communityAPI.getPosts(),
      ]);
      setCategories(categoriesData);
      setPosts(postsData);
    } catch (error) {
      console.error('Failed to load community data:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const filteredPosts = selectedCategory
    ? posts.filter(p => p.categoryId === selectedCategory)
    : posts;

  const getCategoryById = (id: string) => {
    return categories.find(c => c.id === id);
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Community</Text>
          <Text style={styles.subtitle}>Share your journey, support others</Text>
        </View>
      </View>

      {/* Tabs */}
      <View style={styles.tabs}>
        {TABS.map(tab => (
          <TouchableOpacity
            key={tab}
            onPress={() => setActiveTab(tab)}
            style={[styles.tab, activeTab === tab && styles.tabActive]}
          >
            <Text style={[styles.tabText, activeTab === tab && styles.tabTextActive]}>
              {tab}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Content */}
      {activeTab === 'Feed' && (
        <ScrollView
          style={styles.content}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={theme.colors.sage} />
          }
        >
          {/* Weekly Prompt Banner */}
          <Card style={styles.promptBanner}>
            <Badge label="Weekly Prompt" color={theme.colors.mutedGold} size="small" />
            <Text style={styles.promptText}>
              What's one small win you experienced this week?
            </Text>
            <TouchableOpacity style={styles.promptButton}>
              <Text style={styles.promptButtonText}>Share Your Story</Text>
            </TouchableOpacity>
          </Card>

          {/* Category Filter */}
          {categories.length > 0 && (
            <View style={styles.categories}>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.categoriesContent}>
                <TouchableOpacity
                  onPress={() => setSelectedCategory(null)}
                  activeOpacity={0.7}
                >
                  <View style={[styles.categoryChip, !selectedCategory && styles.categoryChipActive]}>
                    <Text style={[styles.categoryLabel, !selectedCategory && styles.categoryLabelActive]}>
                      All
                    </Text>
                  </View>
                </TouchableOpacity>
                
                {categories.map(cat => (
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
                        {cat.name}
                      </Text>
                    </View>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
          )}

          {/* Posts */}
          {loading ? (
            <View style={styles.loading}>
              <ActivityIndicator size="large" color={theme.colors.sage} />
            </View>
          ) : filteredPosts.length > 0 ? (
            <View style={styles.posts}>
              {filteredPosts.map((post) => {
                const category = getCategoryById(post.categoryId);
                return (
                  <Card key={post.id} elevated style={styles.postCard}>
                    {/* Post Header */}
                    <View style={styles.postHeader}>
                      <View style={styles.postAvatar}>
                        <Text style={styles.postAvatarText}>
                          {post.isAnonymous ? '?' : '👤'}
                        </Text>
                      </View>
                      <View style={styles.postHeaderInfo}>
                        <Text style={styles.postAuthor}>
                          {post.isAnonymous ? 'Anonymous' : 'User'}
                        </Text>
                        <Text style={styles.postTime}>
                          {new Date(post.createdAt).toLocaleDateString()}
                        </Text>
                      </View>
                      {category && (
                        <Badge 
                          label={category.name}
                          icon={category.icon}
                          color={category.color}
                          size="small"
                        />
                      )}
                    </View>

                    {/* Post Content */}
                    <Text style={styles.postContent}>{post.content}</Text>

                    {/* Post Actions */}
                    <View style={styles.postActions}>
                      <TouchableOpacity style={styles.postAction}>
                        <Text style={styles.postActionIcon}>❤️</Text>
                        <Text style={styles.postActionText}>{post.likes || 0}</Text>
                      </TouchableOpacity>
                      <TouchableOpacity style={styles.postAction}>
                        <Text style={styles.postActionIcon}>💬</Text>
                        <Text style={styles.postActionText}>{post.comments || 0}</Text>
                      </TouchableOpacity>
                      <TouchableOpacity style={styles.postAction}>
                        <Text style={styles.postActionIcon}>🔖</Text>
                      </TouchableOpacity>
                    </View>
                  </Card>
                );
              })}
            </View>
          ) : (
            <View style={styles.empty}>
              <Text style={styles.emptyEmoji}>🌱</Text>
              <Text style={styles.emptyText}>No posts yet</Text>
              <Text style={styles.emptySubtext}>
                {selectedCategory 
                  ? 'Try selecting a different category' 
                  : 'Be the first to share your story'}
              </Text>
            </View>
          )}
        </ScrollView>
      )}

      {/* Other Tabs (Placeholder) */}
      {activeTab !== 'Feed' && (
        <View style={styles.placeholder}>
          <Text style={styles.placeholderEmoji}>🚧</Text>
          <Text style={styles.placeholderText}>{activeTab} Coming Soon</Text>
        </View>
      )}

      {/* Floating Action Button */}
      {activeTab === 'Feed' && (
        <TouchableOpacity style={styles.fab} activeOpacity={0.8}>
          <Text style={styles.fabText}>+</Text>
        </TouchableOpacity>
      )}
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
    backgroundColor: theme.colors.warmWhite,
  },
  title: {
    fontSize: theme.typography.fontSize.hero,
    fontWeight: theme.typography.fontWeight.bold,
    color: theme.colors.text,
  },
  subtitle: {
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.textSecondary,
  },
  
  // Tabs
  tabs: {
    flexDirection: 'row',
    backgroundColor: theme.colors.warmWhite,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.borderLight,
    paddingHorizontal: theme.spacing.base,
  },
  tab: {
    paddingVertical: theme.spacing.md,
    paddingHorizontal: theme.spacing.base,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabActive: {
    borderBottomColor: theme.colors.sage,
  },
  tabText: {
    fontSize: theme.typography.fontSize.body,
    fontWeight: theme.typography.fontWeight.medium,
    color: theme.colors.textTertiary,
  },
  tabTextActive: {
    color: theme.colors.sage,
    fontWeight: theme.typography.fontWeight.semibold,
  },
  
  // Content
  content: {
    flex: 1,
  },
  
  // Prompt Banner
  promptBanner: {
    margin: theme.spacing.base,
    backgroundColor: theme.colors.mutedGold + '15',
    borderColor: theme.colors.mutedGold + '30',
  },
  promptText: {
    fontSize: theme.typography.fontSize.bodyLarge,
    fontWeight: theme.typography.fontWeight.medium,
    color: theme.colors.text,
    marginVertical: theme.spacing.md,
  },
  promptButton: {
    backgroundColor: theme.colors.mutedGold,
    borderRadius: theme.borderRadius.xxl,
    paddingVertical: theme.spacing.sm,
    alignItems: 'center',
  },
  promptButtonText: {
    fontSize: theme.typography.fontSize.body,
    fontWeight: theme.typography.fontWeight.semibold,
    color: theme.colors.warmWhite,
  },
  
  // Categories
  categories: {
    marginBottom: theme.spacing.base,
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
    fontSize: 14,
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
  
  // Posts
  posts: {
    padding: theme.spacing.base,
    paddingTop: 0,
  },
  postCard: {
    marginBottom: theme.spacing.base,
  },
  postHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: theme.spacing.md,
  },
  postAvatar: {
    width: 40,
    height: 40,
    borderRadius: theme.borderRadius.circle,
    backgroundColor: theme.colors.warmBeige,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: theme.spacing.md,
  },
  postAvatarText: {
    fontSize: 20,
  },
  postHeaderInfo: {
    flex: 1,
  },
  postAuthor: {
    fontSize: theme.typography.fontSize.body,
    fontWeight: theme.typography.fontWeight.semibold,
    color: theme.colors.text,
  },
  postTime: {
    fontSize: theme.typography.fontSize.small,
    color: theme.colors.textTertiary,
  },
  postContent: {
    fontSize: theme.typography.fontSize.body,
    color: theme.colors.text,
    lineHeight: 22,
    marginBottom: theme.spacing.md,
  },
  postActions: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: theme.colors.borderLight,
    paddingTop: theme.spacing.md,
    gap: theme.spacing.lg,
  },
  postAction: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  postActionIcon: {
    fontSize: 16,
    marginRight: theme.spacing.xs,
  },
  postActionText: {
    fontSize: theme.typography.fontSize.small,
    color: theme.colors.textSecondary,
    fontWeight: theme.typography.fontWeight.medium,
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
    textAlign: 'center',
  },
  
  // Placeholder
  placeholder: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: theme.spacing.xxxl,
  },
  placeholderEmoji: {
    fontSize: 64,
    marginBottom: theme.spacing.base,
  },
  placeholderText: {
    fontSize: theme.typography.fontSize.heading,
    fontWeight: theme.typography.fontWeight.semibold,
    color: theme.colors.text,
  },
  
  // FAB
  fab: {
    position: 'absolute',
    right: theme.spacing.base,
    bottom: theme.spacing.base,
    width: 56,
    height: 56,
    borderRadius: theme.borderRadius.circle,
    backgroundColor: theme.colors.sage,
    alignItems: 'center',
    justifyContent: 'center',
    ...theme.shadows.large,
  },
  fabText: {
    fontSize: 32,
    color: theme.colors.warmWhite,
    fontWeight: theme.typography.fontWeight.bold,
  },
});
