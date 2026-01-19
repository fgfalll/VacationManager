"""
Unified entry point for VacationManager.
Can start backend API server, web UI, and desktop app independently or together.
"""

import argparse
import os
import subprocess
import sys
import shutil


def get_project_root():
    """Get the project root directory."""
    return os.path.dirname(os.path.abspath(__file__))


def find_npm():
    """Find npm executable, checking common Windows locations."""
    # Try npm in PATH
    npm = shutil.which("npm")
    if npm:
        return npm

    # Windows-specific npm locations
    npm_paths = [
        os.path.expandvars(r"%ProgramFiles%\nodejs\npm.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\nodejs\npm.exe"),
        os.path.expandvars(r"%LocalAppData%\Programs\nodejs\npm.exe"),
    ]

    for path in npm_paths:
        if os.path.exists(path):
            return path

    # Also try .cmd version on Windows
    npm_cmd_paths = [
        os.path.expandvars(r"%ProgramFiles%\nodejs\npm.cmd"),
        os.path.expandvars(r"%ProgramFiles(x86)%\nodejs\npm.cmd"),
    ]

    for path in npm_cmd_paths:
        if os.path.exists(path):
            return path

    return "npm"  # Fallback - will fail with better error


def start_backend(port: int = 8000, host: str = "127.0.0.1", reload: bool = True):
    """Start the FastAPI backend server."""
    cmd = [
        sys.executable, "-m", "uvicorn",
        "backend.main:app",
        "--host", host,
        "--port", str(port),
    ]
    if reload:
        cmd.append("--reload")

    print(f"Starting backend on http://{host}:{port}")
    return subprocess.Popen(cmd, cwd=get_project_root())


def start_web(dev: bool = True):
    """Start the React web UI."""
    env = os.environ.copy()
    env["VITE_API_URL"] = f"http://127.0.0.1:8000"

    npm_path = find_npm()

    if dev:
        cmd = [npm_path, "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
        print("Starting web UI in development mode...")
    else:
        cmd = [npm_path, "run", "build"]
        print("Building web UI...")

    return subprocess.Popen(cmd, cwd=os.path.join(get_project_root(), "web"), env=env)


def start_desktop():
    """Start the desktop application."""
    cmd = [sys.executable, "-m", "desktop"]
    print("Starting desktop application...")
    return subprocess.Popen(cmd, cwd=get_project_root())


def main():
    parser = argparse.ArgumentParser(
        description="VacationManager - Start backend, web UI, or desktop app",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py --backend   # Start only backend API
  python run.py --web       # Start only web UI
  python run.py --desktop   # Start only desktop app
  python run.py --all       # Start all three
        """
    )

    parser.add_argument("--backend", action="store_true", help="Start backend API server")
    parser.add_argument("--web", action="store_true", help="Start web UI (React)")
    parser.add_argument("--desktop", action="store_true", help="Start desktop application")
    parser.add_argument("--all", action="store_true", help="Start all components")
    parser.add_argument("--port", type=int, default=8000, help="Backend port (default: 8000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Backend host (default: 127.0.0.1)")

    args = parser.parse_args()

    # If no specific option is given, show help
    if not any([args.backend, args.web, args.desktop, args.all]):
        parser.print_help()
        return

    processes = []

    try:
        if args.all or args.backend:
            processes.append(start_backend(port=args.port, host=args.host))

        if args.all or args.web:
            web_proc = start_web(dev=True)
            processes.append(web_proc)

        if args.all or args.desktop:
            processes.append(start_desktop())

        print("\n" + "=" * 50)
        print("VacationManager is running!")
        print("=" * 50)
        if args.backend or args.all:
            print(f"  API:      http://{args.host}:{args.port}")
        if args.web or args.all:
            print(f"  Web UI:   http://localhost:5173")
        if args.desktop or args.all:
            print(f"  Desktop:  Running in separate window")
        print("=" * 50)
        print("\nPress Ctrl+C to stop all services...")

        # Wait for all processes
        for proc in processes:
            proc.wait()

    except KeyboardInterrupt:
        print("\nShutting down...")
        for proc in processes:
            proc.terminate()
        for proc in processes:
            proc.wait()


if __name__ == "__main__":
    main()
