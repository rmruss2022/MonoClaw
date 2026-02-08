import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { theme } from '../theme';

type TabName = 'Home' | 'Meditate' | 'Chat' | 'Community' | 'Profile';

interface BottomNavProps {
  activeTab?: TabName;
  onTabPress?: (tab: TabName) => void;
}

export default function BottomNav({ activeTab = 'Home', onTabPress }: BottomNavProps) {
  const tabs: Array<{ name: TabName; icon: string }> = [
    { name: 'Home', icon: '🏠' },
    { name: 'Meditate', icon: '🧘' },
    { name: 'Chat', icon: '💬' },
    { name: 'Community', icon: '🤝' },
    { name: 'Profile', icon: '👤' },
  ];

  return (
    <View style={styles.container}>
      <View style={styles.inner}>
        {tabs.map((tab) => (
          <TouchableOpacity
            key={tab.name}
            style={styles.tab}
            onPress={() => onTabPress?.(tab.name)}
            activeOpacity={0.7}
          >
            <Text style={styles.icon}>{tab.icon}</Text>
            <Text style={[
              styles.label,
              activeTab === tab.name && styles.labelActive,
            ]}>
              {tab.name}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: theme.colors.warmWhite,
    borderTopWidth: 1,
    borderTopColor: theme.colors.borderLight,
    paddingBottom: 20,
  },
  inner: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingTop: theme.spacing.sm,
  },
  tab: {
    alignItems: 'center',
    paddingVertical: theme.spacing.xs,
    paddingHorizontal: theme.spacing.sm,
  },
  icon: {
    fontSize: 24,
    marginBottom: 4,
  },
  label: {
    fontSize: theme.typography.fontSize.tiny,
    color: theme.colors.textTertiary,
    fontWeight: '500',
  },
  labelActive: {
    color: theme.colors.sage,
    fontWeight: '600',
  },
});
