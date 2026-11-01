import React from "react";
import { Text, View, StyleSheet } from "react-native";
import { NavigationContainer, DefaultTheme } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { useAuth } from "@/context/AuthContext";
import { colors, font } from "@/theme";
import { PrimaryButton } from "@/components/ui";
import LoginScreen from "@/screens/LoginScreen";
import HomeScreen from "@/screens/HomeScreen";
import LightsScreen from "@/screens/LightsScreen";
import ClimateScreen from "@/screens/ClimateScreen";
import SpeakersScreen from "@/screens/SpeakersScreen";
import SettingsScreen from "@/screens/SettingsScreen";

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

const ICONS: Record<string, string> = {
  Home: "⌂",
  Lights: "☀",
  Climate: "❄",
  Speakers: "♪",
  Settings: "⚙",
};

function tabIcon(name: string) {
  return ({ color }: { color: string }) => (
    <Text style={{ fontSize: 20, color }}>{ICONS[name]}</Text>
  );
}

function NoHome() {
  const { email, signOut } = useAuth();
  return (
    <View style={noHomeStyles.wrap}>
      <Text style={noHomeStyles.title}>No home paired yet</Text>
      <Text style={noHomeStyles.body}>
        {email ? `${email} is signed in, ` : ""}but no hub is linked to this account.
        Pair your openhome hub, then reopen the app.
      </Text>
      <View style={{ height: 20 }} />
      <PrimaryButton label="Sign out" onPress={signOut} />
    </View>
  );
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
            tabBarLabelStyle: { fontSize: 11, fontWeight: "700" },
            tabBarIcon: tabIcon(route.name),
          })}
        >
          <Tab.Screen name="Home" component={HomeScreen} />
          <Tab.Screen name="Lights" component={LightsScreen} />
          <Tab.Screen name="Climate" component={ClimateScreen} />
          <Tab.Screen name="Speakers" component={SpeakersScreen} />
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
