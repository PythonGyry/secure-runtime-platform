from __future__ import annotations

import uuid


def get_hwid() -> str:
    return str(uuid.getnode())
