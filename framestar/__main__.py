import argparse
import logging

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the framestar kiosk")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    uvicorn.run("framestar.app:app_from_env", factory=True, host=args.host, port=args.port, proxy_headers=True)


if __name__ == "__main__":
    main()
