import os
import re
import sys
import traceback
from datetime import datetime, timedelta

from curl_cffi import requests
from dotenv import load_dotenv

from notify.email import info, send_error_mail

load_dotenv()

PLATFORM = "V2EX"


def _headers(cookie: str) -> dict:
    return {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "referer": "https://www.v2ex.com/mission/daily",
        "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "cookie": cookie,
    }


def get_once(headers: dict) -> tuple[str | None, bool]:
    res = requests.get("https://www.v2ex.com/mission/daily", headers=headers)
    content = res.text

    if re.search(r"需要先登录", content):
        raise RuntimeError("V2EX cookie is overdated.")

    if re.search(r"每日登录奖励已领取", content):
        info("Already signed today.")
        return None, True

    once_match = re.search(r"redeem\?once=(.*?)'", content)
    if once_match:
        once = once_match.group(1)
        info(f"Successfully got once {once}")
        return once, False

    raise RuntimeError("Not signed yet, but failed to extract once token.")


def check_in(once: str, headers: dict) -> None:
    url = f"https://www.v2ex.com/mission/daily/redeem?once={once}"
    res = requests.get(url, headers=headers)

    if re.search(r"已成功领取每日登录奖励", res.text):
        info("V2EX check-in successful.")
        return

    raise RuntimeError("V2EX check-in failed (redeem page did not confirm).")


def balance(headers: dict) -> tuple[str | None, str | None]:
    res = requests.get("https://www.v2ex.com/balance", headers=headers)
    pattern = (
        r'每日登录奖励.*?<small class="gray">(.*?)</small>.*?'
        r'<td class="d" style="text-align: right;">.*?</td>.*?'
        r'<td class="d" style="text-align: right;">(.*?)</td>'
    )
    match = re.search(pattern, res.text, re.DOTALL)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return None, None


def main() -> None:
    cookie = os.environ.get("V2EX_COOKIE", "").strip()
    if not cookie:
        raise ValueError("Environment variable V2EX_COOKIE is not set")

    headers = _headers(cookie)
    now = datetime.utcnow() + timedelta(hours=8)
    info(now.strftime("%Y/%m/%d %H:%M:%S") + " from V2EX")

    once, signed = get_once(headers)
    if signed:
        return

    check_in(once, headers)
    bal_time, bal_value = balance(headers)
    if bal_time and bal_value:
        info(f"Balance at {bal_time}: {bal_value}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        tb = traceback.format_exc()
        print(tb, file=sys.stderr, flush=True)
        send_error_mail(f"[CloudCheckin] {PLATFORM} failed", tb)
        sys.exit(1)
