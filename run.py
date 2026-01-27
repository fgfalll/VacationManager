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


def start_backend(port: int = 8000, host: str = "127.0.0.1", reload: bool = True, env: dict = None) -> subprocess.Popen:
    """
    Start the FastAPI backend server.

    Args:
        port: Port to run on
        host: Host to bind to
        reload: Enable auto-reload
        env: Additional environment variables to pass

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

    # Merge environment variables
    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    log_info(f"Starting backend on http://{host}:{port}")
    return subprocess.Popen(cmd, cwd=get_project_root(), env=run_env)


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


def start_mini_app(dev: bool = True, port: int = 5174) -> subprocess.Popen:
    """
    Start the Telegram Mini App React UI.

    Args:
        dev: Run in development mode with hot-reload
        port: Port to run on (default 5174 to not conflict with web UI)

    Returns:
        Subprocess object
    """
    env = os.environ.copy()
    # The Mini App uses proxy to reach backend API
    env["VITE_API_URL"] = f"http://127.0.0.1:{os.getenv('VM_PORT', '8000')}"

    npm_path = find_npm()

    if dev:
        # For dev mode, use npx vite directly for better control
        cmd = [npm_path, "run", "dev"]
        log_info(f"Starting Telegram Mini App in development mode on http://localhost:{port}")
    else:
        cmd = [npm_path, "run", "build"]
        log_info("Building Telegram Mini App...")

    # Set working directory to telegram-mini-app
    mini_app_dir = get_project_root() / "telegram-mini-app"
    return subprocess.Popen(cmd, cwd=str(mini_app_dir), env=env)


def start_desktop() -> subprocess.Popen:
    """
    Start the desktop application.

    Returns:
        Subprocess object
    """
    cmd = [sys.executable, "-m", "desktop"]
    log_info("Starting desktop application...")
    return subprocess.Popen(cmd, cwd=get_project_root())


def _get_telegram_settings_from_db() -> tuple[bool, str, str, str]:
    """
    Read Telegram settings from database.

    Returns:
        Tuple of (enabled, bot_token, webhook_url, mini_app_url)
    """
    import sqlite3
    db_path = get_project_root() / "vacation_manager.db"

    if not db_path.exists():
        return False, "", "", ""

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'telegram_enabled'")
        result = cursor.fetchone()
        enabled = result[0].lower() in ('true', '1', 'yes') if result and result[0] else False

        cursor.execute("SELECT value FROM settings WHERE key = 'telegram_bot_token'")
        result = cursor.fetchone()
        bot_token = result[0] if result else ""

        cursor.execute("SELECT value FROM settings WHERE key = 'telegram_webhook_url'")
        result = cursor.fetchone()
        webhook_url = result[0] if result else ""

        cursor.execute("SELECT value FROM settings WHERE key = 'telegram_mini_app_url'")
        result = cursor.fetchone()
        mini_app_url = result[0] if result else ""

        conn.close()
        return enabled, bot_token, webhook_url, mini_app_url
    except Exception:
        return False, "", "", ""


def start_telegram_bot(test: bool = False) -> subprocess.Popen:
    """
    Start the Telegram bot in polling mode (for development/testing).

    Args:
        test: Run in test mode with verbose output

    Returns:
        Subprocess object
    """
    # Check database settings first, fall back to env vars
    db_enabled, db_token, db_webhook, db_mini_app = _get_telegram_settings_from_db()

    # Use database values if set, otherwise use environment/config
    telegram_enabled = db_enabled
    telegram_bot_token = db_token

    if not telegram_enabled:
        log_error("Telegram bot is not enabled. Enable it in desktop settings:")
        log_info("  Desktop app → Settings → Telegram → 'Увімкнути Telegram бота'")
        sys.exit(1)

    if not telegram_bot_token:
        log_error("Telegram bot token is not configured.")
        log_info("Please configure bot token in Desktop app → Settings → Telegram")
        sys.exit(1)

    log_info("Starting Telegram bot in polling mode...")

    # Delete any existing webhook before starting polling mode
    # This prevents "conflict: can't use getUpdates while webhook is active" errors
    try:
        import urllib.request
        import json
        delete_url = f"https://api.telegram.org/bot{telegram_bot_token}/deleteWebhook?drop_pending_updates=true"
        with urllib.request.urlopen(delete_url, timeout=10) as response:
            if response.status == 200:
                result = json.loads(response.read())
                if result.get("ok"):
                    log_info("Cleared any existing webhook")
    except Exception as e:
        log_warn(f"Could not clear webhook (may not exist): {e}")

    cmd = [
        sys.executable, "-m", "backend.telegram.run_bot",
    ]

    if test:
        cmd.extend(["--skip-updates", "--log-level", "DEBUG"])
        log_info("Running in test mode (skipping updates)")
    else:
        cmd.extend(["--log-level", "INFO"])

    # Set environment variables from database settings
    env = os.environ.copy()
    env["VM_TELEGRAM_ENABLED"] = "true" if telegram_enabled else "false"
    env["VM_TELEGRAM_BOT_TOKEN"] = telegram_bot_token
    if db_webhook:
        env["VM_TELEGRAM_WEBHOOK_URL"] = db_webhook
    if db_mini_app:
        env["VM_TELEGRAM_MINI_APP_URL"] = db_mini_app

    return subprocess.Popen(cmd, cwd=get_project_root(), env=env)


def start_telegram_with_ngrok(backend_port: int = 8000, mini_app_port: int = 5174, host: str = "127.0.0.1") -> list:
    """
    Start Telegram bot with ngrok tunnel for webhook mode.

    This starts the backend server, Mini App dev server, and ngrok tunnel.
    ngrok tunnels to the Mini App port, which proxies /api requests to the backend.

    Args:
        backend_port: Backend port (default: 8000)
        mini_app_port: Mini App port (default: 5174)
        host: Backend host (default: 127.0.0.1)

    Returns:
        List of subprocess objects
    """
    import json
    from pathlib import Path

    # Check database settings first
    db_enabled, db_token, db_webhook, db_mini_app = _get_telegram_settings_from_db()

    telegram_enabled = db_enabled
    telegram_bot_token = db_token

    if not telegram_enabled:
        log_error("Telegram bot is not enabled. Enable it in desktop settings:")
        log_info("  Desktop app → Settings → Telegram → 'Увімкнути Telegram бота'")
        sys.exit(1)

    if not telegram_bot_token:
        log_error("Telegram bot token is not configured.")
        log_info("Please configure bot token in Desktop app → Settings → Telegram")
        sys.exit(1)

    # Find ngrok executable
    ngrok_paths = [
        Path(get_project_root()) / "tools" / "ngrok.exe",
        Path(get_project_root()) / "tools" / "ngrok",
    ]
    ngrok_exe = None
    for path in ngrok_paths:
        if path.exists():
            ngrok_exe = str(path)
            break

    if not ngrok_exe:
        # Try system path
        ngrok_exe = "ngrok"

    log_info(f"Using ngrok: {ngrok_exe}")

    # Get ngrok config to find dev domain
    ngrok_config_path = Path.home() / ".config" / "ngrok" / "ngrok.yml"
    if not ngrok_config_path.exists():
        ngrok_config_path = Path.home() / "AppData" / "Local" / "ngrok" / "ngrok.yml"

    dev_domain = None
    if ngrok_config_path.exists():
        try:
            with open(ngrok_config_path) as f:
                for line in f:
                    if "domain:" in line and "ngrok-free.dev" in line:
                        dev_domain = line.split("domain:")[1].strip().strip('"').strip("'")
                        break
        except Exception:
            pass

    # If no domain in config, check environment variable or use known domain
    if not dev_domain:
        dev_domain = os.getenv("NGROK_DOMAIN", "unescheatable-barney-nonecstatically.ngrok-free.dev")

    if dev_domain:
        log_info(f"Using ngrok dev domain: {dev_domain}")
    else:
        log_warn("No ngrok dev domain found. Using random URL.")
        dev_domain = None

    # Start ngrok tunnel to Mini App port (which proxies /api to backend)
    if dev_domain:
        ngrok_cmd = [ngrok_exe, "http", str(mini_app_port), "--domain", dev_domain, "--log=stdout"]
    else:
        ngrok_cmd = [ngrok_exe, "http", str(mini_app_port), "--log=stdout"]

    log_info(f"Starting ngrok tunnel on port {mini_app_port} (Mini App)...")
    # Open a null file to discard ngrok output (prevents blocking on Windows)
    null_file = open(os.devnull, 'w')
    ngrok_process = subprocess.Popen(
        ngrok_cmd,
        stdout=null_file,
        stderr=null_file,
        text=True
    )

    # Wait for ngrok to start and get the URL
    import time
    log_info("Waiting for ngrok to start...")
    time.sleep(5)

    webhook_url = None
    if not dev_domain:
        # Try to get URL from ngrok API
        try:
            import urllib.request
            import json
            log_info("Fetching ngrok URL from API...")
            response = urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=5)
            if response.status == 200:
                data = json.loads(response.read())
                tunnels = data.get("tunnels", [])
                log_info(f"ngrok API returned {len(tunnels)} tunnel(s)")
                if tunnels:
                    webhook_url = tunnels[0].get("public_url")
                    log_info(f"Using ngrok URL: {webhook_url}")
                else:
                    log_warn("No tunnels found in ngrok API response")
            else:
                log_warn(f"ngrok API returned status {response.status}")
        except Exception as e:
            log_warn(f"Failed to get ngrok URL from API: {e}")
    else:
        webhook_url = f"https://{dev_domain}"

    if webhook_url:
        log_info(f"ngrok tunnel URL: {webhook_url}")
        webhook_url = f"{webhook_url}/api/telegram/webhook"
        log_info(f"Webhook URL: {webhook_url}")
    else:
        log_error("Could not get ngrok URL")
        ngrok_process.terminate()
        sys.exit(1)

    # Set webhook via Telegram API
    try:
        import urllib.request
        import json

        webhook_set_url = f"https://api.telegram.org/bot{telegram_bot_token}/setWebhook"
        data = json.dumps({"url": webhook_url}).encode("utf-8")
        req = urllib.request.Request(webhook_set_url, data=data, headers={"Content-Type": "application/json"})

        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                result = json.loads(response.read())
                if result.get("ok"):
                    log_success("Telegram webhook set successfully!")
                else:
                    log_error(f"Failed to set webhook: {result.get('description', 'Unknown error')}")
            else:
                log_error(f"Failed to set webhook: HTTP {response.status}")
    except Exception as e:
        log_error(f"Failed to set webhook: {e}")

    # Start backend server first with webhook mode enabled
    log_info(f"Starting backend server on port {backend_port}...")
    backend_process = start_backend(
        port=backend_port, 
        host=host, 
        reload=True, 
        env={"VM_TELEGRAM_WEBHOOK_MODE": "true"}
    )

    # Wait for backend to start
    import time
    time.sleep(2)

    # Start Mini App dev server
    log_info(f"Starting Mini App dev server on port {mini_app_port}...")
    mini_app_process = start_mini_app(dev=True, port=mini_app_port)

    # Wait for Mini App to start
    time.sleep(2)

    log_success("Telegram bot with ngrok started!")
    log_info(f"Backend: http://{host}:{backend_port}")
    log_info(f"Mini App: http://localhost:{mini_app_port}")
    log_info(f"Mini App (public): {webhook_url.replace('/api/telegram/webhook', '')}")
    log_info(f"Webhook: {webhook_url}")
    log_info("Press Ctrl+C to stop all services")

    return [ngrok_process, backend_process, mini_app_process]


def print_banner():
    """Print application banner."""
    banner = f"""
{Colors.CYAN}╔════════════════════════════════════════════════════════════╗
║                                                            ║
║  {Colors.BOLD}VacationManager v7.7.4{Colors.RESET}{Colors.CYAN}                                    ║
║  Система управління відпустками та табелем                 ║
║  + Telegram Mini App + Telegram Bot                       ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
    try:
        print(banner)
    except UnicodeEncodeError:
        # Fallback for Windows console encoding issues
        print("VacationManager v7.7.4 - Starting...")


