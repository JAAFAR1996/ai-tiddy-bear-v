#!/bin/sh
set -e
: "${PORT:=8000}"   # افتراضي محلي إذا ما مرّت Render PORT
exec sh -c "$*"     # شغّل الأمر عبر shell حتى تتوسّع المتغيرات
