import React from 'react';
import { Text } from 'react-native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { NavigationContainer } from '@react-navigation/native';
import { theme } from '../theme';
import { HomeScreen } from '../screens/HomeScreen';
import { MeditationScreen } from '../screens/MeditationScreen';
import { ChatScreen } from '../screens/ChatScreen';
import { CommunityScreen } from '../screens/CommunityScreen';

type TabIconOptions = {
  focused: boolean;
  color: string;
  size: number;
};

const Tab = createBottomTabNavigator();

export const AppNavigator: React.FC = () => {
  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={{
          headerShown: false,
          tabBarStyle: {
            backgroundColor: theme.colors.warmWhite,
            borderTopColor: theme.colors.borderLight,
            borderTopWidth: 1,
            height: 80,
            paddingBottom: 24,
            paddingTop: 12,
          },
          tabBarActiveTintColor: theme.colors.sage,
          tabBarInactiveTintColor: theme.colors.textLight,
          tabBarLabelStyle: {
            fontSize: 11,
            fontWeight: '600',
            marginTop: 4,
          },
        }}
      >
        <Tab.Screen
          name="Home"
          component={HomeScreen}
          options={{
            tabBarIcon: (props: TabIconOptions) => (
              <TabIcon emoji="🏠" focused={props.focused} />
            ),
          }}
        />
        <Tab.Screen
          name="Meditate"
          component={MeditationScreen}
          options={{
            tabBarIcon: (props: TabIconOptions) => (
              <TabIcon emoji="🧘" focused={props.focused} />
            ),
          }}
        />
        <Tab.Screen
          name="Chat"
          component={ChatScreen}
          options={{
            tabBarIcon: (props: TabIconOptions) => (
              <TabIcon emoji="💬" focused={props.focused} />
            ),
          }}
        />
        <Tab.Screen
          name="Community"
          component={CommunityScreen}
          options={{
            tabBarIcon: (props: TabIconOptions) => (
              <TabIcon emoji="🤝" focused={props.focused} />
            ),
          }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
};

interface TabIconProps {
  emoji: string;
  focused: boolean;
}

const TabIcon: React.FC<TabIconProps> = ({ emoji, focused }) => {
  return (
    <Text style={{
      fontSize: focused ? 28 : 24,
      opacity: focused ? 1 : 0.6,
    }}>
      {emoji}
    </Text>
  );
};
