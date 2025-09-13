<div align="center">

# 🧸 AI Teddy Bear Server

خادم ذكاء اصطناعي متوافق مع COPPA للتواصل الصوتي الآمن مع دمى ESP32 عبر WebSocket.

[![Build](https://img.shields.io/badge/build-passing-brightgreen?style=flat-square)](#)
[![Security](https://img.shields.io/badge/security-COPPA%20Ready-0066ff?style=flat-square)](#)
[![Docker](https://img.shields.io/badge/docker-ready-0db7ed?style=flat-square&logo=docker&logoColor=white)](#)
[![Python](https://img.shields.io/badge/python-3.11+-3776ab?style=flat-square&logo=python&logoColor=white)](#)
[![License](https://img.shields.io/badge/license-Private-important?style=flat-square)](#)

</div>

— يتضمن: مصادقة HMAC للأجهزة، تصفية محتوى، مراقبة وإشعارات، نشر إنتاجي عبر Docker + Nginx + Certbot، وقابلية ملاحظة عبر Prometheus/Grafana.

## 🔎 نظرة عامة
- محادثة آمنة للأطفال بعمر 3–13: تحويل كلام→نص (Whisper) → رد ذكاء اصطناعي (OpenAI) → نص→كلام (TTS) ثم بث الصوت للـ ESP32.
- بوابة WebSocket للأجهزة: مصادقة HMAC على أساس `device_id` + `ESP32_SHARED_SECRET`، ورسائل بث صوتي آنية.
- نشر إنتاجي متكامل: Postgres, Redis, Nginx (SSL/HTTP2), Certbot, Prometheus, Grafana, نسخ احتياطي للقاعدة.
- ضبط مركزي واحد: `src/infrastructure/config/production_config.py` مع فحص أمني صارم للبيئة.

## ✨ الميزات الأساسية
- مصادقة HMAC للأجهزة: تمنع الوصول غير المصرح به (`ESP32_SHARED_SECRET`).
- أمان إنتاجي: HSTS, TLS 1.2+, قيود CORS/Hosts، تحديد معدلات، حماية brute-force.
- مراقبة وإشعارات: Prometheus/Grafana ومتكامل مع Sentry.
- نسخ احتياطي واستعادة لقاعدة البيانات.

## 🗂️ بنية المشروع (مختصر)
- `src/` — كود التطبيق والخدمات.
  - `src/adapters/esp32_router.py` — نقاط ESP32 العامة/الخاصة + تحقق HMAC.
  - `src/adapters/esp32_websocket_router.py` — مسار WebSocket الإنتاجي للأجهزة.
  - `src/services/esp32_chat_server.py` — خادم محادثة ESP32: إدارة الجلسات والصوت.
  - `src/infrastructure/config/production_config.py` — مصدر الضبط الموحد (بيئة/فحص).
  - `src/infrastructure/routing/route_manager.py` — تسجيل الراوترات وإدارة المسارات.
- `deployment/` — نشر إنتاجي: Docker Compose, Nginx, Certbot, Prometheus, Grafana.
  - `deployment/docker-compose.production.yml` — الكومة الإنتاجية كاملة.
  - `deployment/nginx/nginx.prod.conf` — عكس عناوين/SSL/WS.
- `migrations/`, `alembic.ini` — ترحيلات قاعدة البيانات.

## ⚙️ المتطلبات
- Docker + Docker Compose (للإنتاج).
- مفاتيح OpenAI صالحة.
- نطاق عام وإمكانية إصدار شهادات SSL (Let’s Encrypt).

## 🔐 إعداد البيئة (حد أدنى)
- أنشئ ملف بيئة (يمكن توليد قالب من الكود):
  - `src/infrastructure/config/production_config.py:680` يحتوي مولد قالب `.env`.
- المتغيرات الأساسية:
  - `ENVIRONMENT=production`
  - `SECRET_KEY`, `JWT_SECRET_KEY`, `COPPA_ENCRYPTION_KEY` (قيم عشوائية قوية)
  - `DATABASE_URL=postgresql://<user>:<pass>@postgres:5432/<db>`
  - `REDIS_URL=redis://:<password>@redis:6379/0`
  - `OPENAI_API_KEY=sk-...`
  - `PARENT_NOTIFICATION_EMAIL=parent@example.com`
  - `SENTRY_DSN=<dsn>`
  - `ESP32_SHARED_SECRET=<64-hex-secret-for-HMAC>`
  - `CORS_ALLOWED_ORIGINS`, `ALLOWED_HOSTS` (قوائم بدون *)

## 🚀 بدء سريع — إنتاج (Docker Compose)
- احرص على ضبط قيم البيئة في ملف `.env.production` أو متغيرات النظام.
- من داخل مجلد `deployment/`:
  - `docker-compose -f deployment/docker-compose.production.yml up -d`
  - تحقق من الصحة:
    - `docker-compose -f deployment/docker-compose.production.yml ps`
    - `docker-compose -f deployment/docker-compose.production.yml logs -f app`
  - الخدمات:
    - API عبر Nginx على المنفذ `443` (المضيف: `api.${PRODUCTION_DOMAIN}`)
    - Prometheus محليًا: `http://localhost:9090`
    - Grafana محليًا: `http://localhost:3000`

## 🧪 تشغيل محلي (تطوير)
- فعّل بيئة تطوير:
  - `python -m venv venv && source venv/bin/activate` (أو Windows PowerShell مع `venv\Scripts\Activate.ps1`)
  - `pip install -r requirements.txt`
  - صِف المتغيرات الأساسية (`ENVIRONMENT=development`, مفاتيح وهمية آمنة، Redis/Postgres محليين أو عبر Docker).
  - شغّل الخادم:
    - `uvicorn src.main:app --reload --host 0.0.0.0 --port 8000`

## 🔌 تكامل ESP32
- مسارات WebSocket للأجهزة:
  - خاص مؤمّن: `wss://<host>/api/v1/esp32/private/chat`
  - عام (عبر Nginx): `wss://<host>/ws/esp32/connect` (تم تفعيل نفس تحقق HMAC)
- بارامترات الاتصال (Query):
  - `device_id`, `child_id`, `child_name`, `child_age` (3–13)، و`token`.
- توليد التوكن `token`:
  - `token = HMAC_SHA256( key=ESP32_SHARED_SECRET, message=device_id ).hexdigest()` (حروف صغيرة بطول 64).
- تنسيق الرسائل (العميل → الخادم):
  - `{"type":"audio_start","audio_session_id":"uuid"}`
  - `{"type":"audio_chunk","audio_data":"<base64>","chunk_id":"uuid","audio_session_id":"uuid","is_final":false}`
  - `{"type":"audio_end","audio_session_id":"uuid"}`
- رد الخادم (الخادم → العميل):
  - `{"type":"audio_response","audio_data":"<base64>","text":"...","format":"mp3","sample_rate":22050}`

## 🔗 نقاط REST الهامة
- إعداد الجهاز العام:
  - `GET /api/v1/esp32/config` — إعدادات اتصال الجهاز، تشمل مسار WebSocket والتحديثات.
  - `GET /api/v1/esp32/firmware` — بيان التحديث (manifest) مع `sha256` والحجم والرابط.
- المطالبة بالجهاز (Claim):
  - `POST /api/v1/pair/claim` — ربط الجهاز مع الحساب الأبوي (HMAC + nonce).
- مقاييس خادم محادثة ESP32:
  - `GET /api/v1/esp32/metrics` (خاص، مصادقة).
- صحة النظام:
  - `GET /health` — فحص أساسي لصحة التطبيق.

## 🛡️ الأمان
- تحقق HMAC للأجهزة: `ESP32_SHARED_SECRET` إلزامي في الإنتاج.
- CORS و ALLOWED_HOSTS صارمة (بدون wildcards).
- TLS/SSL عبر Nginx + Certbot، HSTS مفعل.
- تحديد معدلات API و WebSocket، وحماية brute-force.
- مراقبة سريّة القيم عبر فاحص البيئة الأمني (قابل للتفعيل):
  - `src/infrastructure/startup/security_hooks.py`
  - `src/infrastructure/security/environment_validator.py`

## 📈 المراقبة والقياس
- Prometheus: `deployment/monitoring/prometheus.yml`
- Grafana: لوحات جاهزة في `deployment/monitoring/grafana/`
- Sentry: عيّن `SENTRY_DSN` لتتبع الأخطاء.

## 💾 النسخ الاحتياطي والاستعادة
- خدمة النسخ: `db-backup` (كرون افتراضي 2 صباحًا).
- تنفيذ يدوي داخل الحاوية:
  - نسخ احتياطي: `docker exec ai-teddy-db-backup-prod /backup.sh`
  - استعادة: `docker exec -it ai-teddy-db-backup-prod /restore.sh <backup.sql.enc>`

## 🧳 عمليات الترحيل (Database Migrations)
- تهيئة قاعدة البيانات:
  - `alembic upgrade head`
- ملفات: `migrations/`, `alembic.ini`

## 🧰 استكشاف الأخطاء الشائعة
- فشل اتصال WebSocket: تحقق من `ESP32_SHARED_SECRET`، وصحة `token` والحقل `device_id`، و`CORS/Hosts` والشهادة ووقت النظام على ESP32 (NTP).
- Healthcheck للحاوية يفشل: تأكد من `GET /health` يعمل (`deployment/docker-compose.production.yml` يستخدمه).
- بطء نشر Docker: استخدم `.dockerignore` لاستبعاد الأرشيفات والاختبارات والسجلات لتسريع بناء/تصدير الطبقات.

## 🧭 أوامر مفيدة
- تشغيل الكومة الإنتاجية:
  - `docker-compose -f deployment/docker-compose.production.yml up -d`
- سجلات التطبيق:
  - `docker-compose -f deployment/docker-compose.production.yml logs -f app`
- صحة الخدمات:
  - `docker-compose -f deployment/docker-compose.production.yml ps`

## 📚 مراجع ملفات سريعة
- `src/infrastructure/config/production_config.py`
- `src/adapters/esp32_router.py`
- `src/adapters/esp32_websocket_router.py`
- `src/services/esp32_chat_server.py`
- `deployment/docker-compose.production.yml`
- `deployment/nginx/nginx.prod.conf`

## 🤝 المساهمة والتطوير
- يُرحب بالمساهمات التي تُحسّن الأمان، الأداء، وتجربة الأطفال.
- التزم بضوابط المحتوى وسرية البيانات، ولا تدرج بيانات أطفال حقيقية في السجلات.

---

## 🧭 جدول المحتويات
- [نظرة عامة](#-نظرة-عامة)
- [الميزات الأساسية](#-الميزات-الأساسية)
- [بنية المشروع](#️-بنية-المشروع-مختصر)
- [المتطلبات](#-المتطلبات)
- [إعداد البيئة](#-إعداد-البيئة-حد-أدنى)
- [بدء سريع (إنتاج)](#-بدء-سريع--إنتاج-docker-compose)
- [تشغيل محلي](#-تشغيل-محلي-تطوير)
- [تكامل ESP32](#-تكامل-esp32)
- [نقاط REST](#-نقاط-rest-الهامة)
- [الأمان](#️-الأمان)
- [المراقبة](#-المراقبة-والقياس)
- [النسخ الاحتياطي](#-النسخ-الاحتياطي-والاستعادة)
- [الترحيل](#-عمليات-الترحيل-database-migrations)
- [استكشاف الأخطاء](#-استكشاف-الأخطاء-الشائعة)
- [أوامر مفيدة](#-أوامر-مفيدة)
- [مراجع](#-مراجع-ملفات-سريعة)
- [المساهمة](#-المساهمة-والتطوير)

---

## 📦 متغيرات البيئة (مختصر)
| المتغير | الوصف | مثال |
|---|---|---|
| `ENVIRONMENT` | وضع التشغيل | `production` |
| `SECRET_KEY` | مفتاح التطبيق | `…` |
| `JWT_SECRET_KEY` | توقيع JWT | `…` |
| `COPPA_ENCRYPTION_KEY` | تشفير بيانات الأطفال | `…` |
| `DATABASE_URL` | اتصال Postgres | `postgresql://user:pass@postgres:5432/db` |
| `REDIS_URL` | اتصال Redis | `redis://:password@redis:6379/0` |
| `OPENAI_API_KEY` | مفتاح OpenAI | `sk-…` |
| `PARENT_NOTIFICATION_EMAIL` | بريد تنبيهات | `parent@example.com` |
| `SENTRY_DSN` | تتبع الأخطاء | `https://…sentry.io/…` |
| `ESP32_SHARED_SECRET` | سر HMAC للأجهزة | `64-hex` |

