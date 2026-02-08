# Ora Health - Quick Implementation Guide

## What You Have Now

✅ **Complete Design System** - Colors, typography, spacing, components
✅ **App Vision Document** - Philosophy, tone, target audience
✅ **4 Redesigned Screens** - Home, Chat, Meditation, Community
✅ **Design Tokens** - Theme file ready to use
✅ **8 Dynamic Behaviors** - AI that adapts to user needs

---

## Step 1: Activate the New Screens (5 minutes)

### Replace Old Screens with New Designs

```bash
cd /Users/matthew/Desktop/Feb26/shadow-ai/src/screens

# Backup originals
mkdir _old
mv ChatScreen.tsx _old/
mv HomeScreen.tsx _old/

# Activate redesigned versions
mv ChatScreen.redesigned.tsx ChatScreen.tsx
mv HomeScreen.redesigned.tsx HomeScreen.tsx
mv MeditationScreen.redesigned.tsx MeditationScreen.tsx
mv CommunityScreen.redesigned.tsx CommunityScreen.tsx
```

---

## Step 2: Set Up Navigation (10 minutes)

### Install Dependencies

```bash
cd /Users/matthew/Desktop/Feb26/shadow-ai
npm install @react-navigation/native @react-navigation/bottom-tabs
npm install react-native-screens react-native-safe-area-context
```

### Create Navigator File

**File:** `src/navigation/AppNavigator.tsx`

```typescript
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { HomeScreen } from '../screens/HomeScreen';
import { ChatScreen } from '../screens/ChatScreen';
import { MeditationScreen } from '../screens/MeditationScreen';
import { CommunityScreen } from '../screens/CommunityScreen';
import { theme } from '../theme';

const Tab = createBottomTabNavigator();

export function AppNavigator() {
  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={{
          headerShown: false,
          tabBarStyle: {
            backgroundColor: theme.colors.white,
            borderTopColor: theme.colors.border,
            height: 60,
            paddingBottom: 8,
            paddingTop: 8,
          },
          tabBarActiveTintColor: theme.colors.primary,
          tabBarInactiveTintColor: theme.colors.textTertiary,
          tabBarLabelStyle: {
            fontSize: 11,
            fontWeight: '600',
          },
        }}
      >
        <Tab.Screen
          name="Home"
          component={HomeScreen}
          options={{
            tabBarIcon: ({ focused }) => <Text style={{ fontSize: 24 }}>🏠</Text>,
          }}
        />
        <Tab.Screen
          name="Chat"
          component={ChatScreen}
          options={{
            tabBarIcon: ({ focused }) => <Text style={{ fontSize: 24 }}>💜</Text>,
          }}
        />
        <Tab.Screen
          name="Meditation"
          component={MeditationScreen}
          options={{
            tabBarIcon: ({ focused }) => <Text style={{ fontSize: 24 }}>🧘</Text>,
            tabBarLabel: 'Calm',
          }}
        />
        <Tab.Screen
          name="Community"
          component={CommunityScreen}
          options={{
            tabBarIcon: ({ focused }) => <Text style={{ fontSize: 24 }}>🤝</Text>,
            tabBarLabel: 'Connect',
          }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
```

### Update App.tsx

**File:** `App.tsx`

```typescript
import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaView, StyleSheet } from 'react-native';
import { AppNavigator } from './src/navigation/AppNavigator';
import { theme } from './src/theme';

export default function App() {
  return (
    <>
      <SafeAreaView style={styles.container}>
        <AppNavigator />
      </SafeAreaView>
      <StatusBar style="auto" />
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.backgroundLight,
  },
});
```

---

## Step 3: Update Chat Components (15 minutes)

### Update ChatMessage.tsx

**File:** `src/components/chat/ChatMessage.tsx`

