import argparse
import sys

from core.integrations.hue_auth import provision_app_key


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pair JARVIS with a Philips Hue Bridge and print a Hue app key."
    )
    parser.add_argument(
        "--bridge-ip",
        required=True,
        help="Hue Bridge IP or hostname on your local network.",
    )
    parser.add_argument(
        "--device-type",
        default="jarvis#core",
        help="Hue devicetype label used when requesting a key (default: jarvis#core).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=45,
        help="How long to keep retrying while waiting for bridge button press.",
    )
    args = parser.parse_args()

    print("Philips Hue pairing")
    print(f"- Bridge IP: {args.bridge_ip}")
    print("- Press the physical button on the Hue Bridge now.")
    print("- Waiting for bridge authorization...")

    result = provision_app_key(
        bridge_ip=args.bridge_ip,
        device_type=args.device_type,
        timeout_seconds=args.timeout_seconds,
    )
    if not result.ok or not result.app_key:
        print(f"Pairing failed: {result.message or result.error or 'unknown error'}")
        return 1

    print("")
    print("Pairing successful.")
    print(f"HUE_APP_KEY=\"{result.app_key}\"")
    print("")
    print("Set these environment variables before starting Core:")
    print(f"HUE_BRIDGE_IP=\"{args.bridge_ip}\"")
    print(f"HUE_APP_KEY=\"{result.app_key}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
