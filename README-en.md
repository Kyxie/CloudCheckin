# CloudCheckin

<div align="center">

Multi-platform automated daily check-in and quiz answering, powered by Docker + Kubernetes (k3s) CronJob.

English Version | [中文版本](./README.md)
</div>

## Features

Check-in tasks are triggered daily via k3s CronJobs. Failures are reported by SMTP email; successes are written to container stdout and viewable via `kubectl logs`.

- **Nodeseek** — automated daily check-in (multi-account supported, separate cookies with `&`)
- **Deepflood** — automated daily check-in (multi-account supported)
- **V2EX** — automated daily check-in
- **1Point3Acres** — automated daily check-in + quiz answering (requires 2Captcha)

## Architecture

```
                       ┌────────────────────────────┐
git repo (sops-encrypted)  │  Flux syncs CronJob /      │
   ──────────────────►     │  Secret to k3s cluster     │
                       └────────────┬───────────────┘
                                    │
                  ┌─────────────────┼─────────────────┐
                  ▼                 ▼                 ▼
          CronJob: nodeseek   CronJob: v2ex   CronJob: ...
                  │                 │                 │
                  └─────────────► same image: cloudcheckin
                                    │
                                    ▼
                          failure → SMTP email (MAIL_TO)
                          success → stdout (kubectl logs)
```

Each CronJob specifies its entry module via `args`, for example:

```yaml
args: ["-m", "nodeseek.nodeseek"]
```

## Building the Image

```bash
docker build -t cloudcheckin:latest .
```

The image `ENTRYPOINT` is `python`; the entry module is supplied by the caller via `args`:

| Platform      | Entry point                               |
| ------------- | ----------------------------------------- |
| Nodeseek      | `python -m nodeseek.nodeseek`             |
| Deepflood     | `python -m deepflood.deepflood`           |
| V2EX          | `python -m v2ex.v2ex`                     |
| 1Point3Acres  | `python -m onepoint3acres.onepoint3acres` |

## Environment Variables

| Variable              | Description                                                                |
| --------------------- | -------------------------------------------------------------------------- |
| `NODESEEK_COOKIE`     | Nodeseek session cookie; separate multiple accounts with `&`               |
| `DEEPFLOOD_COOKIE`    | Deepflood session cookie; separate multiple accounts with `&`              |
| `V2EX_COOKIE`         | V2EX session cookie (escape `"` and `$` if needed)                        |
| `ONEPOINT3ACRES_COOKIE` | 1Point3Acres session cookie                                              |
| `TWOCAPTCHA_APIKEY`   | [2Captcha](https://2captcha.com/) API key (required for 1Point3Acres)      |
| `SMTP_HOST`           | SMTP server hostname, e.g. `smtp.gmail.com`                               |
| `SMTP_PORT`           | SMTP port, default `587`                                                   |
| `SMTP_USER`           | SMTP username (optional; leave blank for anonymous relay)                  |
| `SMTP_PASS`           | SMTP password or app token                                                 |
| `SMTP_TLS`            | TLS mode: `starttls` (default) / `ssl` / `none`                           |
| `MAIL_FROM`           | Sender address (falls back to `SMTP_USER` if blank)                       |
| `MAIL_TO`             | Recipient address for failure notifications                                |

If SMTP is not configured, failures still exit with a non-zero code and a warning is written to stderr; email sending is silently skipped.

## Local Testing

```bash
pip install -r requirements.txt
cp .env.localtest.example .env  # fill in your credentials

python -m nodeseek.nodeseek
python -m deepflood.deepflood
python -m v2ex.v2ex
python -m onepoint3acres.onepoint3acres
```

Or run a one-off container with Docker:

```bash
docker run --rm --env-file .env cloudcheckin:latest -m nodeseek.nodeseek
```

## Deployment (k3s + Flux + sops)

This repository does not include Kubernetes manifests. In your Flux repository:

1. Encrypt a `Secret` containing the environment variables above using sops; let the Flux/SOPS controller decrypt it at runtime.
2. Create a `CronJob` for each platform, pointing `image` at your built `cloudcheckin` image, setting `args` to the corresponding entry module, and referencing the `Secret` via `envFrom`.
3. Set `restartPolicy: OnFailure`; tune `successfulJobsHistoryLimit` and `failedJobsHistoryLimit` as needed.

## FAQ

1. **Why do cookies expire?** Site cookies typically expire after 30–90 days. A check-in failure email is your signal to refresh them.
2. **Why `curl_cffi`?** It accurately emulates browser TLS/JA3 fingerprints, which helps bypass site anti-bot measures.
3. **What does 2Captcha cost?** 1Point3Acres uses Cloudflare Turnstile; each solve costs ~$0.00145. A $3 top-up covers ~2,068 solves (~2.83 years of daily runs).

## References

- [curl_cffi](https://github.com/lexiforest/curl_cffi)
- [2captcha](https://github.com/2captcha/2captcha-python)
- [1point3acres](https://github.com/harryhare/1point3acres)
- [V2EX](https://github.com/CruiseTian/action-hub)
- [nodeseek](https://github.com/xinycai/nodeseek_signin)
