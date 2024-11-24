from typing import Optional


def link(url: str, caption: Optional[str] = None) -> str:
    return f"<a href='{url}'>{caption if caption is not None else url}</a>"