#!/usr/bin/env python3
"""
Launch the IntoTheUnknown web interface.

Usage:
    python run_web.py [--host HOST] [--port PORT] [--debug]

Environment:
    OPENAI_API_KEY: Set to enable OpenAI integration (optional)
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Run IntoTheUnknown Web Interface")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    try:
        from web.app import app
    except ImportError as e:
        print(f"Error: {e}")
        print("\nPlease install required dependencies:")
        print("  pip install flask")
        sys.exit(1)

    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║             IntoTheUnknown - Web Interface                    ║
║         AI Memory Governance and Behavioral Constraints       ║
╠═══════════════════════════════════════════════════════════════╣
║  Chat Interface:    http://{args.host}:{args.port}/                       ║
║  Audit Dashboard:   http://{args.host}:{args.port}/audit                  ║
╚═══════════════════════════════════════════════════════════════╝
""")

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
