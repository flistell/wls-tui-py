import argparse
import logging
from textwrap import indent
import requests
import sys
import json
import os
from dotenv import load_dotenv
from urllib.parse import urljoin
from rich.pretty import pprint

BASE_REST = 'management/weblogic/latest/'

SESSION = None

pages = dict()

def navigate(base_url, uri=None):
    url = urljoin(base_url, BASE_REST, uri)
    response = SESSION.get(url)
    response.raise_for_status()
    logging.debug("Connection successful")
    data = response.json()
    pprint(data)
    pages['uri'] = data
    if 'links' in data:
        for link in data['links']:
            print(link['rel'])
            logging.debug(f"Found link: {link}")



def main():
    load_dotenv()  # Load .env file if present

    parser = argparse.ArgumentParser(description="Fetch JSON from a URL with authentication (accepts insecure HTTPS).")
    parser.add_argument("url", help="URL to connect to (HTTP or HTTPS)")
    parser.add_argument("--username", help="Username for authentication")
    parser.add_argument("--password", help="Password for authentication")
    parser.add_argument("--log", default="INFO", help="Logging level (default: INFO)")
    args = parser.parse_args()

    logging.basicConfig(level=args.log.upper(), format="%(levelname)s: %(message)s")

    username = args.username or os.getenv("WLS_USERNAME")
    password = args.password or os.getenv("WLS_PASSWORD")

    auth = (username, password) if username and password else None


    try:
        logging.debug(f"Connecting to {args.url}")
        global SESSION
        SESSION = requests.Session()
        SESSION.auth = auth
        SESSION.verify = False
        SESSION.proxies = {}
        navigate(args.url, '')
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {e}")
        sys.exit(1)
    except ValueError as e:
        logging.error(f"Failed to parse JSON: {e}")
        sys.exit(2)

if __name__ == "__main__":
    main()
