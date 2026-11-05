/**
 * Ora Health Design System
 * Modern Aurora Aesthetic — purple + pink
 * (Keys kept stable so every screen re-themes from this one file.)
 */

export const theme = {
  colors: {
    // Primary muted purple - matches the real app's #7B5EA7 (key name kept as `sage`)
    sage: '#7B5EA7',
    oliveGreen: '#5F4B87',

    // Backgrounds - Soft lavender (matches app's #F0E8F5)
    warmCream: '#F3EDF8',
    warmBeige: '#EADDF3',
    backgroundLight: '#F0E8F5',

    // Surfaces - Cards, modals
    softTaupe: '#D4B8E8',
    warmWhite: '#FFFFFF',
    cardBg: '#FFFFFF',

    // Accents - Blush pink (matches app's #F8C8DC family)
    mutedGold: '#E68FBE',
    goldHighlight: '#F0B8D6',
    weekBadge: '#F6DCEC',

    // Semantic Colors
    text: '#2E2440',
    textSecondary: '#5C5470',
    textTertiary: '#8B84A0',
    textLight: '#B4ADC6',

    // Category Colors (soft purple/pink family)
    categoryPurple: '#A78BCF',
    categoryGreen: '#7B5EA7',
    categoryCoral: '#E89BC4',
    categoryBlue: '#8E9BD6',
    categoryAmber: '#D98FC0',

    // Functional
    border: '#ECE1F5',
    borderLight: '#F4ECFA',
    shadow: 'rgba(123, 94, 167, 0.12)',
    shadowDark: 'rgba(123, 94, 167, 0.18)',

    // Interactive
    active: '#6D4F9C',
    inactive: '#C9BBDD',
    error: '#E27B9C',
    success: '#7B5EA7',
  },

  // Signature gradients (mirrors the real app's LinearGradient pairs)
  gradients: {
    signature: ['#D4B8E8', '#F8C8DC'] as const, // lavender → blush pink (used 24× in-app)
    purple: ['#9B72B0', '#7B5EA7'] as const,    // muted purple buttons
    pink: ['#EFB4D6', '#F8C8DC'] as const,       // pink selected state
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
