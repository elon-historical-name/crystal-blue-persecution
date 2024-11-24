from typing import Optional


class BlueSkyCredentials:
    def __init__(self, user_name: Optional[str], password: Optional[str]):
        self.user_name = user_name
        self.password = password
