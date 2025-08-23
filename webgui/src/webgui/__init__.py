import argparse
import sys
from pathlib import Path
from webgui.index import run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="WoodsGate Water Measurements Web GUI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Server configuration
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="Host to bind the server to"
    )

    parser.add_argument(
        "--port", type=int, default=8080, help="Port to bind the server to"
    )

    # Database configuration
    parser.add_argument(
        "--db-path",
        type=str,
        default="data.db",
        help="Path to the SQLite database file",
    )

    return parser.parse_args()


def main(args: argparse.Namespace | None = None, reload: bool = False) -> None:
    """Main entry point for the web application with argument parsing."""

    args = args or parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"Error: Database file '{db_path}' not found!", file=sys.stderr)
        sys.exit(1)

    if reload:
        print("🔄 Running in development mode with hot reload enabled")
    else:
        print("🚀 Running in production mode")

    print(f"🗄️  Database: {db_path.absolute()}")
    print(f"🌐 Server: http://{args.host}:{args.port}")
    print("Starting server...")

    try:
        run(
            db_path=str(db_path.absolute()),
            host=args.host,
            port=args.port,
            reload=reload,
        )
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"❌ Error starting server: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ in {"__main__", "__mp_main__"}:
    main(reload=True)
