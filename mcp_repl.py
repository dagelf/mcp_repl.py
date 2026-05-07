#!/usr/bin/env python3

# Dependencies:
#   uv pip install mcp

import argparse
import asyncio
import json
import readline
import shlex
import sys
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client


def dump(x):
    if hasattr(x, "model_dump"):
        x = x.model_dump(mode="json", exclude_none=True)
    print(json.dumps(x, indent=2, ensure_ascii=False) if isinstance(x, (dict, list)) else x)


def text(result):
    return "\n".join(getattr(c, "text", str(c)) for c in result.content)


def val(s):
    try:
        return json.loads(s)
    except Exception:
        return s


def call_args(tool, raw):
    if not raw:
        return {}
    raw = raw.strip()
    if raw.startswith("{"):
        return json.loads(raw)
    names = list(tool.inputSchema.get("properties", {}))
    out, pos = {}, 0
    for tok in shlex.split(raw):
        if ":" in tok and not tok.startswith(("http://", "https://")):
            k, v = tok.split(":", 1)
            out[k] = val(v)
        else:
            if pos >= len(names):
                raise ValueError("too many positional args")
            out[names[pos]] = val(tok)
            pos += 1
    return out


async def run_line(s, tools, line):
    parts = line.strip().split(maxsplit=2)
    if not parts:
        return tools, 0, False
    cmd, rest = parts[0], parts[1:]
    if cmd in {"q", "quit", "exit"}:
        return tools, 0, True
    if cmd == "help":
        print("tools | tool <name> | [call] <name> {json|k:v|pos...} | refresh | quit")
    elif cmd == "refresh":
        tools = {t.name: t for t in (await s.list_tools()).tools}
        print(f"{len(tools)} tools")
    elif cmd == "tools":
        print("\n".join(f"{n}: {tools[n].description or ''}" for n in tools))
    elif cmd == "tool" and rest:
        dump(tools[rest[0]])
    elif cmd == "call" and rest:
        print(text(await s.call_tool(rest[0], call_args(tools[rest[0]], rest[1] if len(rest) > 1 else ""))))
    elif cmd in tools:
        print(text(await s.call_tool(cmd, call_args(tools[cmd], " ".join(rest)))))
    else:
        print("unknown command", file=sys.stderr)
        return tools, 1, False
    return tools, 0, False


@asynccontextmanager
async def connect(args):
    if args.stdio:
        cmd = shlex.split(args.stdio)
        async with stdio_client(StdioServerParameters(command=cmd[0], args=cmd[1:])) as streams:
            yield streams[:2]
    else:
        async with streamablehttp_client(args.url) as (r, w, _):
            yield r, w


async def main():
    ap = argparse.ArgumentParser(description="Minimal MCP tester REPL")
    ap.add_argument("url", nargs="?", default="http://localhost:8000/")
    ap.add_argument("--stdio", help='stdio server command, e.g. --stdio "python qwenmcp.py"')
    ap.add_argument("-c", "--cmd", action="append", help='run command and exit, e.g. -c "web_fetch https://example.com"')
    args = ap.parse_args()

    async with connect(args) as (read, write), ClientSession(read, write) as s:
        await s.initialize()
        tools = {t.name: t for t in (await s.list_tools()).tools}
        cmds = ["tools", "tool", "call", "refresh", "help", "quit", "exit", "q"]

        if args.cmd:
            code = 0
            for line in args.cmd:
                tools, rc, done = await run_line(s, tools, line)
                code = code or rc
                if done:
                    break
            return code

        def complete(txt, state):
            line = readline.get_line_buffer()
            opts = cmds if " " not in line else list(tools)
            hits = [x for x in opts if x.startswith(txt)]
            return (hits + [None])[state]

        readline.parse_and_bind("tab: complete")
        readline.set_completer(complete)
        print("MCP REPL: tools | tool <name> | [call] <name> {json|k:v|pos...} | refresh | quit")

        while True:
            try:
                line = input("mcp> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            parts = line.split(maxsplit=2)
            if not parts:
                continue
            try:
                tools, _, done = await run_line(s, tools, line)
                if done:
                    return
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()) or 0)
