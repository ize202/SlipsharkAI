# Deploying SlipsharkAI

SlipsharkAI has Railway configuration, but this branch has not been deployed.
There is no verified production URL. `api.slipshark.com` remains an unverified
name until a separately approved deployment, DNS change, TLS check, and
end-to-end test all pass.

## Release gate

Run the full repository verifier on an attended Docker host before connecting
the repository to Railway:

```bash
./scripts/verify --full
docker image inspect slipshark:verify --format '{{.Config.User}}'
```

The verifier must exit successfully, and the image user must be `slipshark`.
It also proves that Redis is not published, the app is bound only to loopback,
readiness fails when Redis stops, and temporary Docker resources are removed.

This gate is currently pending. Do not interpret the Dockerfile or
`railway.json` as deployment evidence.

## Railway build and startup

`railway.json` selects Railway's Dockerfile builder. The Docker `CMD` owns
startup, maps Railway's `PORT` to `SLIPSHARK_PORT`, and preserves shutdown
signals with `exec`. There is no Procfile or duplicate Railway start command.

The configured health path is `/health/ready` with a 30-second timeout and a
bounded restart policy. `/health/live` only reports process liveness.
`/health/ready` checks Redis in the production runtime and returns `503` when
Redis is unavailable.

## Required environment

Store these values in Railway's secret or variable controls. Do not add them to
`railway.json`, the Dockerfile, a committed `.env` file, build arguments, logs,
or screenshots.

| Variable | Purpose |
| --- | --- |
| `SLIPSHARK_ENVIRONMENT=production` | Enables production configuration checks |
| `SLIPSHARK_OPENAI_API_KEY` | Server-side OpenAI credential |
| `SLIPSHARK_EXA_API_KEY` | Server-side Exa credential |
| `SLIPSHARK_API_KEYS` | JSON map of principal IDs to unique keys of at least 32 characters |
| `SLIPSHARK_REDIS_URL` | Managed `redis://` or `rediss://` connection string |

Railway supplies `PORT`; the image maps it at startup. The Dockerfile already
sets `SLIPSHARK_HOST=0.0.0.0`, so a Railway variable is not needed for the host.

Generate an API-key map on a trusted machine:

```bash
uv run python generate_key.py
```

The command prints one `SLIPSHARK_API_KEYS` value. Treat the printed key as a
secret and send it only to a trusted server-side caller.

## Deployment sequence

1. Pass the local full gate and record the exact Git commit.
2. Create a Railway service from that commit and select the repository's
   Dockerfile configuration.
3. Attach a managed Redis service and set all required environment values.
4. Deploy without a custom domain. Wait for `/health/ready` to pass.
5. Check `/health/live`, `/health/ready`, invalid-key rejection, rate limiting,
   and one approved end-to-end research request.
6. Review logs for request IDs and safe error codes. Keys and provider response
   bodies must not appear.
7. Add a domain only through a separate approved change after the Railway URL
   and end-to-end path are stable.

Creating Railway resources, setting secrets, deploying, and changing DNS are
external writes. They require an explicit approval window and are not part of
the repository-only verification.

## Health checks

Use the Railway-provided URL before adding DNS:

```bash
curl --fail --silent --show-error https://replace-with-railway-host/health/live
curl --fail --silent --show-error https://replace-with-railway-host/health/ready
```

Expected healthy responses:

```json
{"status":"ok"}
```

```json
{"status":"ready","configuration":"ready","redis":"ready"}
```

Liveness can remain `200` while readiness returns `503`. That difference is
intentional: a running process must not receive research traffic when the
production rate limiter is unavailable.

## Secret rotation

Rotate client API keys without an outage:

1. Generate a second key under a new principal ID.
2. Add it to `SLIPSHARK_API_KEYS` while retaining the old entry.
3. Deploy and move the trusted caller to the new key.
4. Verify authentication and rate limiting with the new principal.
5. Remove the old entry and deploy again.

For OpenAI or Exa, create the replacement credential first, update the Railway
secret, deploy and verify, then revoke the old credential. For Redis, provision
or rotate the connection, update `SLIPSHARK_REDIS_URL`, wait for readiness, and
only then retire the old connection. Never place both old and new provider
credentials in source control.

## Rollback

Use Railway's deployment history to redeploy the last known-good commit or
image. Restore any compatible secret values separately because a code rollback
does not prove that environment changes were reversed.

After rollback:

1. Confirm `/health/live` and `/health/ready`.
2. Send one invalid-key request and confirm rejection.
3. Send one approved research request through the trusted caller.
4. Check logs for the rollback deployment ID and safe request errors.
5. Keep the failed deployment available for diagnosis; do not force-push Git
   history to hide it.

## Custom domain

Custom DNS is the last step, not part of initial deployment. Record the current
DNS values before editing them, apply Railway's assigned target, wait for TLS,
then verify the health and research paths through the custom host. Restore the
recorded DNS values if certificate issuance or routing fails.

Until those checks pass, do not publish or describe `api.slipshark.com` as a
working endpoint.