def print_status(host: str, backend_port: int, web_port: int):
    """
    Print running services status.

    Args:
        host: Backend host
        backend_port: Backend port
        web_port: Web UI port
    """
    try:
        print(f"\n{Colors.BOLD}{'═' * 58}{Colors.RESET}")
        print(f"{Colors.GREEN}{Colors.BOLD}  VacationManager is running!{Colors.RESET}")
        print(f"{Colors.BOLD}{'═' * 58}{Colors.RESET}")
        print(f"  {Colors.CYAN}API:{Colors.RESET}      http://{host}:{backend_port}")
        print(f"  {Colors.CYAN}Web UI:{Colors.RESET}   http://localhost:{web_port}")
        print(f"  {Colors.CYAN}Docs:{Colors.RESET}     http://{host}:{backend_port}/docs")
        print(f"{Colors.BOLD}{'═' * 58}{Colors.RESET}")
        print(f"\n{Colors.DIM}Press Ctrl+C to stop all services...{Colors.RESET}\n")
    except UnicodeEncodeError:
        print(f"\nVacationManager is running!")
        print(f"API:      http://{host}:{backend_port}")
        print(f"Web UI:   http://localhost:{web_port}")
        print(f"Docs:     http://{host}:{backend_port}/docs")
        print(f"\nPress Ctrl+C to stop all services...\n")


