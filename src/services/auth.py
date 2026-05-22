import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import streamlit as st

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "users.json"


@dataclass
class UserSession:
    user_id: int
    username: str
    display_name: str
    is_admin: bool


class AuthService:
    def __init__(self, config_path: Path | None = None):
        self._users = self._load_users(config_path or _CONFIG_PATH)

    def _load_users(self, config_path: Path) -> dict:
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                return json.load(f).get("users", {})
        # Fallback: single admin user (dev mode, no config file yet)
        return {
            "matteo": {
                "password": "password1",
                "display_name": "Matteo",
                "user_id": 1,
                "is_admin": True,
            }
        }

    def authenticate(self, username: str, password: str) -> Optional[UserSession]:
        cfg = self._users.get(username.lower())
        if not cfg or cfg.get("password") != password:
            return None
        return UserSession(
            user_id=cfg["user_id"],
            username=username.lower(),
            display_name=cfg["display_name"],
            is_admin=cfg.get("is_admin", False),
        )

    def get_current_user(self) -> Optional[UserSession]:
        return st.session_state.get("_user_session")

    def set_current_user(self, session: Optional[UserSession]) -> None:
        st.session_state["_user_session"] = session
