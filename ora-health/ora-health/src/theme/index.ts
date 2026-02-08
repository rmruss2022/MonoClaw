/**
 * Ora Health Design System
 * Mediterranean Sanctuary Aesthetic
 * Based on UI Reference Screenshot
 */

export const theme = {
  colors: {
    // Primary Greens (Sage/Olive) - Icons, accents
    sage: '#8B9A6B',
    oliveGreen: '#6B7B5A',
    
    // Backgrounds - Warm, organic
    warmCream: '#F5F2EA',
    warmBeige: '#EDE9DF',
    backgroundLight: '#F8F6F2',
    
    // Surfaces - Cards, modals
    softTaupe: '#D4C9B8',
    warmWhite: '#FEFEFE',
    cardBg: '#FFFFFF',
    
    // Accents - Highlights, badges
    mutedGold: '#C4A962',
    goldHighlight: '#D4B86A',
    weekBadge: '#E8D9A6',
    
    // Semantic Colors
    text: '#2C2C2C',
    textSecondary: '#5C5C5C',
    textTertiary: '#8C8C8C',
    textLight: '#A8A8A8',
    
    // Category Colors (muted, harmonious)
    categoryPurple: '#A89AC4',
    categoryGreen: '#8B9A6B',
    categoryCoral: '#D4A59A',
    categoryBlue: '#8BA4B8',
    categoryAmber: '#C4A962',
    
    // Functional
    border: '#E5E1D8',
    borderLight: '#F0EDE5',
    shadow: 'rgba(44, 44, 44, 0.08)',
    shadowDark: 'rgba(44, 44, 44, 0.12)',
    
    // Interactive
    active: '#6B7B5A',
    inactive: '#B8B8B8',
    error: '#D47B7B',
    success: '#7B9A6B',
  },
  
  spacing: {
    xs: 4,
    sm: 8,
    md: 12,
    base: 16,
    lg: 20,
    xl: 24,
    xxl: 32,
    xxxl: 40,
    huge: 48,
  },
  
  borderRadius: {
    xs: 4,
    sm: 8,
    md: 12,
    lg: 16,
    xl: 20,
    xxl: 24,
    pill: 100,
    circle: 999,
  },
  
  typography: {
    // Font families
    fontFamily: {
      regular: 'System', // Will use SF Pro on iOS
      medium: 'System',
      semibold: 'System',
      bold: 'System',
    },
    
    // Font sizes
    fontSize: {
      tiny: 11,
      small: 13,
      body: 16,
      bodyLarge: 18,
      heading: 20,
      headingLarge: 24,
      hero: 28,
      heroLarge: 32,
    },
    
    // Line heights
    lineHeight: {
      tight: 1.2,
      normal: 1.5,
      relaxed: 1.7,
    },
    
    // Font weights
    fontWeight: {
      regular: '400' as const,
      medium: '500' as const,
      semibold: '600' as const,
      bold: '700' as const,
    },
  },
  
  shadows: {
    small: {
      shadowColor: '#2C2C2C',
      shadowOffset: { width: 0, height: 1 },
      shadowOpacity: 0.06,
      shadowRadius: 2,
      elevation: 1,
    },
    medium: {
      shadowColor: '#2C2C2C',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.08,
      shadowRadius: 4,
      elevation: 2,
    },
    large: {
      shadowColor: '#2C2C2C',
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.10,
      shadowRadius: 8,
      elevation: 4,
    },
    card: {
      shadowColor: '#2C2C2C',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.06,
      shadowRadius: 6,
      elevation: 2,
    },
  },
  
  animation: {
    duration: {
      fast: 150,
      normal: 250,
      slow: 350,
    },
    easing: {
      ease: 'ease-in-out',
      spring: 'spring',
    },
  },
};

export type Theme = typeof theme;
