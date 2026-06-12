import json
import os
import random
import sys
import time
import traceback

from curl_cffi import requests
from dotenv import load_dotenv
from twocaptcha import NetworkException, TimeoutException, TwoCaptcha

from notify.email import info, send_error_mail

from .questions import questions

load_dotenv()

PLATFORM = "1POINT3ACRES"


def _parse_cookie_string(cookie: str) -> dict[str, str]:
    """Parse a raw 'k1=v1; k2=v2' cookie header into a name->value dict."""
    jar: dict[str, str] = {}
    for item in cookie.split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue
        name, value = item.split("=", 1)
        jar[name.strip()] = value.strip()
    return jar


class OnePointThreeAcres:
    def __init__(self, cookie: str, solver: TwoCaptcha):
        # Keep UA aligned with the impersonate profile so 2Captcha-bound
        # token and the actual outgoing fingerprint match.
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        )
        self.cf_capcha_site_key = "0x4AAAAAAAA6iSaNNPWafmlz"
        self.checkin_page = "https://www.1point3acres.com/next/daily-checkin"
        self.post_checkin_url = "https://api.1point3acres.com/api/users/checkin"
        self.question_page = "https://www.1point3acres.com/next/daily-question"
        self.post_answer_url = "https://api.1point3acres.com/api/daily_questions"
        self.impersonate = "chrome136"
        self.solver = solver
        self.session = requests.Session(impersonate=self.impersonate)
        for name, value in _parse_cookie_string(cookie).items():
            self.session.cookies.set(name, value, domain=".1point3acres.com")
        self.header = {
            "User-Agent": self.user_agent,
            "Content-Type": "application/json",
            "Referer": "https://www.1point3acres.com/",
        }

    def daily_checkin(self) -> None:
        last_error = ""
        for attempt in range(1, 4):
            result = self._solve_turnstile(self.checkin_page)
            code = result["code"]
            captcha_id = result.get("captchaId")
            emoji_list = ["kx", "ng", "ym", "wl", "nu", "ch", "fd", "yl", "shuai"]
            body = {
                "qdxq": random.choice(emoji_list),
                "todaysay": "没有太多想说的",
                "captcha_response": code,
                "hashkey": "",
                "version": 2,
            }
            response = self.session.post(
                self.post_checkin_url,
                headers=self.header,
                data=json.dumps(body),
            )

            if response.status_code == 200:
                if captcha_id:
                    self.solver.report(captcha_id, True)
                resp_json = response.json()
                info(f"Checkin: {resp_json.get('msg', resp_json)}")
                return

            last_error = (
                f"1point3acres checkin failed (status={response.status_code}): {response.text}"
            )
            if "人机验证出错，请重试" in response.text:
                if captcha_id:
                    self.solver.report(captcha_id, False)
                info(f"Checkin captcha rejected, retry {attempt}/3")
                time.sleep(random.uniform(2, 8))
                continue

            raise RuntimeError(last_error)

        raise RuntimeError(last_error or "1point3acres checkin failed after retries")

    def get_daily_task_answer(self) -> tuple[int, int]:
        info("Fetching daily question from 1point3acres")
        response = self.session.get(self.post_answer_url, headers=self.header)
        resp_json = response.json()
        if resp_json.get("errno") != 0 or resp_json.get("msg") != "OK":
            raise RuntimeError(f"Failed to fetch daily question: {response.text}")

        question_id = resp_json["question"]["id"]
        question = resp_json["question"]["qc"].strip()
        info(f"Question: {question}")

        answers = {
            1: resp_json["question"]["a1"],
            2: resp_json["question"]["a2"],
            3: resp_json["question"]["a3"],
            4: resp_json["question"]["a4"],
        }
        info(f"Options: {answers}")

        if question not in questions:
            raise RuntimeError(
                f"Question not found in local dictionary: {question}. "
                "Please submit a PR to update questions.py."
            )

        expected = questions[question]
        answer_id = 0
        for k, v in answers.items():
            match = v in expected if isinstance(expected, list) else expected in v
            if match:
                answer_id = k
                break

        if answer_id == 0:
            raise RuntimeError(
                f"Answer not found among options for question: {question}. "
                f"Expected snippet: {expected}"
            )

        return question_id, answer_id

    def _solve_turnstile(self, page_url: str, attempts: int = 3):
        # Turnstile can be slow on 2Captcha; bump timeout and retry on transient failures.
        last_err: Exception | None = None
        for i in range(1, attempts + 1):
            try:
                return self.solver.turnstile(
                    sitekey=self.cf_capcha_site_key,
                    url=page_url,
                    useragent=self.user_agent,
                    timeout=300,
                    pollingInterval=5,
                )
            except (TimeoutException, NetworkException) as e:
                last_err = e
                info(f"Turnstile solve attempt {i}/{attempts} failed: {e}")
                time.sleep(random.uniform(3, 10))
        raise RuntimeError(
            f"2Captcha Turnstile solve failed after {attempts} attempts: "
            f"{type(last_err).__name__}: {last_err}"
        )

    def answer_daily_question(self, question: int, answer: int) -> None:
        last_error = ""
        for attempt in range(1, 4):
            result = self._solve_turnstile(self.question_page)
            code = result["code"]
            captcha_id = result.get("captchaId")

            body = {
                "qid": question,
                "answer": answer,
                "captcha_response": code,
                "hashkey": "",
                "version": 2,
            }
            response = self.session.post(
                self.post_answer_url,
                headers=self.header,
                data=json.dumps(body),
            )

            if "人机验证出错，请重试" in response.text:
                if captcha_id:
                    self.solver.report(captcha_id, False)
                last_error = f"1point3acres captcha rejected: {response.text}"
                info(f"Answer captcha rejected, retry {attempt}/3")
                time.sleep(random.uniform(3, 10))
                continue

            if captcha_id:
                self.solver.report(captcha_id, True)

            result_json = response.json()
            msg = result_json.get("msg", "")
            info(f"Answer: {msg}")

            if result_json.get("errno") == 0:
                return
            if msg == "您今天已经答过题了":
                info("Already answered today.")
                return
            raise RuntimeError(f"1point3acres answer failed: {response.text}")

        raise RuntimeError(last_error or "1point3acres answer failed after retries")


def main() -> None:
    cookie = os.environ.get("ONEPOINT3ACRES_COOKIE", "").strip()
    if not cookie:
        raise ValueError("Environment variable ONEPOINT3ACRES_COOKIE is not set")

    api_key = os.environ.get("TWOCAPTCHA_APIKEY", "").strip()
    if not api_key:
        raise ValueError("Environment variable TWOCAPTCHA_APIKEY is not set")

    solver = TwoCaptcha(api_key)
    acres = OnePointThreeAcres(cookie, solver)

    acres.daily_checkin()

    question_id, answer_id = acres.get_daily_task_answer()
    time.sleep(random.uniform(1, 50))
    acres.answer_daily_question(question_id, answer_id)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        tb = traceback.format_exc()
        print(tb, file=sys.stderr, flush=True)
        send_error_mail(f"[CloudCheckin] {PLATFORM} failed", tb)
        sys.exit(1)
