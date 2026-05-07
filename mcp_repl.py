#!/usr/bin/env python3

# Dependencies:
#   uv pip install mcp

import argparse
import asyncio
import json
import readline
import shlex
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client


HELP = "[call] <name> {json|k:v|pos...} | refresh | help | params | (exit|quit|q) | (tool|show) | (list|tools|ls)"
EXIT = {"exit", "quit", "q"}
LIST = {"list", "tools", "ls"}
SHOW = {"tool", "show"}


@dataclass
class Server:
    label: str
    session: ClientSession


@dataclass
class BoundTool:
    tool: object
    server: Server


def dump(x):
    if hasattr(x, "model_dump"):
        x = x.model_dump(mode="json", exclude_none=True)
    print(json.dumps(x, indent=2, ensure_ascii=False) if isinstance(x, (dict, list)) else x)


def warn(msg):
    print(f"Warning: {msg}", file=sys.stderr)


def err(msg):
    print(f"Error: {msg}", file=sys.stderr)


async def load_tools(servers):
    tools = {}
    for server in servers:
        try:
            for tool in (await server.session.list_tools()).tools:
                if tool.name in tools:
                    warn(f"duplicate tool {tool.name!r}; rightmost server will be used")
                tools[tool.name] = BoundTool(tool, server)
        except Exception as e:
            err(f"{server.label}: list_tools failed: {e}")
    return tools


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
    names = param_names(tool)
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


def schema(tool):
    return tool.inputSchema or {}


def required(tool):
    return set(schema(tool).get("required", []))


def param_type(meta):
    t = meta.get("type")
    if isinstance(t, list):
        return "|".join(t)
    if t:
        return t
    if "anyOf" in meta:
        return "|".join(param_type(x) for x in meta["anyOf"])
    if "enum" in meta:
        return "enum"
    return "any"


def param_names(tool):
    return list(schema(tool).get("properties", {}))


def params_summary(tool):
    req = required(tool)
    bits = []
    for name, meta in schema(tool).get("properties", {}).items():
        suffix = "" if name in req else "?"
        bits.append(f"{name}{suffix}:{param_type(meta)}")
    return ", ".join(bits) or "no params"


def describe_tool(name, tool):
    desc = tool.description or ""
    params = params_summary(tool)
    return f"{name}({params})" + (f": {desc}" if desc else "")


def print_params(tool):
    props = schema(tool).get("properties", {})
    if not props:
        print("no params")
        return
    req = required(tool)
    for name, meta in props.items():
        flag = "required" if name in req else "optional"
        line = f"{name}: {param_type(meta)} ({flag})"
        if "default" in meta:
            line += f", default={meta['default']!r}"
        if "enum" in meta:
            line += f", enum={meta['enum']!r}"
        if meta.get("description"):
            line += f" - {meta['description']}"
        print(line)


def named_tool(tools, name):
    try:
        return tools[name]
    except KeyError:
        raise ValueError(f"unknown tool: {name}") from None


def need_arg(rest, usage):
    if rest:
        return rest[0]
    raise ValueError(f"usage: {usage}")


async def run_line(servers, tools, line):
    parts = line.strip().split(maxsplit=2)
    if not parts:
        return tools, 0, False
    cmd, rest = parts[0], parts[1:]
    if cmd in EXIT:
        return tools, 0, True
    if cmd == "help":
        print(HELP)
    elif cmd == "refresh":
        tools = await load_tools(servers)
        print(f"{len(tools)} tools")
    elif cmd in LIST:
        print("\n".join(describe_tool(n, tools[n].tool) for n in tools))
    elif cmd == "params":
        print_params(named_tool(tools, need_arg(rest, "params <name>")).tool)
    elif cmd in SHOW:
        dump(named_tool(tools, need_arg(rest, f"{cmd} <name>")).tool)
    elif cmd == "call":
        name = need_arg(rest, "call <name> {json|k:v|pos...}")
        bound = named_tool(tools, name)
        raw = rest[1] if len(rest) > 1 else ""
        print(text(await bound.server.session.call_tool(name, call_args(bound.tool, raw))))
    elif cmd in tools:
        bound = tools[cmd]
        print(text(await bound.server.session.call_tool(cmd, call_args(bound.tool, " ".join(rest)))))
    else:
        err("unknown command")
        return tools, 1, False
    return tools, 0, False


@asynccontextmanager
async def connect_url(url):
    async with streamablehttp_client(url) as (r, w, _):
        yield r, w


@asynccontextmanager
async def connect_stdio(command):
    cmd = shlex.split(command)
    if not cmd:
        raise ValueError("--stdio command cannot be empty")
    async with stdio_client(StdioServerParameters(command=cmd[0], args=cmd[1:])) as streams:
        yield streams[:2]


async def open_server(stack, label, conn):
    read, write = await stack.enter_async_context(conn)
    session = await stack.enter_async_context(ClientSession(read, write))
    await session.initialize()
    return Server(label, session)


async def open_servers(args):
    urls = args.url or ([] if args.stdio else ["http://localhost:8000/"])
    servers = []
    stack = AsyncExitStack()
    for url in urls:
        try:
            servers.append(await open_server(stack, url, connect_url(url)))
        except Exception as e:
            err(f"{url}: connect failed: {e}")
    for command in args.stdio:
        try:
            servers.append(await open_server(stack, f"stdio:{command}", connect_stdio(command)))
        except Exception as e:
            err(f"stdio:{command}: connect failed: {e}")
    if servers:
        return stack, servers
    else:
        await stack.aclose()
        raise RuntimeError("no MCP servers connected")


async def main():
    ap = argparse.ArgumentParser(description="Minimal MCP tester REPL")
    ap.add_argument("url", nargs="*", help="streamable HTTP MCP server URL(s)")
    ap.add_argument("--stdio", action="append", default=[], help='stdio server command, e.g. --stdio "python qwenmcp.py"')
    ap.add_argument("-c", "--cmd", action="append", help='run command and exit, e.g. -c "web_fetch https://example.com"')
    args = ap.parse_args()

    stack, servers = await open_servers(args)
    async with stack:
        tools = await load_tools(servers)
        cmds = sorted(EXIT | LIST | SHOW | {"call", "refresh", "help", "params"})

        if args.cmd:
            code = 0
            for line in args.cmd:
                try:
                    tools, rc, done = await run_line(servers, tools, line)
                except Exception as e:
                    err(str(e))
                    rc, done = 1, False
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
        print(f"MCP REPL: {HELP}")

        while True:
            try:
                line = input("mcp> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not line:
                continue
            try:
                tools, _, done = await run_line(servers, tools, line)
                if done:
                    return
            except Exception as e:
                err(str(e))


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()) or 0)
