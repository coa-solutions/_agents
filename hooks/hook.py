#!/usr/bin/env python3
"""PostToolUse hook for Edit/Write - track files and warn on collisions."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home()))
from _agents.files import track, is_file_claimed
from _agents.session import get_active_sessions


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_input = data.get('tool_input', {})
    file_path = tool_input.get('file_path')

    if not file_path:
        sys.exit(0)

    # Track file in current session
    track(file_path)

    # Warn if file is claimed by another session
    claimed, other_session = is_file_claimed(file_path)
    if claimed:
        sessions = get_active_sessions()
        msg = f'File claimed by another session: {file_path}\n'
        msg += f'Session: {other_session}. Run `agents list` to see details.'
        print(msg)

    sys.exit(0)


if __name__ == '__main__':
    main()
