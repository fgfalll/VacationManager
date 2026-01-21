"""
Unified entry point for VacationManager.
Can start backend API server, web UI, and desktop app independently or together.

Features:
- Structured logging with colors and timestamps
- Health checks to verify services are running
- Port auto-detection if default port is in use
- Graceful shutdown with timeout handling
"""

import argparse
import asyncio
import os
import socket
import subprocess
import sys
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


# ANSI color codes for terminal output
class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Background colors
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"

    @classmethod
    def strip(cls, text: str) -> str:
        """Remove ANSI color codes from text."""
        import re
        ansi_escape = re.compile(r'\033\[[0-9;]*m')
        return ansi_escape.sub('', text)


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.absolute()


def log(level: str, message: str, color: str = Colors.WHITE) -> None:
    """
    Log a message with timestamp, level, and color.

    Args:
        level: Log level (INFO, WARNING, ERROR, SUCCESS)
        message: Message to log
        color: ANSI color code for the message
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    level_colored = {
        "INFO": f"{Colors.BLUE}{level}{Colors.RESET}",
        "WARN": f"{Colors.YELLOW}{level}{Colors.RESET}",
        "ERROR": f"{Colors.RED}{level}{Colors.RESET}",
        "SUCCESS": f"{Colors.GREEN}{level}{Colors.RESET}",
    }.get(level.upper(), level)

    print(f"{Colors.DIM}[{timestamp}]{Colors.RESET} {level_colored}: {color}{message}{Colors.RESET}")


def log_info(message: str) -> None:
    """Log an info message."""
    log("INFO", message, Colors.WHITE)


def log_warn(message: str) -> None:
    """Log a warning message."""
    log("WARN", message, Colors.YELLOW)


def log_error(message: str) -> None:
    """Log an error message."""
    log("ERROR", message, Colors.RED)


def log_success(message: str) -> None:
    """Log a success message."""
    log("SUCCESS", message, Colors.GREEN)


def is_port_available(host: str, port: int) -> bool:
    """
    Check if a port is available.

    Args:
        host: Host address to check
        port: Port number to check

    Returns:
        True if port is available, False otherwise
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def find_available_port(host: str, start_port: int, max_attempts: int = 100) -> int:
    """
    Find an available port starting from start_port.

    Args:
        host: Host address
        start_port: Starting port number
        max_attempts: Maximum number of ports to try

    Returns:
        Available port number
    """
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(host, port):
            return port
    raise RuntimeError(f"No available port found in range {start_port}-{start_port + max_attempts}")


def find_npm() -> str:
    """
    Find npm executable, checking common Windows locations.

    Returns:
        Path to npm executable or "npm" as fallback
    """
    # Try npm in PATH
    npm = shutil.which("npm")
    if npm:
        log_info(f"Found npm in PATH: {npm}")
        return npm

    # Windows-specific npm locations
    npm_paths = [
        os.path.expandvars(r"%ProgramFiles%\nodejs\npm.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\nodejs\npm.exe"),
        os.path.expandvars(r"%LocalAppData%\Programs\nodejs\npm.exe"),
    ]

    for path in npm_paths:
        if os.path.exists(path):
            log_info(f"Found npm at: {path}")
            return path

    # Also try .cmd version on Windows
    npm_cmd_paths = [
        os.path.expandvars(r"%ProgramFiles%\nodejs\npm.cmd"),
        os.path.expandvars(r"%ProgramFiles(x86)%\nodejs\npm.cmd"),
    ]

    for path in npm_cmd_paths:
        if os.path.exists(path):
            log_info(f"Found npm.cmd at: {path}")
            return path

    log_warn("npm not found in standard locations, using 'npm' as fallback")
    return "npm"  # Fallback - will fail with better error


async def check_service_health(url: str, timeout: int = 10) -> bool:
    """
    Check if a service is healthy by making HTTP request.

    Args:
        url: Health check URL
        timeout: Timeout in seconds

    Returns:
        True if service is healthy, False otherwise
    """
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=timeout) as response:
                return response.status < 500
    except Exception:
        return False


async def check_backend_health(host: str, port: int, timeout: int = 10) -> bool:
    """
    Check if backend API is healthy.

    Args:
        host: Backend host
        port: Backend port
        timeout: Timeout in seconds

    Returns:
        True if backend is healthy, False otherwise
    """
    return await check_service_health(f"http://{host}:{port}/health", timeout)


async def check_web_health(host: str = "localhost", port: int = 5173, timeout: int = 10) -> bool:
    """
    Check if web UI is healthy.

    Args:
        host: Web UI host
        port: Web UI port
        timeout: Timeout in seconds

    Returns:
        True if web UI is healthy, False otherwise
    """
    return await check_service_health(f"http://{host}:{port}", timeout)


def start_backend(port: int = 8000, host: str = "127.0.0.1", reload: bool = True) -> subprocess.Popen:
    """
    Start the FastAPI backend server.

    Args:
        port: Port to run on
        host: Host to bind to
        reload: Enable auto-reload

    Returns:
        Subprocess object
    """
    cmd = [
        sys.executable, "-m", "uvicorn",
        "backend.main:app",
        "--host", host,
        "--port", str(port),
    ]
    if reload:
        cmd.append("--reload")

    log_info(f"Starting backend on http://{host}:{port}")
    return subprocess.Popen(cmd, cwd=get_project_root())


