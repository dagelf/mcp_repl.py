Use any MCP servers from the cli or in a REPL, with autocomplete and line editing.

Install Python, and then deps:

```
$ python -m venv venv .venv
$ source .venv/bin/activate
$ pip install uv
$ uv pip install mcp # parallel, so much faster
```

Help:

```
$ python mcp_repl.py --help

usage: mcp_repl.py [URL ...] [--stdio STDIO ...] [-c CMD]

Minimal MCP tester REPL

options:
  -h, --help     show this help message and exit
  --stdio STDIO  stdio server command, e.g. --stdio "python qwenmcp.py"
  -c, --cmd CMD  run command and exit, e.g. -c "web_fetch https://example.com"

Pass one or more MCP server URLs, or repeat --stdio for stdio servers.
Defaults to http://localhost:8000/ when no server is given.
```

Run it from cli:

```
$ python mcp_repl.py http://127.0.0.1:8000 -c "web_fetch https://example.com"
Status: 200
Example Domain
# Example Domain
This domain is for use in documentation examples without needing permission. Avoid use in operations.
[Learn more](https://iana.org/domains/example)

```

Or as a REPL:
 
```
$ python mcp_repl.py
MCP REPL:  [call] <name> {json|k:v|pos...} | refresh | help | params | (exit|quit|q) | (tool|show) | (list|tools|ls)
mcp> 
call	refresh		help	params	(exit|quit|q)	(tool|show)	(tools|list|ls)
mcp> tools
web_fetch(u:string, m?:string, d?:string, md?:boolean, cb?:boolean): Fetch URL. u=url, m=method, d=body, md=markdown, cb=cache bust.
web_search(q:string): Search first 3 configured engines in parallel. q=query.
mcp> web_fetch https://example.com
Status: 200
Example Domain
# Example Domain
This domain is for use in documentation examples without needing permission. Avoid use in operations.
[Learn more](https://iana.org/domains/example)

mcp> ^D
```
