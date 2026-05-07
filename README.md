Use any MCP server from the cli

```
$ python -m venv venv .venv
$ source .venv/bin/activate
$ pip install uv
$ uv pip install mcp # parallel, so much faster

$ python mcp_repl.py --help

usage: mcp_repl.py [-h] [--stdio STDIO] [-c CMD] [url]

Minimal MCP tester REPL

positional arguments:
  url

options:
  -h, --help     show this help message and exit
  --stdio STDIO  stdio server command, e.g. --stdio "python qwenmcp.py"
  -c, --cmd CMD  run command and exit, e.g. -c "web_fetch https://example.com"

$ python mcp_repl.py http://127.0.0.1:8000 -c "web_fetch https://exmaple.com"
Status: 200
Example Domain
# Example Domain
This domain is for use in documentation examples without needing permission. Avoid use in operations.
[Learn more](https://iana.org/domains/example)

$ python mcp_repl.py
MCP REPL: tools | tool <name> | [call] <name> {json|k:v|pos...} | refresh | quit
mcp> 
call     exit     help     q        quit     refresh  tool     tools    
mcp> tools
web_fetch: Fetch URL. u=url, m=method, d=body, md=markdown, cb=cache bust.
web_search: Search first 3 configured engines in parallel. q=query.
mcp> web_fetch https://example.com
Status: 200
Example Domain
# Example Domain
This domain is for use in documentation examples without needing permission. Avoid use in operations.
[Learn more](https://iana.org/domains/example)

```
