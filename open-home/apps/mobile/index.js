import { registerRootComponent } from "expo";
import App from "./App";

// registerRootComponent calls AppRegistry.registerComponent('main', () => App)
// and sets up the environment for both Expo Go and native (bare) builds. Using an
// explicit entry (rather than node_modules/expo/AppEntry.js) survives dependency
// hoisting in the open-home workspace.
registerRootComponent(App);
