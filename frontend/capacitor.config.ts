import type { CapacitorConfig } from "@capacitor/cli";

/**
 * LAN clinic (default): http scheme + cleartext so phones can call http://192.168.x.x:8000.
 * Cloud HTTPS production: set CAPACITOR_HTTPS=true before `npm run mobile:build`
 * (requires API at https://… and no cleartext LAN).
 */
const httpsBuild = process.env.CAPACITOR_HTTPS === "true";

const config: CapacitorConfig = {
  appId: "com.healthcare.secure",
  appName: "Aarogya One Connect",
  webDir: "out",
  server: {
    androidScheme: httpsBuild ? "https" : "http",
    iosScheme: "https",
    cleartext: !httpsBuild,
  },
};

export default config;
