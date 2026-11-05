/**
 * Life OS navigation stack. Lives inside the "Life OS" bottom tab and drills
 * from the pillar dashboard → pillar → journey → practice.
 */
import React from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import { LifeOSProvider } from '../lifeos/store';
import { LifeOSScreen } from '../screens/lifeos/LifeOSScreen';
import { PillarScreen } from '../screens/lifeos/PillarScreen';
import { JourneyScreen } from '../screens/lifeos/JourneyScreen';
import { PracticeScreen } from '../screens/lifeos/PracticeScreen';

export type LifeOSStackParamList = {
  LifeOSHome: undefined;
  Pillar: { pillarId: string };
  Journey: { journeyId: string };
  Practice: { journeyId: string };
};

const Stack = createStackNavigator<LifeOSStackParamList>();

export const LifeOSNavigator: React.FC = () => (
  <LifeOSProvider>
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="LifeOSHome" component={LifeOSScreen} />
      <Stack.Screen name="Pillar" component={PillarScreen} />
      <Stack.Screen name="Journey" component={JourneyScreen} />
      <Stack.Screen name="Practice" component={PracticeScreen} />
    </Stack.Navigator>
  </LifeOSProvider>
);
