"""CLI 入口"""

import argparse

from src.cli.main import run_cli
from web.server import run_server


def main():
    parser = argparse.ArgumentParser(description="salsaAuto - 餐饮管理系统自动化工具")
    parser.add_argument("command", nargs="?", default="cli", help="命令: cli, web")
    parser.add_argument("--host", default="127.0.0.1", help="Web 服务地址")
    parser.add_argument("--port", type=int, default=8080, help="Web 服务端口")
    
    args = parser.parse_args()
    
    if args.command == "web":
        print(f"启动 Web 服务: http://{args.host}:{args.port}")
        run_server(host=args.host, port=args.port)
    else:
        run_cli()


if __name__ == "__main__":
    main()