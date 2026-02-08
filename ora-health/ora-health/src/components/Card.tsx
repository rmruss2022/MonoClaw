import React from 'react';
import { View, StyleSheet, ViewStyle } from 'react-native';
import { theme } from '../theme';

interface CardProps {
  children: React.ReactNode;
  style?: ViewStyle;
  elevated?: boolean;
  padding?: keyof typeof theme.spacing;
}

export const Card: React.FC<CardProps> = ({ 
  children, 
  style, 
  elevated = false,
  padding = 'base'
}) => {
  return (
    <View 
      style={[
        styles.card, 
        elevated && theme.shadows.card,
        { padding: theme.spacing[padding] },
        style
      ]}
    >
      {children}
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.colors.cardBg,
    borderRadius: theme.borderRadius.lg,
    borderWidth: 1,
    borderColor: theme.colors.borderLight,
  },
});
