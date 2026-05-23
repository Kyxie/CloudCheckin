# CloudCheckin

<div align="center">

基于 Docker + Kubernetes (k3s) CronJob 的多平台自动签到与答题。

[English Version](./README-en.md) | 中文版本
</div>

## 功能

每天通过 k3s CronJob 触发签到任务，仅在失败时通过 SMTP 邮件告警；成功仅写入容器 stdout，由 `kubectl logs` 查看。

- **Nodeseek** — 自动签到（支持多账号，cookie 用 `&` 分隔）
- **Deepflood** — 自动签到（支持多账号）
- **V2EX** — 自动签到
- **一亩三分地** — 自动签到 + 自动答题（依赖 2Captcha）

## 架构

```
                       ┌────────────────────────────┐
git repo (sops 加密)   │  Flux 把 CronJob / Secret  │
   ──────────────────► │   同步到 k3s 集群           │
                       └────────────┬───────────────┘
                                    │
                  ┌─────────────────┼─────────────────┐
                  ▼                 ▼                 ▼
          CronJob: nodeseek   CronJob: v2ex   CronJob: ...
                  │                 │                 │
                  └─────────────► 同一镜像 cloudcheckin
                                    │
                                    ▼
                          失败 → SMTP 邮件 (MAIL_TO)
                          成功 → stdout (kubectl logs)
```

每个 CronJob 通过 `args` 指定入口模块，例如：

```yaml
args: ["-m", "nodeseek.nodeseek"]
```

## 构建镜像

```bash
docker build -t cloudcheckin:latest .
```

镜像 `ENTRYPOINT` 是 `python`，入口模块由调用方通过 `args` 提供：

| 平台 | 入口 |
| --- | --- |
| Nodeseek | `python -m nodeseek.nodeseek` |
| Deepflood | `python -m deepflood.deepflood` |
| V2EX | `python -m v2ex.v2ex` |
| 一亩三分地 | `python -m onepoint3acres.onepoint3acres` |

## 环境变量

| 变量 | 用途 |
| --- | --- |
| `NODESEEK_COOKIE` | Nodeseek cookie，多账号用 `&` 分隔 |
| `DEEPFLOOD_COOKIE` | Deepflood cookie |
| `V2EX_COOKIE` | V2EX cookie（注意 `"` 和 `$` 需要转义） |
| `ONEPOINT3ACRES_COOKIE` | 一亩三分地 cookie |
| `TWOCAPTCHA_APIKEY` | [2Captcha](https://2captcha.com/) API key（一亩三分地需要） |
| `SMTP_HOST` | SMTP 服务器，例如 `smtp.gmail.com` |
| `SMTP_PORT` | SMTP 端口，默认 `587` |
| `SMTP_USER` | SMTP 用户名（可选，匿名 relay 留空） |
| `SMTP_PASS` | SMTP 密码 / 授权码 |
| `SMTP_TLS` | `starttls`（默认） / `ssl` / `none` |
| `MAIL_FROM` | 发件人地址（留空回退到 `SMTP_USER`） |
| `MAIL_TO` | 收件人地址 |

未配置 SMTP 时失败仍会以非零退出码退出，且邮件发送会被跳过并在 stderr 写入提示。

## 本地调试

```bash
pip install -r requirements.txt
cp .env.localtest.example .env  # 填入你的配置

python -m nodeseek.nodeseek
python -m deepflood.deepflood
python -m v2ex.v2ex
python -m onepoint3acres.onepoint3acres
```

或者用 Docker 直接跑一次：

```bash
docker run --rm --env-file .env cloudcheckin:latest -m nodeseek.nodeseek
```

## 部署提示（k3s + Flux + sops）

本仓库不包含 k8s 清单。在你的 Flux 仓库中：

1. 用 sops 加密包含上述环境变量的 `Secret`，由 Flux/SOPS controller 解密。
2. 为每个平台创建 `CronJob`，`image` 指向你构建并推送的 `cloudcheckin` 镜像，`args` 指向对应入口模块，`envFrom` 引用上一步的 `Secret`。
3. `restartPolicy: OnFailure`，`successfulJobsHistoryLimit` / `failedJobsHistoryLimit` 按需调整。

## 常见问题

1. **为什么 cookie 会过期？** 各站点的 cookie 通常 30-90 天会失效，签到失败邮件就是它的信号。
2. **为什么用 `curl_cffi`？** 它能更精确地模拟浏览器 TLS/JA3 指纹，对站点风控更友好。
3. **2Captcha 费用？** 一亩三分地通过 Cloudflare Turnstile 验证，每次约 \$0.00145，\$3 充值约 2068 次（约 2.83 年）。

## 参考

- [curl_cffi](https://github.com/lexiforest/curl_cffi)
- [2captcha](https://github.com/2captcha/2captcha-python)
- [1point3acres](https://github.com/harryhare/1point3acres)
- [V2EX](https://github.com/CruiseTian/action-hub)
- [nodeseek](https://github.com/xinycai/nodeseek_signin)
