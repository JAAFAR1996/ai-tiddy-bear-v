# 🚀 Production Deployment Guide - AI Teddy Bear Parent App

## 📋 Pre-Deployment Checklist

### ✅ Security Requirements
- [ ] All API URLs use HTTPS in production
- [ ] SSL Certificate Pinning enabled (ENABLE_SSL_PINNING=true)
- [ ] Environment variables configured in CI/CD (not in code)
- [ ] Sensitive credentials stored in secure environment
- [ ] JWT tokens stored in Keychain/Keystore (not AsyncStorage)

### ✅ Configuration
- [ ] Production .env file created (not committed to git)
- [ ] API_BASE_URL points to production backend
- [ ] WS_BASE_URL uses WSS protocol
- [ ] APP_ENV=production
- [ ] ENABLE_ANALYTICS=true
- [ ] ENABLE_CRASH_REPORTING=true
- [ ] ENABLE_LOGGING=false
- [ ] ENABLE_DEV_TOOLS=false

## 🔧 Environment Configuration

### Production Environment Variables (.env)
```bash
# Production API Configuration
API_BASE_URL=https://api.aiteddybear.com
WS_BASE_URL=wss://api.aiteddybear.com

# App Configuration
APP_ENV=production
APP_VERSION=1.0.0

# Security (Production settings)
ENABLE_SSL_PINNING=true
API_TIMEOUT=10000

# Features
ENABLE_PUSH_NOTIFICATIONS=true
ENABLE_ANALYTICS=true
ENABLE_CRASH_REPORTING=true

# Debug (Disabled in production)
ENABLE_LOGGING=false
ENABLE_DEV_TOOLS=false
```

### Staging Environment Variables (.env.staging)
```bash
# Staging API Configuration
API_BASE_URL=https://api-staging.aiteddybear.com
WS_BASE_URL=wss://api-staging.aiteddybear.com

# App Configuration
APP_ENV=staging
APP_VERSION=1.0.0-beta

# Security (Staging settings)
ENABLE_SSL_PINNING=true
API_TIMEOUT=15000

# Features
ENABLE_PUSH_NOTIFICATIONS=true
ENABLE_ANALYTICS=false
ENABLE_CRASH_REPORTING=true

# Debug (Limited in staging)
ENABLE_LOGGING=true
ENABLE_DEV_TOOLS=false
```

## 🏗️ Build Commands

### Development Build
```bash
npm run start
# or
expo start --dev-client
```

### Production Build
```bash
# iOS
expo build:ios --release-channel production

# Android  
expo build:android --release-channel production

# Or using EAS Build (recommended)
eas build --platform ios --profile production
eas build --platform android --profile production
```

## 🔐 Security Validations

The app includes automatic security checks:

1. **HTTPS Enforcement**: App will throw error if production API doesn't use HTTPS
2. **WSS Enforcement**: WebSocket connections must use WSS in production
3. **Token Security**: All auth tokens stored in secure keychain/keystore
4. **SSL Pinning**: Optional SSL certificate pinning for enhanced security

## 📱 App Store Deployment

### iOS App Store
1. Configure app.config.js with correct bundle identifier
2. Set up Apple Developer certificates
3. Configure push notification certificates
4. Build with `eas build --platform ios --profile production`
5. Submit to App Store Connect

### Google Play Store
1. Configure app.config.js with correct package name
2. Set up Google Play Console
3. Configure Firebase for push notifications
4. Build with `eas build --platform android --profile production`
5. Upload to Google Play Console

## 🚨 Critical Security Notes

### ⚠️ Never Commit These Files:
- `.env`
- `.env.staging`
- `google-services.json`
- `GoogleService-Info.plist`
- `AuthKey_*.p8`
- `*.keystore`
- `*.jks`

### ✅ Production Security Features:
- JWT tokens stored in encrypted keychain/keystore
- HTTPS enforcement for all API calls
- WSS enforcement for WebSocket connections
- App transport security enabled
- Certificate pinning available
- Production builds disable debug features

## 🔄 CI/CD Integration

### GitHub Actions Example:
```yaml
- name: Set up environment
  run: |
    echo "API_BASE_URL=${{ secrets.API_BASE_URL }}" >> .env
    echo "WS_BASE_URL=${{ secrets.WS_BASE_URL }}" >> .env
    echo "APP_ENV=production" >> .env
    echo "ENABLE_SSL_PINNING=true" >> .env
```

### Required Secrets in CI/CD:
- `API_BASE_URL`: Production API endpoint
- `WS_BASE_URL`: Production WebSocket endpoint
- `EXPO_TOKEN`: Expo CLI authentication token
- `APPLE_CERT`: iOS certificates and provisioning profiles
- `ANDROID_KEYSTORE`: Android signing keystore

## 📊 Monitoring & Analytics

### Production Monitoring:
- Sentry for crash reporting (if enabled)
- Analytics tracking (if enabled)
- Performance monitoring
- API response time tracking
- WebSocket connection health

### Health Checks:
The app includes automatic health checks for:
- Backend API connectivity
- WebSocket connection status
- Secure storage functionality
- Push notification registration

## 🆘 Troubleshooting

### Common Issues:
1. **SSL/TLS Errors**: Ensure production API has valid SSL certificate
2. **WebSocket Connection Fails**: Check WSS protocol and port configuration
3. **Push Notifications Not Working**: Verify Firebase/Expo push credentials
4. **Token Storage Issues**: Check device keychain/keystore permissions

### Debug Production Issues:
```bash
# Enable production logging temporarily
ENABLE_LOGGING=true npm run start
```

## 📝 Post-Deployment Verification

### ✅ Verify After Deployment:
- [ ] App connects to production API successfully
- [ ] WebSocket connections work via WSS
- [ ] Push notifications are received
- [ ] User authentication flows work
- [ ] Child data synchronization works
- [ ] Safety alerts are received in real-time
- [ ] All HTTPS connections verified
- [ ] No debug logs in production
- [ ] Crash reporting active (if enabled)
- [ ] Analytics tracking active (if enabled)

---

## 🎯 Production Readiness Score

Current Status: **🔄 In Progress**

- ✅ Secure token storage (Completed)
- 🔄 HTTPS/WSS enforcement (In Progress)
- ⏳ Push notifications setup
- ⏳ Privacy policy screens
- ⏳ App store assets
- ⏳ Production testing
- ⏳ Security audit

**Target**: 100% Production Ready 🎯
