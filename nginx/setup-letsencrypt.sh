#!/bin/bash
# Let's Encrypt SSL Certificate Setup Script
# Run as root on the production server

set -euo pipefail

DOMAIN="medical-platform.example.com"  # REPLACE with your actual domain
EMAIL="admin@example.com"               # REPLACE with your email
WEBROOT="/var/www/letsencrypt"
NGINX_CONF="/etc/nginx/sites-available/medical-platform"

echo "=== Let's Encrypt SSL Setup for $DOMAIN ==="

# 1. Create webroot directory
mkdir -p "$WEBROOT"
chown -R www-data:www-data "$WEBROOT"

# 2. Install certbot if not present
if ! command -v certbot &> /dev/null; then
    echo "Installing certbot..."
    apt-get update && apt-get install -y certbot python3-certbot-nginx
fi

# 3. Ensure nginx is running with HTTP config first
echo "Starting nginx with HTTP-only config..."
nginx -t && systemctl reload nginx

# 4. Obtain certificate
echo "Obtaining SSL certificate for $DOMAIN..."
certbot certonly \
    --webroot \
    -w "$WEBROOT" \
    -d "$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --non-interactive

# 5. Deploy the production nginx config
echo "Deploying production nginx configuration..."
cp nginx/medical-platform.conf "$NGINX_CONF"
sed -i "s/medical-platform.example.com/$DOMAIN/g" "$NGINX_CONF"

# Update SSL certificate paths in nginx config
sed -i "s|medical-platform.example.com|$DOMAIN|g" "$NGINX_CONF"

# 6. Test and reload nginx
nginx -t && systemctl reload nginx

# 7. Setup auto-renewal
echo "Setting up auto-renewal..."
cat > /etc/cron.d/certbot-renew << 'EOF'
# Renew Let's Encrypt certificates twice daily
0 */12 * * * root certbot renew --quiet --post-hook "systemctl reload nginx"
EOF

# 8. Test renewal
certbot renew --dry-run

echo "=== SSL Setup Complete ==="
echo "Certificate installed for $DOMAIN"
echo "Auto-renewal configured (runs twice daily)"
echo "Nginx reloaded with production config"