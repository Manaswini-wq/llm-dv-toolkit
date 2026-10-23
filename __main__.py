"""CLI entry point."""
import argparse
import asyncio
import sys


def main() -> int:
    parser = argparse.ArgumentParser(prog="llm-dv", description="LLM DV Toolkit")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("generate", help="Generate UVM tests from description")
    sub.add_parser("analyze", help="Analyze simulation failures")
    sub.add_parser("server", help="Start MCP server")

    args = parser.parse_args()
    if args.command == "server":
        from llm_dv_toolkit.mcp_server.server import main as server_main
        server_main()
    elif args.command == "generate":
        from llm_dv_toolkit.test_generator.generator import TestGenerator
        from llm_dv_toolkit.utils.config import Config
        gen = TestGenerator(Config.from_env())
        result = asyncio.run(gen.generate("Write a basic read/write test"))
        print(result)
    elif args.command == "analyze":
        from llm_dv_toolkit.debug_assistant.log_analyzer import LogAnalyzer
        from llm_dv_toolkit.utils.config import Config
        analyzer = LogAnalyzer(Config.from_env())
        print("Use: llm-dv analyze <log_file>")
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
