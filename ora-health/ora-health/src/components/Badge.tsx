import React from 'react';
import { View, Text, StyleSheet, ViewStyle } from 'react-native';
import { theme } from '../theme';

interface BadgeProps {
  label: string;
  color?: string;
  icon?: string;
  style?: ViewStyle;
  size?: 'small' | 'medium';
}

export const Badge: React.FC<BadgeProps> = ({
  label,
  color = theme.colors.sage,
  icon,
  style,
  size = 'medium',
}) => {
  return (
    <View style={[styles.badge, { backgroundColor: color + '20' }, styles[`badge_${size}`], style]}>
      {icon && <Text style={[styles.icon, styles[`icon_${size}`]]}>{icon}</Text>}
      <Text style={[styles.text, { color }, styles[`text_${size}`]]}>{label}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: theme.borderRadius.pill,
    alignSelf: 'flex-start',
  },
  badge_small: {
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: theme.spacing.xs,
  },
  badge_medium: {
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.xs,
  },
  icon: {
    marginRight: theme.spacing.xs,
  },
  icon_small: {
    fontSize: 11,
  },
  icon_medium: {
    fontSize: 13,
  },
  text: {
    fontWeight: theme.typography.fontWeight.semibold,
  },
  text_small: {
    fontSize: theme.typography.fontSize.tiny,
  },
  text_medium: {
    fontSize: theme.typography.fontSize.small,
  },
});