```typescript
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { theme } from '../../theme';

interface ChatMessageProps {
  message: {
    id: string;
    role: 'user' | 'assistant';
    content: string;
  };
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const isUser = message.role === 'user';

  return (
    <View style={[styles.container, isUser && styles.containerUser]}>
      <View style={[styles.bubble, isUser ? styles.bubbleUser : styles.bubbleAssistant]}>
        <Text style={[styles.text, isUser && styles.textUser]}>
          {message.content}
        </Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    marginBottom: theme.spacing.sm,
    alignItems: 'flex-start',
  },
  containerUser: {
    alignItems: 'flex-end',
  },
  bubble: {
    maxWidth: '80%',
    padding: theme.spacing.md,
    borderRadius: theme.borderRadius.lg,
  },
  bubbleAssistant: {
    backgroundColor: theme.colors.white,
    borderBottomLeftRadius: theme.borderRadius.xs,
    ...theme.shadows.sm,
  },
  bubbleUser: {
    backgroundColor: theme.colors.primary,
    borderBottomRightRadius: theme.borderRadius.xs,
  },
  text: {
    ...theme.typography.body,
    color: theme.colors.textPrimary,
    lineHeight: 22,
  },
  textUser: {
    color: theme.colors.white,
  },
});
```

### Update ChatInput.tsx

**File:** `src/components/chat/ChatInput.tsx`

```typescript
import React, { useState } from 'react';
import {
  View,
  TextInput,
  TouchableOpacity,
  Text,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { theme } from '../../theme';

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSend, isLoading }) => {
  const [text, setText] = useState('');

  const handleSend = () => {
    if (text.trim() && !isLoading) {
      onSend(text.trim());
      setText('');
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.inputContainer}>
        <TextInput
          style={styles.input}
          placeholder="Share what's on your mind..."
          placeholderTextColor={theme.colors.textTertiary}
          value={text}
          onChangeText={setText}
          multiline
          maxLength={1000}
          editable={!isLoading}
        />
        <TouchableOpacity
          style={[styles.sendButton, (!text.trim() || isLoading) && styles.sendButtonDisabled]}
          onPress={handleSend}
          disabled={!text.trim() || isLoading}
          activeOpacity={0.7}
        >
          {isLoading ? (
            <ActivityIndicator size="small" color={theme.colors.white} />
          ) : (
            <Text style={styles.sendIcon}>↑</Text>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: theme.colors.white,
    borderTopWidth: 1,
    borderTopColor: theme.colors.border,
    paddingHorizontal: theme.spacing.lg,
    paddingVertical: theme.spacing.sm,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
  },
  input: {
    flex: 1,
    ...theme.typography.body,
    backgroundColor: theme.colors.backgroundLight,
    borderRadius: theme.borderRadius.lg,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    marginRight: theme.spacing.xs,
    maxHeight: 100,
  },
  sendButton: {
    width: 40,
    height: 40,
    borderRadius: theme.borderRadius.full,
    backgroundColor: theme.colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendButtonDisabled: {
    backgroundColor: theme.colors.textTertiary,
    opacity: 0.5,
  },
  sendIcon: {
    fontSize: 20,
    color: theme.colors.white,
    fontWeight: '600',
  },
});
```

---

## Step 4: Fix HomeScreen Navigation (5 minutes)

### Update HomeScreen to use Navigation

**File:** `src/screens/HomeScreen.tsx` (update the interface and implementation)

```typescript
import { useNavigation } from '@react-navigation/native';

export const HomeScreen: React.FC = () => {
  const navigation = useNavigation();

  const handleSelectFeature = (featureId: string) => {
    switch (featureId) {
      case 'chat':
        navigation.navigate('Chat');
        break;
      case 'meditation':
        navigation.navigate('Meditation');
        break;
      case 'community':
        navigation.navigate('Community');
        break;
      case 'journal':
        // TODO: Create journal screen
        console.log('Journal feature coming soon');
        break;
    }
  };

  return (
    // ... existing JSX with onSelectFeature={handleSelectFeature}
  );
};
```

---

## Step 5: Test Everything (10 minutes)

