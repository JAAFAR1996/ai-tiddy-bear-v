#!/bin/sh
set -eu

if [ "${TLS_SELF_SIGNED:-false}" != "true" ]; then
  exit 0
fi

DOMAIN="${PRODUCTION_DOMAIN:-${DOMAIN:-aiteddybear.com}}"
CERT_DIR="/etc/nginx/ssl/live/${DOMAIN}"

mkdir -p "$CERT_DIR"

if [ -s "$CERT_DIR/fullchain.pem" ] && [ -s "$CERT_DIR/privkey.pem" ]; then
  echo "NGINX: TLS certificates found at $CERT_DIR; skipping self-signed generation."
  exit 0
fi

echo "NGINX: Generating self-signed certificate for $DOMAIN"
openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout "$CERT_DIR/privkey.pem" \
  -out "$CERT_DIR/fullchain.pem" \
  -days "${TLS_SELF_SIGNED_DAYS:-365}" \
  -subj "/CN=${DOMAIN}"

chmod 600 "$CERT_DIR/privkey.pem"
chmod 644 "$CERT_DIR/fullchain.pem"