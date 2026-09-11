import re
import requests
from bs4 import BeautifulSoup


TGJU_URL = "https://www.tgju.org/profile/geram18"


def get_gold_18k():
    response = requests.get(
        TGJU_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "Chrome/131.0 Safari/537.36"
            )
        },
        timeout=15,
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Find the current price near "نرخ فعلی"
    text = soup.get_text(" ", strip=True)

    match = re.search(
        r"نرخ فعلی\s*[:：]?\s*([\d,]+)",
        text
    )

    if not match:
        raise RuntimeError(
            "Could not find 18K gold price on TGJU."
        )

    price = int(match.group(1).replace(",", ""))

    return {
        "symbol": "gold_18k",
        "price": price,
        "currency": "IRR",
        "source": "tgju",
    }
