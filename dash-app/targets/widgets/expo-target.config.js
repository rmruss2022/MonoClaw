/** @type {import('@bacons/apple-targets').Config} */
module.exports = {
  type: "widget",
  name: "DashWidgets",
  bundleIdentifier: ".widgets",
  deploymentTarget: "15.1",
  frameworks: ["WidgetKit", "SwiftUI", "AppIntents"],
};
