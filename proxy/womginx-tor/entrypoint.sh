#!/bin/sh
set -eu

TOR_IP="$(getent hosts tor | awk '{print $1; exit}')"
if [ -z "$TOR_IP" ]; then
    echo "Could not resolve tor container" >&2
    exit 1
fi

sed -i "s/listen 80;/listen ${PORT};/" /etc/nginx/nginx.conf
sed -i "s/ip = TOR_IP;/ip = ${TOR_IP};/" /etc/redsocks.conf
rm -f /etc/nginx/conf.d/default.conf

redsocks -c /etc/redsocks.conf &

iptables -t nat -N REDSOCKS || true
iptables -t nat -F REDSOCKS
iptables -t nat -A REDSOCKS -d 0.0.0.0/8 -j RETURN
iptables -t nat -A REDSOCKS -d 10.0.0.0/8 -j RETURN
iptables -t nat -A REDSOCKS -d 127.0.0.0/8 -j RETURN
iptables -t nat -A REDSOCKS -d 169.254.0.0/16 -j RETURN
iptables -t nat -A REDSOCKS -d 172.16.0.0/12 -j RETURN
iptables -t nat -A REDSOCKS -d 192.168.0.0/16 -j RETURN
iptables -t nat -A REDSOCKS -d 224.0.0.0/4 -j RETURN
iptables -t nat -A REDSOCKS -d 240.0.0.0/4 -j RETURN
iptables -t nat -A REDSOCKS -p tcp -j REDIRECT --to-ports 12345
iptables -t nat -D OUTPUT -p tcp -j REDSOCKS 2>/dev/null || true
iptables -t nat -A OUTPUT -p tcp -j REDSOCKS

exec nginx