### Start the App

```bash
cd /Users/matthew/Desktop/Feb26/shadow-ai
npm start

# Then press 'w' for web
# Or scan QR code for mobile
```

### Test Checklist

**Navigation:**
- [ ] Bottom tabs visible
- [ ] Can navigate between all 4 screens
- [ ] Active tab highlighted in purple
- [ ] Smooth transitions

**Home Screen:**
- [ ] Daily check-in card visible
- [ ] 4 feature cards displayed
- [ ] Progress insight shows
- [ ] Tapping cards navigates correctly

**Chat Screen:**
- [ ] Empty state shows with prompts
- [ ] Can type and send messages
- [ ] Messages appear in bubbles
- [ ] Behavior indicator visible
- [ ] Input disables while loading

**Meditation Screen:**
- [ ] Featured practice card shows
- [ ] Category filters work
- [ ] Can see all 8 meditations
- [ ] Play buttons visible

**Community Screen:**
- [ ] Feed tabs work
- [ ] Posts display correctly
- [ ] Can like posts (toggle heart)
- [ ] Prompt banner visible
- [ ] Tags displayed

---

## Step 6: Polish (Optional, 30 minutes)

### Add Loading States

Create `src/components/LoadingSpinner.tsx`:

```typescript
import React from 'react';
import { View, ActivityIndicator, StyleSheet } from 'react-native';
import { theme } from '../theme';

export const LoadingSpinner: React.FC = () => {
  return (
    <View style={styles.container}>
      <ActivityIndicator size="large" color={theme.colors.primary} />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: theme.colors.backgroundLight,
  },
});
```

### Add Error Boundaries

Create `src/components/ErrorBoundary.tsx`:

```typescript
import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { theme } from '../theme';

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends React.Component<Props, State> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <View style={styles.container}>
          <Text style={styles.emoji}>💜</Text>
          <Text style={styles.title}>Something went wrong</Text>
          <Text style={styles.message}>
            We're here to help. Try refreshing the app.
          </Text>
          <TouchableOpacity
            style={styles.button}
            onPress={() => this.setState({ hasError: false })}
          >
            <Text style={styles.buttonText}>Try Again</Text>
          </TouchableOpacity>
        </View>
      );
    }

    return this.props.children;
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: theme.spacing.xl,
    backgroundColor: theme.colors.backgroundLight,
  },
  emoji: {
    fontSize: 64,
    marginBottom: theme.spacing.lg,
  },
  title: {
    ...theme.typography.h2,
    color: theme.colors.textPrimary,
    marginBottom: theme.spacing.sm,
  },
  message: {
    ...theme.typography.body,
    color: theme.colors.textSecondary,
    textAlign: 'center',
    marginBottom: theme.spacing.xl,
  },
  button: {
    backgroundColor: theme.colors.primary,
    paddingVertical: theme.spacing.sm,
    paddingHorizontal: theme.spacing.xl,
    borderRadius: theme.borderRadius.md,
  },
  buttonText: {
    ...theme.typography.body,
    color: theme.colors.white,
    fontWeight: '600',
  },
});
```

---

## Troubleshooting

### Issue: "Module not found: @react-navigation/native"
**Fix:** Run `npm install` again and restart the dev server

### Issue: Screens are blank
**Fix:** Check that all imports use correct paths (./theme not ../theme)

### Issue: Bottom tabs not showing
**Fix:** Make sure AppNavigator is wrapped in NavigationContainer

### Issue: TypeScript errors
**Fix:** Check that navigation types are properly set up

### Issue: Colors look different
**Fix:** Verify theme colors are imported from `src/theme`

---

## You're Done! 🎉

Your app now has:
✅ Warm, therapeutic design system
✅ 4 fully functional screens
✅ Bottom tab navigation
✅ Updated chat components
✅ Dynamic AI behaviors
✅ Complete design documentation

**Next steps:** Test with real users, gather feedback, iterate! 💜
