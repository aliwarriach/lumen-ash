// Extends app.json. Release builds ask Android for fewer permissions than the defaults.
//
// The defaults include "draw over other apps" and read/write of shared storage. This app uses
// none of them: it saves no files and shows nothing over other apps. They are only removed from
// the production build, so development builds (which may use them) are unaffected.
const UNUSED_PERMISSIONS = [
  "android.permission.SYSTEM_ALERT_WINDOW",
  "android.permission.READ_EXTERNAL_STORAGE",
  "android.permission.WRITE_EXTERNAL_STORAGE",
];

module.exports = ({ config }) => ({
  ...config,
  android: {
    ...config.android,
    blockedPermissions:
      process.env.EAS_BUILD_PROFILE === "production"
        ? [...(config.android?.blockedPermissions ?? []), ...UNUSED_PERMISSIONS]
        : config.android?.blockedPermissions,
  },
});