def print_status_full(host: str, backend_port: int, web_port: int, mini_app_port: int = 0):
    """
    Print running services status including mini app.

    Args:
        host: Backend host
        backend_port: Backend port
        web_port: Web UI port
        mini_app_port: Telegram Mini App port (0 if not running)
    """
    try:
        print(f"\n{Colors.BOLD}{'═' * 58}{Colors.RESET}")
        print(f"{Colors.GREEN}{Colors.BOLD}  VacationManager is running!{Colors.RESET}")
        print(f"{Colors.BOLD}{'═' * 58}{Colors.RESET}")
        print(f"  {Colors.CYAN}API:{Colors.RESET}        http://{host}:{backend_port}")
        print(f"  {Colors.CYAN}Web UI:{Colors.RESET}     http://localhost:{web_port}")
        if mini_app_port:
            print(f"  {Colors.CYAN}Mini App:{Colors.RESET}   http://localhost:{mini_app_port}")
        print(f"  {Colors.CYAN}Docs:{Colors.RESET}       http://{host}:{backend_port}/docs")
        print(f"{Colors.BOLD}{'═' * 58}{Colors.RESET}")
        print(f"\n{Colors.DIM}Press Ctrl+C to stop all services...{Colors.RESET}\n")
    except UnicodeEncodeError:
        print(f"\nVacationManager is running!")
        print(f"API:        http://{host}:{backend_port}")
        print(f"Web UI:     http://localhost:{web_port}")
        if mini_app_port:
            print(f"Mini App:   http://localhost:{mini_app_port}")
        print(f"Docs:       http://{host}:{backend_port}/docs")
        print(f"\nPress Ctrl+C to stop all services...\n")


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
  python run.py --tray                 # Start desktop with system tray (services in background)
  python run.py --telegram             # Start Telegram bot (polling mode)
  python run.py --telegram-webhook     # Start Telegram bot with ngrok (webhook mode)
  python run.py --mini-app             # Start Telegram Mini App dev server
  python run.py --all                  # Start all components
  python run.py --all --no-reload      # Start without hot-reload
  python run.py --backend --port 9000  # Start backend on custom port
  python run.py --telegram --telegram-test  # Start bot in test mode
        """
    )

    parser.add_argument("--backend", action="store_true", help="Start backend API server")
    parser.add_argument("--web", action="store_true", help="Start web UI (React)")
    parser.add_argument("--desktop", action="store_true", help="Start desktop application")
    parser.add_argument("--tray", action="store_true", help="Start desktop with system tray (services run in background)")
    parser.add_argument("--telegram", action="store_true", help="Start Telegram bot (polling mode for development)")
    parser.add_argument("--telegram-webhook", action="store_true", help="Start Telegram bot with ngrok tunnel (webhook mode)")
    parser.add_argument("--mini-app", action="store_true", help="Start Telegram Mini App dev server")
    parser.add_argument("--all", action="store_true", help="Start all components")
    parser.add_argument("--port", type=int, default=8000, help="Backend port (default: 8000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Backend host (default: 127.0.0.1)")
    parser.add_argument("--web-port", type=int, default=5173, help="Web UI port (default: 5173)")
    parser.add_argument("--mini-app-port", type=int, default=5174, help="Telegram Mini App port (default: 5174)")
    parser.add_argument("--no-reload", action="store_true", help="Disable hot-reload for backend")
    parser.add_argument("--health-check", action="store_true", help="Wait for health checks before completing")
    parser.add_argument("--health-timeout", type=int, default=30, help="Health check timeout in seconds")
    parser.add_argument("--telegram-test", action="store_true", help="Run Telegram bot in test mode (verbose, skip updates)")

    args = parser.parse_args()

    # If no specific option is given, show banner and help
    mini_app_flag = getattr(args, 'mini_app', False)  # Handle hyphenated arg name
    telegram_webhook_flag = getattr(args, 'telegram_webhook', False)
    if not any([args.backend, args.web, args.desktop, args.tray, args.telegram, telegram_webhook_flag, mini_app_flag, args.all]):
        print_banner()
        parser.print_help()
        return

    print_banner()

    processes = []
    backend_port = args.port
    web_port = args.web_port
    mini_app_port = getattr(args, 'mini_app_port', 5174)

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

    if mini_app_flag or args.all or telegram_webhook_flag:
        if not is_port_available("localhost", mini_app_port):
            log_warn(f"Port {mini_app_port} is already in use, finding available port...")
            mini_app_port = find_available_port("localhost", mini_app_port)
            log_info(f"Using port {mini_app_port} for Telegram Mini App")

    try:
        # Handle telegram-webhook mode separately (starts both ngrok, backend, and mini app)
        if telegram_webhook_flag:
            telegram_processes = start_telegram_with_ngrok(backend_port=backend_port, mini_app_port=mini_app_port, host=args.host)
            processes.extend(telegram_processes)
        elif args.all or args.backend:
            # Enable DEV_MODE for Mini App browser testing in non-webhook mode
            processes.append(start_backend(
                port=backend_port, 
                host=args.host, 
                reload=not args.no_reload,
                env={"DEV_MODE": "true"}
            ))

        if args.all or args.web:
            processes.append(start_web(dev=True, port=web_port))

        if args.all or args.desktop:
            processes.append(start_desktop())

        if args.tray:
            # Start desktop in tray mode (services run in background)
            # Enable Telegram if it's configured in database
            db_enabled, _, _, _ = _get_telegram_settings_from_db()
            cmd = [
                sys.executable, "-m", "desktop",
                "--enable-telegram" if db_enabled else "",
                "--backend-port", str(backend_port),
                "--web-port", str(web_port),
            ]
            # Filter out empty strings
            cmd = [c for c in cmd if c]
            processes.append(subprocess.Popen(cmd, cwd=get_project_root()))

        if args.all or args.telegram:
            processes.append(start_telegram_bot(test=args.telegram_test))

        if args.all or mini_app_flag:
            processes.append(start_mini_app(dev=True, port=mini_app_port))

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
        if args.all:
            print_status_full(args.host, backend_port, web_port, mini_app_port)
        elif telegram_webhook_flag:
            # Status already printed by start_telegram_with_ngrok
            pass
        elif args.backend:
            print_status(args.host, backend_port, web_port)
        elif args.web:
            log_success(f"Web UI running at http://localhost:{web_port}")
        elif mini_app_flag:
            log_success(f"Telegram Mini App running at http://localhost:{mini_app_port}")
            log_info("Open this URL in browser to test the Mini App")
        elif args.desktop:
            log_success("Desktop application running")
        elif args.tray:
            log_success("Desktop application running with system tray")
            log_info(f"Backend: http://{args.host}:{backend_port}")
            log_info(f"Web UI: http://localhost:{web_port}")
            log_info("Close the tray icon to stop all services")
        elif args.telegram:
            log_success("Telegram bot is running in polling mode")
            log_info("Bot will receive updates from Telegram")
            if args.telegram_test:
                log_info("Running in TEST MODE - updates will be skipped")
            from backend.core.config import get_settings
            settings = get_settings()
            if settings.telegram_webhook_url:
                log_info(f"Webhook URL: {settings.telegram_webhook_url}")
                log_info("Note: Polling mode is for development only")
                log_info("For production, configure webhook URL")

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
