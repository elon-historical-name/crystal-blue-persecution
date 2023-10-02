import json
import os
from typing import Dict

import aiofiles


def get_accounts() -> Dict[str, str]:
    accounts_database = os.environ.get("ACCOUNTS_JSON")
    with open(accounts_database, mode='r') as file:
        data = json.loads(file.read())
        return data
