import React from "react";
import { Text, View, StyleSheet } from "react-native";
import { NavigationContainer, DefaultTheme } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import Ionicons from "@expo/vector-icons/Ionicons";
import { useAuth } from "@/context/AuthContext";
import { colors, font } from "@/theme";
import { PrimaryButton } from "@/components/ui";
import LoginScreen from "@/screens/LoginScreen";
import HomeScreen from "@/screens/HomeScreen";
import LightsScreen from "@/screens/LightsScreen";
import ClimateScreen from "@/screens/ClimateScreen";
import MusicScreen from "@/screens/MusicScreen";
import RemoteScreen from "@/screens/RemoteScreen";
import TvScreen from "@/screens/TvScreen";
import SettingsScreen from "@/screens/SettingsScreen";
import AccountScreen from "@/screens/AccountScreen";
import ConnectHubScreen from "@/screens/ConnectHubScreen";

const Tab = createBottomTabNavigator();

const navTheme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    background: colors.bg,
    card: colors.bg,
    text: colors.text,
    border: colors.line,
    primary: colors.accent,
  },
};

// Real vector icons, not Unicode glyphs. iOS renders ☀ ❄ ▶ with emoji
// presentation by default, so the old tab bar came out as colour emoji that
// ignored the active/inactive tint entirely.
const ICONS: Record<string, { on: keyof typeof Ionicons.glyphMap; off: keyof typeof Ionicons.glyphMap }> = {
  Home: { on: "home", off: "home-outline" },
  Lights: { on: "bulb", off: "bulb-outline" },
  Climate: { on: "thermometer", off: "thermometer-outline" },
  Music: { on: "disc", off: "disc-outline" },
  Remote: { on: "mic", off: "mic-outline" },
  TV: { on: "tv", off: "tv-outline" },
  Account: { on: "person-circle", off: "person-circle-outline" },
  Settings: { on: "settings", off: "settings-outline" },
};

function tabIcon(name: string) {
  return ({ color, focused }: { color: string; focused: boolean }) => {
    const set = ICONS[name];
    if (!set) return null;
    return <Ionicons name={focused ? set.on : set.off} size={23} color={color} />;
  };
}

function NoHome() {
  // The old version told the user to pair a hub and reopen the app — a dead
  // end with Sign out as its only button. ConnectHubScreen searches, offers a
  // pairing code, and accepts a manual address, so every branch has a way on.
  return <ConnectHubScreen />;
}

const noHomeStyles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", padding: 32 },
  title: { color: colors.text, fontSize: font.h2, fontWeight: "700", marginBottom: 8 },
  body: { color: colors.muted, fontSize: font.body, textAlign: "center", lineHeight: 22 },
});

export default function RootNavigator() {
  const { status } = useAuth();

  return (
    <NavigationContainer theme={navTheme}>
      {status === "noHome" ? (
        <NoHome />
      ) : status === "signedIn" ? (
        <Tab.Navigator
          screenOptions={({ route }) => ({
            headerShown: false,
            tabBarStyle: {
              backgroundColor: colors.panel,
              borderTopColor: colors.line,
              height: 84,
              paddingTop: 8,
            },
            tabBarActiveTintColor: colors.accent,
            tabBarInactiveTintColor: colors.muted,
            // Eight tabs is one or two more than a bottom bar comfortably
            // holds, hence the smaller label and the tighter item padding.
            // A "More" tab is the real answer if this grows again.
            tabBarLabelStyle: { fontSize: 9.5, fontWeight: "700" },
            tabBarItemStyle: { paddingHorizontal: 0 },
            tabBarIcon: tabIcon(route.name),
          })}
        >
          <Tab.Screen name="Home" component={HomeScreen} />
          <Tab.Screen name="Music" component={MusicScreen} />
          <Tab.Screen name="Remote" component={RemoteScreen} />
          <Tab.Screen name="Lights" component={LightsScreen} />
          <Tab.Screen name="Climate" component={ClimateScreen} />
          <Tab.Screen name="TV" component={TvScreen} />
          <Tab.Screen name="Account" component={AccountScreen} />
          <Tab.Screen name="Settings" component={SettingsScreen} />
        </Tab.Navigator>
      ) : (
        // Reuse the tab container shape-free: a single-screen stack would be nicer,
        // but Login is self-contained and status flips the tree on sign-in.
        <LoginScreen />
      )}
    </NavigationContainer>
  );
}
