"""Session query utilities."""
import json
import os
from datetime import datetime
from pathlib import Path

SESSIONS_DIR = Path.home() / '.agents' / 'sessions'


def get_current_session() -> str | None:
    """Get current session ID from environment."""
    return os.environ.get('AGENT_SESSION_ID')


def get_session_dir(session_id: str) -> Path:
    """Get path to session directory."""
    return SESSIONS_DIR / session_id


def get_session_meta(session_id: str) -> dict | None:
    """Get session metadata."""
    meta_file = get_session_dir(session_id) / 'meta.json'
    if not meta_file.exists():
        return None
    try:
        return json.loads(meta_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def get_all_sessions() -> list[dict]:
    """Get all sessions."""
    if not SESSIONS_DIR.exists():
        return []

    sessions = []
    for session_dir in SESSIONS_DIR.iterdir():
        if not session_dir.is_dir():
            continue

        meta = get_session_meta(session_dir.name)
        if meta:
            sessions.append({
                'session_id': session_dir.name,
                **meta,
            })

    return sorted(sessions, key=lambda s: s.get('started', ''), reverse=True)


def get_active_sessions() -> list[dict]:
    """Get all active sessions (alias for get_all_sessions)."""
    return get_all_sessions()


def cleanup_stale() -> int:
    """Remove stale sessions (no running process)."""
    if not SESSIONS_DIR.exists():
        return 0

    removed = 0
    for session_dir in SESSIONS_DIR.iterdir():
        if not session_dir.is_dir():
            continue

        meta = get_session_meta(session_dir.name)
        if not meta:
            continue

        pid = meta.get('pid')
        if pid:
            # Check if process is still running
            try:
                os.kill(pid, 0)  # Signal 0 = check if process exists
            except (OSError, ProcessLookupError):
                # Process not running, remove session
                import shutil
                shutil.rmtree(session_dir, ignore_errors=True)
                removed += 1

    return removed


def time_ago(iso_timestamp: str) -> str:
    """Convert ISO timestamp to human-readable 'X ago' format."""
    try:
        started = datetime.fromisoformat(iso_timestamp)
        delta = datetime.now() - started

        minutes = int(delta.total_seconds() / 60)
        if minutes < 1:
            return 'just now'
        elif minutes < 60:
            return f'{minutes}m ago'
        else:
            hours = minutes // 60
            return f'{hours}h ago'
    except (ValueError, TypeError):
        return 'unknown'
