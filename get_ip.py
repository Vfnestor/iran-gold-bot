import requests


def get_public_ip():
    try:
        response = requests.get(
            "https://api.ipify.org",
            timeout=10
        )

        response.raise_for_status()

        ip = response.text.strip()

        print(f"🌐 RENDER OUTBOUND IP: {ip}")

    except requests.RequestException as e:
        print(f"❌ Failed to detect public IP: {e}")


if __name__ == "__main__":
    get_public_ip()
