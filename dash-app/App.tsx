import React, { useRef, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { WebView } from 'react-native-webview';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';

type Tab = { key: string; label: string; icon: string; url: string };

const TABS: Tab[] = [
  { key: 'dash', label: 'Dash', icon: '◴', url: 'https://dash.bedrock.casa/' },
  { key: 'events', label: 'Events', icon: '▦', url: 'https://marquee.bedrock.casa/' },
];

const BG = '#0b0b12';

function Panel({ tab, active }: { tab: Tab; active: boolean }) {
  const ref = useRef<WebView>(null);
  const [loading, setLoading] = useState(true);
  return (
    <View
      style={[StyleSheet.absoluteFill, { opacity: active ? 1 : 0 }]}
      pointerEvents={active ? 'auto' : 'none'}
    >
      <WebView
        ref={ref}
        source={{ uri: tab.url }}
        style={{ flex: 1, backgroundColor: BG }}
        onLoadEnd={() => setLoading(false)}
        allowsBackForwardNavigationGestures
        decelerationRate="normal"
        originWhitelist={['*']}
        setSupportMultipleWindows={false}
        startInLoadingState
      />
      {loading && (
        <View style={styles.loader} pointerEvents="none">
          <ActivityIndicator color="#ff5c8a" />
        </View>
      )}
    </View>
  );
}

export default function App() {
  const [active, setActive] = useState('dash');
  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      <SafeAreaView style={styles.root} edges={['top', 'bottom']}>
        <View style={styles.body}>
          {TABS.map((t) => (
            <Panel key={t.key} tab={t} active={active === t.key} />
          ))}
        </View>
        <View style={styles.tabbar}>
          {TABS.map((t) => {
            const on = active === t.key;
            return (
              <TouchableOpacity key={t.key} style={styles.tab} onPress={() => setActive(t.key)} activeOpacity={0.7}>
                <Text style={[styles.tabIcon, on && styles.tabIconOn]}>{t.icon}</Text>
                <Text style={[styles.tabLabel, on && styles.tabLabelOn]}>{t.label}</Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: BG },
  body: { flex: 1, backgroundColor: BG },
  loader: { ...StyleSheet.absoluteFillObject, alignItems: 'center', justifyContent: 'center', backgroundColor: BG },
  tabbar: {
    flexDirection: 'row',
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: '#262636',
    backgroundColor: '#101019',
    paddingTop: 7,
  },
  tab: { flex: 1, alignItems: 'center', paddingVertical: 2 },
  tabIcon: { fontSize: 19, color: '#6b6980', lineHeight: 22 },
  tabIconOn: { color: '#ff5c8a' },
  tabLabel: { fontSize: 11, fontWeight: '600', color: '#6b6980', marginTop: 1 },
  tabLabelOn: { color: '#ff5c8a' },
});
