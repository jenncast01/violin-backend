#!/bin/bash
set -e

# Crear directorios de logs
mkdir -p /var/log/uvicorn /var/run/fail2ban

# Limpiar archivos de log anteriores (evita symlinks que bloquean fail2ban)
rm -f /var/log/uvicorn/access.log
touch /var/log/uvicorn/access.log

# Limpiar socket/pid de fail2ban de ejecuciones anteriores
rm -f /var/run/fail2ban/fail2ban.sock /var/run/fail2ban/fail2ban.pid
touch /var/log/fail2ban.log

# Arrancar Uvicorn en background escribiendo logs a archivo
uvicorn main:app \
  --host 0.0.0.0 \
  --port 5000 \
  --access-log \
  --log-level info \
  --log-config /app/log_config.json &

sleep 2

# Arrancar Fail2ban
fail2ban-client -x start

echo "[violin-backend] Uvicorn + Fail2ban corriendo exitosamente."
exec tail -F /var/log/fail2ban.log
