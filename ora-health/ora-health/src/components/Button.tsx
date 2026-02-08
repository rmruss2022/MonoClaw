import React from 'react';
import { TouchableOpacity, Text, StyleSheet, ViewStyle, TextStyle, ActivityIndicator } from 'react-native';
import { theme } from '../theme';

interface ButtonProps {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost';
  size?: 'small' | 'medium' | 'large';
  disabled?: boolean;
  loading?: boolean;
  style?: ViewStyle;
  textStyle?: TextStyle;
  icon?: string;
}

export const Button: React.FC<ButtonProps> = ({
  title,
  onPress,
  variant = 'primary',
  size = 'medium',
  disabled = false,
  loading = false,
  style,
  textStyle,
  icon,
}) => {
  const buttonStyles = [
    styles.button,
    styles[`button_${variant}`],
    styles[`button_${size}`],
    disabled && styles.button_disabled,
    style,
  ];

  const textStyles = [
    styles.text,
    styles[`text_${variant}`],
    styles[`text_${size}`],
    disabled && styles.text_disabled,
    textStyle,
  ];

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={disabled || loading}
      style={buttonStyles}
      activeOpacity={0.7}
    >
      {loading ? (
        <ActivityIndicator color={variant === 'primary' ? theme.colors.warmWhite : theme.colors.sage} />
      ) : (
        <>
          {icon && <Text style={[styles.icon, styles[`icon_${size}`]]}>{icon}</Text>}
          <Text style={textStyles}>{title}</Text>
        </>
      )}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: theme.borderRadius.xxl,
  },
  
  // Variants
  button_primary: {
    backgroundColor: theme.colors.sage,
    ...theme.shadows.small,
  },
  button_secondary: {
    backgroundColor: theme.colors.warmBeige,
  },
  button_outline: {
    backgroundColor: 'transparent',
    borderWidth: 1.5,
    borderColor: theme.colors.sage,
  },
  button_ghost: {
    backgroundColor: 'transparent',
  },
  button_disabled: {
    backgroundColor: theme.colors.borderLight,
    opacity: 0.5,
  },
  
  // Sizes
  button_small: {
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    minHeight: 32,
  },
  button_medium: {
    paddingHorizontal: theme.spacing.xl,
    paddingVertical: theme.spacing.md,
    minHeight: 44,
  },
  button_large: {
    paddingHorizontal: theme.spacing.xxl,
    paddingVertical: theme.spacing.base,
    minHeight: 52,
  },
  
  // Text styles
  text: {
    fontWeight: theme.typography.fontWeight.semibold,
  },
  text_primary: {
    color: theme.colors.warmWhite,
  },
  text_secondary: {
    color: theme.colors.text,
  },
  text_outline: {
    color: theme.colors.sage,
  },
  text_ghost: {
    color: theme.colors.sage,
  },
  text_disabled: {
    color: theme.colors.textLight,
  },
  text_small: {
    fontSize: theme.typography.fontSize.small,
  },
  text_medium: {
    fontSize: theme.typography.fontSize.body,
  },
  text_large: {
    fontSize: theme.typography.fontSize.bodyLarge,
  },
  
  // Icon
  icon: {
    marginRight: theme.spacing.xs,
  },
  icon_small: {
    fontSize: 14,
  },
  icon_medium: {
    fontSize: 18,
  },
  icon_large: {
    fontSize: 20,
  },
});
