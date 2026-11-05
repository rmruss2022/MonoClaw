// Metro config for the open-home monorepo.
//
// apps/mobile is an npm workspace. Dependencies hoist to the monorepo root
// (open-home/node_modules), but some packages (e.g. react) stay in the
// workspace (apps/mobile/node_modules). Metro's default resolver only looks
// from the project root upward, so a hoisted package that requires a
// workspace-local package (e.g. use-sync-external-store -> react) fails with
// "Unable to resolve module react". Watching the workspace root and listing
// both node_modules directories in nodeModulesPaths fixes resolution.
//
// See https://docs.expo.dev/guides/monorepos/
const { getDefaultConfig } = require("expo/metro-config");
const path = require("path");

const projectRoot = __dirname;
const workspaceRoot = path.resolve(projectRoot, "../..");

const config = getDefaultConfig(projectRoot);

config.watchFolders = [workspaceRoot];
config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, "node_modules"),
  path.resolve(workspaceRoot, "node_modules"),
];

module.exports = config;
