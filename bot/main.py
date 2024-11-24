import argparse
import logging
import os
import sys

import dotenv

from distribution_main import distribute_posts
from subscription_management_main import manage_subscriptions

if __name__ == '__main__':
    dotenv.load_dotenv()
    log_format = '%(asctime)s %(levelname)-8s %(message)s' \
        if os.environ.get("IS_DOCKERIZED") != "1" \
        else '%(levelname)-8s %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stdout
    )

    if os.environ.get("IS_DOCKERIZED") == "1" and os.environ.get("SQL_ALCHEMY_URL") is not None:
        database_file_path = os.environ.get("SQL_ALCHEMY_URL").lstrip("sqlite+aiosqlite:///")
        with open(database_file_path, "x"):
            pass

    exec_mode = os.environ.get("EXEC_MODE")
    if exec_mode is None:
        parser = argparse.ArgumentParser()
        parser.add_argument('-m', choices=['manage_subscriptions', 'distribute_content'])
        args = parser.parse_args()
        if args.m == 'manage_subscriptions':
            manage_subscriptions()
        elif args.m == 'distribute_content':
            distribute_posts()
    elif exec_mode == 'manage_subscriptions':
        manage_subscriptions()
    elif exec_mode == 'distribute_content':
        distribute_posts()
