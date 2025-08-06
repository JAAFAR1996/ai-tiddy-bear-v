import 'dotenv/config';

export default {
  expo: {
    name: "AI Teddy Parent",
    slug: "ai-teddy-parent",
    version: process.env.APP_VERSION || "1.0.0",
    orientation: "portrait",
    icon: "./assets/icon.png",
    userInterfaceStyle: "light",
    splash: {
      image: "./assets/splash-icon.png",
      resizeMode: "contain",
      backgroundColor: "#007AFF"
    },
    assetBundlePatterns: [
      "**/*"
    ],
    ios: {
      supportsTablet: false,
      bundleIdentifier: "com.aiteddybear.parent",
      infoPlist: {
        NSCameraUsageDescription: "This app needs access to camera for QR code scanning.",
        NSMicrophoneUsageDescription: "This app needs access to microphone for voice interactions."
      }
    },
    android: {
      adaptiveIcon: {
        foregroundImage: "./assets/adaptive-icon.png",
        backgroundColor: "#007AFF"
      },
      package: "com.aiteddybear.parent",
      permissions: [
        "android.permission.INTERNET",
        "android.permission.RECORD_AUDIO",
        "android.permission.CAMERA"
      ]
    },
    web: {
      favicon: "./assets/favicon.png",
      bundler: "metro"
    },
    plugins: [
      "expo-secure-store",
      [
        "expo-notifications",
        {
          icon: "./assets/icon.png",
          color: "#007AFF",
          sounds: ["./assets/notification-sound.wav"],
          androidMode: "exact",
          androidCollapsedTitle: "AI Teddy Bear تنبيهات"
        }
      ]
    ],
    notification: {
      icon: "./assets/icon.png",
      color: "#007AFF",
      androidMode: "collapse",
      androidCollapsedTitle: "AI Teddy Bear"
    },
    extra: {
      // Environment variables for runtime configuration
      API_BASE_URL: process.env.API_BASE_URL,
      WS_BASE_URL: process.env.WS_BASE_URL,
      DEV_API_BASE_URL: process.env.DEV_API_BASE_URL,
      DEV_WS_BASE_URL: process.env.DEV_WS_BASE_URL,
      APP_ENV: process.env.APP_ENV || (__DEV__ ? 'development' : 'production'),
      APP_VERSION: process.env.APP_VERSION || "1.0.0",
      ENABLE_SSL_PINNING: process.env.ENABLE_SSL_PINNING,
      API_TIMEOUT: process.env.API_TIMEOUT,
      ENABLE_PUSH_NOTIFICATIONS: process.env.ENABLE_PUSH_NOTIFICATIONS,
      ENABLE_ANALYTICS: process.env.ENABLE_ANALYTICS,
      ENABLE_CRASH_REPORTING: process.env.ENABLE_CRASH_REPORTING,
      ENABLE_LOGGING: process.env.ENABLE_LOGGING,
      ENABLE_DEV_TOOLS: process.env.ENABLE_DEV_TOOLS,
      eas: {
        projectId: "ai-teddy-bear-parent-2025"
      }
    }
  }
};