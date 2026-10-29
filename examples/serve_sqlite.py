"""Tiny read-only HTTP facade over a SQLite landing database.

Not an Access forms replacement. For local exploration; no authentication or
multi-tenant isolation. Bind localhost only, never expose to the Internet.
"""
import argparse
import base64
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote, parse_qs

from access_fieldkit.landing import quote


class Handler(BaseHTTPRequestHandler):
    db = None

    def do_GET(self):
        u=urlsplit(self.path)
        with sqlite3.connect(f'file:{self.db}?mode=ro',uri=True) as conn:
            tables={t[0]:t[1] for t in conn.execute('SELECT table_name, ordinal_field FROM _af_metadata')}
            if u.path=='/tables':
                data={'tables':list(tables)}
            elif u.path.startswith('/tables/'):
                name=unquote(u.path[len('/tables/'):])
                if name not in tables:
                    self.send_error(404,'Unknown table');return
                raw=parse_qs(u.query).get('limit',['50'])[0]
                try: limit=max(1,min(200,int(raw)))
                except ValueError:self.send_error(400,'Invalid limit');return
                rows=conn.execute('SELECT * FROM '+quote(name)+' ORDER BY '+quote(tables[name])+' LIMIT ?', (limit,))
                cols=[col[0] for col in rows.description]
                data={'table':name,'rows':[dict(zip(cols,[(base64.b64encode(v).decode() if isinstance(v,bytes) else v) for v in row])) for row in rows]}
            else:self.send_error(404,'Try /tables');return
        body=json.dumps(data,ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('database',type=Path);p.add_argument('--port',type=int,default=8765)
    args=p.parse_args()
    Handler.db=str(args.database.resolve())
    print(f'Local-only example: http://127.0.0.1:{args.port}/tables')
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
