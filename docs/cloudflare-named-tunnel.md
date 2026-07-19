# Cloudflare named tunnel (stable public URL)

Use this when RunPod (or any external service) must call back into your Tagr API.
Quick tunnels (`*.trycloudflare.com`) change URL every restart; a **named tunnel** gives a fixed hostname.

## Prerequisites

- A domain on Cloudflare (free plan is fine)
- `cloudflared` installed (`https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/`)

## Steps

1. **Cloudflare Zero Trust** → **Networks** → **Tunnels** → **Create a tunnel**
2. Choose **Cloudflared**, name it (e.g. `tagr-dev`)
3. Copy the **tunnel token** (or install command)
4. **Public Hostname** tab → **Add a public hostname**
   - Subdomain: e.g. `tagr`
   - Domain: your domain
   - Service type: **HTTP**
   - URL: `http://127.0.0.1:8787` (or wherever `tagr-web` listens)
5. Save. Your API is now at `https://tagr.yourdomain.com`

## Tagr `.env`

```env
API_CALLBACK_URL=https://tagr.yourdomain.com/api/v1/internal/inference-callback
```

Restart the web container after changing this value.

## Run the tunnel

**Option A — token in `.env` (docker compose profile):**

```env
CLOUDFLARE_TUNNEL_TOKEN=eyJ...
```

```bash
docker compose --profile tunnel up cloudflared-named
```

**Option B — script:**

```bash
export CLOUDFLARE_TUNNEL_TOKEN=eyJ...
./scripts/cloudflare-tunnel.sh
```

**Option C — quick tunnel (temporary URL, dev only):**

```bash
./scripts/cloudflare-tunnel.sh
# Copy the https://....trycloudflare.com URL into API_CALLBACK_URL
```
