from typing import Optional, TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    from .auth import UserSession


def get_session_user() -> Optional["UserSession"]:
    return st.session_state.get("_user_session")


def require_login() -> "UserSession":
    user = get_session_user()
    if user is None:
        st.stop()
    return user