def start_web(dev: bool = True, port: int = 5173) -> subprocess.Popen:
    """
    Start the React web UI.

    Args:
        dev: Run in development mode with hot-reload
        port: Port to run on

    Returns:
        Subprocess object
    """
    env = os.environ.copy()
    env["VITE_API_URL"] = "http://127.0.0.1:8000"

    npm_path = find_npm()

    if dev:
        cmd = [npm_path, "run", "dev", "--", "--host", "0.0.0.0", "--port", str(port)]
        log_info(f"Starting web UI in development mode on http://localhost:{port}")
    else:
        cmd = [npm_path, "run", "build"]
        log_info("Building web UI...")

    return subprocess.Popen(cmd, cwd=get_project_root() / "web", env=env)


def start_desktop() -> subprocess.Popen:
    """
    Start the desktop application.

    Returns:
        Subprocess object
    """
    cmd = [sys.executable, "-m", "desktop"]
    log_info("Starting desktop application...")
    return subprocess.Popen(cmd, cwd=get_project_root())


def print_banner():
    """Print application banner."""
    banner = f"""
{Colors.CYAN}╔════════════════════════════════════════════════════════════╗
║                                                            ║
║  {Colors.BOLD}VacationManager v7.7.4{Colors.RESET}{Colors.CYAN}                                   ║
║  Система управління відпустками та табелем                   ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
    print(banner)


def print_status(host: str, backend_port: int, web_port: int):
    """
    Print running services status.

    Args:
        host: Backend host
        backend_port: Backend port
        web_port: Web UI port
    """
    print(f"\n{Colors.BOLD}{'═' * 58}{Colors.RESET}")
    print(f"{Colors.GREEN}{Colors.BOLD}  VacationManager is running!{Colors.RESET}")
    print(f"{Colors.BOLD}{'═' * 58}{Colors.RESET}")
    print(f"  {Colors.CYAN}API:{Colors.RESET}      http://{host}:{backend_port}")
    print(f"  {Colors.CYAN}Web UI:{Colors.RESET}   http://localhost:{web_port}")
    print(f"  {Colors.CYAN}Docs:{Colors.RESET}     http://{host}:{backend_port}/docs")
    print(f"{Colors.BOLD}{'═' * 58}{Colors.RESET}")
    print(f"\n{Colors.DIM}Press Ctrl+C to stop all services...{Colors.RESET}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="VacationManager - Start backend, web UI, or desktop app",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py --backend              # Start only backend API
  python run.py --web                  # Start only web UI
  python run.py --desktop              # Start only desktop app
  python run.py --all                  # Start all three
  python run.py --all --no-reload      # Start without hot-reload
  python run.py --backend --port 9000  # Start backend on custom port
        """
    )

    parser.add_argument("--backend", action="store_true", help="Start backend API server")
    parser.add_argument("--web", action="store_true", help="Start web UI (React)")
    parser.add_argument("--desktop", action="store_true", help="Start desktop application")
    parser.add_argument("--all", action="store_true", help="Start all components")
    parser.add_argument("--port", type=int, default=8000, help="Backend port (default: 8000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Backend host (default: 127.0.0.1)")
    parser.add_argument("--web-port", type=int, default=5173, help="Web UI port (default: 5173)")
    parser.add_argument("--no-reload", action="store_true", help="Disable hot-reload for backend")
    parser.add_argument("--health-check", action="store_true", help="Wait for health checks before completing")
    parser.add_argument("--health-timeout", type=int, default=30, help="Health check timeout in seconds")

    args = parser.parse_args()

    # If no specific option is given, show banner and help
    if not any([args.backend, args.web, args.desktop, args.all]):
        print_banner()
        parser.print_help()
        return

    print_banner()

    processes = []
    backend_port = args.port
    web_port = args.web_port

    # Check port availability
    if args.backend or args.all:
        if not is_port_available(args.host, backend_port):
            log_warn(f"Port {backend_port} is already in use, finding available port...")
            backend_port = find_available_port(args.host, backend_port)
            log_info(f"Using port {backend_port} for backend")

    if args.web or args.all:
        if not is_port_available("localhost", web_port):
            log_warn(f"Port {web_port} is already in use, finding available port...")
            web_port = find_available_port("localhost", web_port)
            log_info(f"Using port {web_port} for web UI")

    try:
        if args.all or args.backend:
            processes.append(start_backend(port=backend_port, host=args.host, reload=not args.no_reload))

        if args.all or args.web:
            processes.append(start_web(dev=True, port=web_port))

        if args.all or args.desktop:
            processes.append(start_desktop())

        # Health checks if requested
        if args.health_check:
            log_info("Waiting for services to be healthy...")
            start_time = time.time()

            async def run_health_checks():
                healthy = False
                while time.time() - start_time < args.health_timeout:
                    if args.backend or args.all:
                        if await check_backend_health(args.host, backend_port):
                            log_success(f"Backend is healthy at http://{args.host}:{backend_port}")
                            healthy = True
                            break
                    await asyncio.sleep(0.5)
                return healthy

            if args.backend or args.all:
                try:
                    if not asyncio.run(run_health_checks()):
                        log_warn(f"Backend health check timeout after {args.health_timeout}s")
                except Exception as e:
                    log_warn(f"Health check failed: {e}")

        # Print status
        if args.backend or args.all:
            print_status(args.host, backend_port, web_port)
        elif args.web:
            log_success(f"Web UI running at http://localhost:{web_port}")
        elif args.desktop:
            log_success("Desktop application running")

        # Wait for all processes
        for proc in processes:
            proc.wait()

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Shutting down...{Colors.RESET}")
        for proc in processes:
            proc.terminate()

        # Wait for graceful shutdown with timeout
        shutdown_start = time.time()
        for proc in processes:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                log_warn(f"Process {proc.pid} did not terminate gracefully, forcing...")
                proc.kill()

        elapsed = time.time() - shutdown_start
        log_success(f"Shutdown complete in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
