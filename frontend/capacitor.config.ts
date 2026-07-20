import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.healthcare.secure",
  appName: "Healthcare Secure",
  webDir: "out",
  server: {
    // Use http so the WebView can call the LAN API over HTTP without
    // mixed-content blocks (https://localhost → http://192.168.x.x fails).
    androidScheme: "http",
    iosScheme: "https",
    cleartext: true,
  },
};

export default config;
