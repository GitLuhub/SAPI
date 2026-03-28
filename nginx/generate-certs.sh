#!/usr/bin/env bash
# Genera un certificado TLS autofirmado para desarrollo local.
# Uso: ./nginx/generate-certs.sh
# En producción, coloca tu cert/key en nginx/ssl/ o apunta mediante SSL_CERT_PATH/SSL_KEY_PATH.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSL_DIR="$SCRIPT_DIR/ssl"

mkdir -p "$SSL_DIR"

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$SSL_DIR/key.pem" \
  -out "$SSL_DIR/cert.pem" \
  -subj "/C=ES/ST=Madrid/L=Madrid/O=SAPI/OU=Dev/CN=localhost" \
  2>/dev/null

echo "Certificado autofirmado generado en nginx/ssl/"
echo "  cert: $SSL_DIR/cert.pem"
echo "  key:  $SSL_DIR/key.pem"
echo ""
echo "ADVERTENCIA: Este certificado es solo para desarrollo."
echo "El navegador mostrará una advertencia de seguridad — es esperado."
