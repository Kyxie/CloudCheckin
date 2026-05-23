import os
import random
import sys
import time
import traceback

from curl_cffi import requests
from dotenv import load_dotenv

from notify.email import info, send_error_mail

load_dotenv()

PLATFORM = "NODESEEK"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Origin": "https://www.nodeseek.com",
    "Referer": "https://www.nodeseek.com/board",
    "Content-Type": "application/json",
}


def main() -> None:
    cookies = os.environ.get("NODESEEK_COOKIE", "").strip()
    if not cookies:
        raise ValueError("Environment variable NODESEEK_COOKIE is not set")

    cookie_list = cookies.split("&")

    for idx, cookie in enumerate(cookie_list, start=1):
        info(f"Using account {idx} for check-in...")
        random_delay = random.randint(1, 20)
        info(f"Account {idx} will wait for {random_delay} seconds...")
        time.sleep(random_delay)

        headers = dict(HEADERS, Cookie=cookie.strip())
        url = "https://www.nodeseek.com/api/attendance?random=true"
        response = requests.post(url, headers=headers, impersonate="chrome136")

        info(f"Account {idx} status code: {response.status_code}")
        info(f"Account {idx} response: {response.text}")

        if response.status_code != 200:
            raise RuntimeError(
                f"NODESEEK account {idx} check-in failed "
                f"(status={response.status_code}): {response.text}"
            )

        info(f"NODESEEK account {idx} check-in successful")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        tb = traceback.format_exc()
        print(tb, file=sys.stderr, flush=True)
        send_error_mail(f"[CloudCheckin] {PLATFORM} failed", tb)
        sys.exit(1)
