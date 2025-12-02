"""File tracking - track which files each session touches."""
import subprocess
from pathlib import Path

from .session import get_session_dir, get_all_sessions, get_current_session


def track(filepath: str, session_id: str | None = None) -> None:
    """Track a file as touched by a session.

    Args:
        filepath: Path to file to track
        session_id: Session ID (defaults to current session from env)
    """
    if session_id is None:
        session_id = get_current_session()
    if not session_id:
        return

    files_path = get_session_dir(session_id) / 'files.txt'
    if not files_path.parent.exists():
        return

    filepath = str(Path(filepath).resolve())

    existing = get_session_files(session_id)
    if filepath not in existing:
        with files_path.open('a') as f:
            f.write(filepath + '\n')


def get_session_files(session_id: str) -> set[str]:
    """Get all files tracked by a session."""
    files_path = get_session_dir(session_id) / 'files.txt'
    if not files_path.exists():
        return set()

    files = set()
    for line in files_path.read_text().strip().split('\n'):
        if line:
            files.add(line)
    return files


def is_file_claimed(filepath: str, session_id: str | None = None) -> tuple[bool, str | None]:
    """
    Check if file is claimed by another session.

    Args:
        filepath: Path to check
        session_id: Current session ID (defaults to current session from env)

    Returns:
        (is_claimed, claiming_session_id) - None if not claimed
    """
    if session_id is None:
        session_id = get_current_session()

    filepath = str(Path(filepath).resolve())

    for session in get_all_sessions():
        sid = session['session_id']
        if sid == session_id:
            continue
        if filepath in get_session_files(sid):
            return True, sid

    return False, None


def get_my_files(session_id: str | None = None) -> set[str]:
    """Get files touched by current session.

    Args:
        session_id: Session ID (defaults to current session from env)

    Returns:
        Set of file paths touched by this session
    """
    if session_id is None:
        session_id = get_current_session()
    if not session_id:
        return set()

    return get_session_files(session_id)


def get_uncommitted_intersection(session_id: str | None = None) -> set[str]:
    """Get files touched by session that have uncommitted git changes.

    Args:
        session_id: Session ID (defaults to current session from env)

    Returns:
        Set of file paths with uncommitted changes
    """
    my_files = get_my_files(session_id)
    if not my_files:
        return set()

    # Get list of uncommitted files from git
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return set()

        uncommitted = set()
        for line in result.stdout.strip().split('\n'):
            if line and len(line) > 3:
                # Format: "XY filename" or "XY filename -> newname"
                filepath = line[3:].split(' -> ')[0].strip()
                uncommitted.add(str(Path(filepath).resolve()))

        return my_files & uncommitted
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return set()
