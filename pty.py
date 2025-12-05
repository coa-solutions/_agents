"""
Claude PTY execution.

Single responsibility: run Claude in a pseudo-terminal.
Handles signal forwarding, window resize, and raw mode.
"""

import fcntl
import os
import pty
import select
import signal
import subprocess
import sys
import termios
import tty
from pathlib import Path

CLAUDE_BIN = Path.home() / '.claude/local/node_modules/.bin/claude'


def run_claude(args: list[str]) -> int:
    """Run Claude in a PTY. Returns exit code."""
    master_fd, slave_fd = pty.openpty()

    if sys.stdin.isatty():
        old_settings = termios.tcgetattr(sys.stdin)
        termios.tcsetattr(slave_fd, termios.TCSANOW, old_settings)
        try:
            winsize = fcntl.ioctl(sys.stdin, termios.TIOCGWINSZ, b'\x00' * 8)
            fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)
        except OSError:
            pass

    proc = subprocess.Popen(
        args,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
        start_new_session=True,
    )
    os.close(slave_fd)

    def handle_sigwinch(signum, frame):
        if sys.stdin.isatty():
            try:
                winsize = fcntl.ioctl(sys.stdin, termios.TIOCGWINSZ, b'\x00' * 8)
                fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
                os.kill(proc.pid, signal.SIGWINCH)
            except (OSError, ProcessLookupError):
                pass

    def handle_term(signum, frame):
        proc.terminate()
        proc.wait()
        if sys.stdin.isatty():
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        sys.exit(0)

    signal.signal(signal.SIGWINCH, handle_sigwinch)
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # Let Ctrl+C go to Claude
    signal.signal(signal.SIGTERM, handle_term)
    signal.signal(signal.SIGHUP, handle_term)

    if sys.stdin.isatty():
        tty.setraw(sys.stdin.fileno())

    try:
        while True:
            if proc.poll() is not None:
                # Drain remaining output
                try:
                    while True:
                        data = os.read(master_fd, 4096)
                        if not data:
                            break
                        sys.stdout.buffer.write(data)
                        sys.stdout.buffer.flush()
                except OSError:
                    pass
                break

            rlist = [master_fd]
            if sys.stdin.isatty():
                rlist.append(sys.stdin.fileno())

            ready, _, _ = select.select(rlist, [], [], 0.1)

            for fd in ready:
                try:
                    data = os.read(fd, 4096)
                    if not data:
                        continue
                    if fd == master_fd:
                        sys.stdout.buffer.write(data)
                        sys.stdout.buffer.flush()
                    else:
                        os.write(master_fd, data)
                except OSError:
                    break
    except Exception:
        pass
    finally:
        os.close(master_fd)
        if sys.stdin.isatty():
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    return proc.returncode


def build_args(system_prompt_file: Path, user_args: list[str]) -> list[str]:
    """Build Claude command line arguments."""
    return [str(CLAUDE_BIN), '--append-system-prompt', str(system_prompt_file)] + user_args
