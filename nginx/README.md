# Nginx Routing

Prepared config:

```text
/home/yukang/ERP/nginx/sengchong.conf
```

Routes:

- `erp.sengchong.com` -> `http://127.0.0.1:5000`
- `sengchong.com` -> `http://127.0.0.1:5000`
- `www.sengchong.com` -> `http://127.0.0.1:5000`

DNS currently resolves all three names to `60.51.37.33`.

## Apply HTTP Config

Requires sudo because `/etc/nginx` is root-owned:

```bash
sudo cp /home/yukang/ERP/nginx/sengchong.conf /etc/nginx/sites-available/sengchong.conf
sudo ln -sf /etc/nginx/sites-available/sengchong.conf /etc/nginx/sites-enabled/sengchong.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

## Test HTTP

```bash
curl -I http://erp.sengchong.com/
curl -I http://sengchong.com/
curl -I http://www.sengchong.com/
```

Expected:

- `erp.sengchong.com` returns the ERP Gateway app on port `5000`
- `sengchong.com` and `www.sengchong.com` return the Sengchong website from the ERP app on port `5000`

## Enable HTTPS

Install certbot if needed:

```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
```

Issue certificates and let certbot update nginx:

```bash
sudo certbot --nginx \
  -d erp.sengchong.com \
  -d sengchong.com \
  -d www.sengchong.com \
  --redirect
```

Verify:

```bash
curl -I https://erp.sengchong.com/
curl -I https://sengchong.com/
curl -I https://www.sengchong.com/
sudo certbot renew --dry-run
```
