"""Optional independent reader checks, never a claim of SSMA execution."""
import csv
import hashlib
import io
import json
import shutil
import subprocess
from pathlib import Path

from .landing import read_manifest


def checksum(file):
    h=hashlib.sha256()
    with Path(file).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def command(args,timeout=45):
    try:
        return subprocess.run(args,capture_output=True,text=True,timeout=timeout,check=False)
    except (OSError,subprocess.TimeoutExpired) as ex:
        return type('FailedProbe',(),{'returncode':-1,'stdout':'','stderr':type(ex).__name__})()


def probe(source,folder):
    source=Path(source)
    m=read_manifest(folder,require_export=True)
    if checksum(source)!=m['file_sha256']:
        raise ValueError('Source Access file changed since export; do not compare different snapshots')
    steps=[{'tool':'Jackcess','status':'verified','operation':'Read and export native Access data',
            'evidence':f'{len(m["tables"])} tables, {m["total_rows"]} rows; matching original file fingerprint'}]
    tables_exe=shutil.which('mdb-tables')
    export_exe=shutil.which('mdb-export')
    if not tables_exe:
        steps.append({'tool':'MDB Tools','status':'not_run','operation':'Independent table inventory/export',
                      'evidence':'mdb-tables executable not installed'})
    else:
        result=command([tables_exe,'-1',str(source)])
        names={line.rstrip('\r') for line in result.stdout.splitlines() if line.strip()}
        expected={t['name'] for t in m['tables']}
        if result.returncode!=0 or names!=expected:
            steps.append({'tool':'MDB Tools','status':'failed','operation':'Independent table inventory',
                          'evidence':f'Exit {result.returncode}; expected {len(expected)}, saw {len(names)}; stderr={result.stderr[:200]}'})
        else:
            steps.append({'tool':'MDB Tools','status':'verified','operation':'Independent table inventory',
                          'evidence':f'{len(names)} table names matched the Access inventory'})
            candidates=[t for t in m['tables'] if t['rows']<=10000 and all(c['type'] not in ('OLE','COMPLEX_TYPE') for c in t['columns'])]
            sample=sorted(candidates,key=lambda t:(t['rows'],t['name']))[0] if candidates else None
            if sample and export_exe:
                r=command([export_exe,str(source),sample['name']])
                try:
                    csvrows=csv.reader(io.StringIO(r.stdout,newline=''))
                    header=next(csvrows)
                    count=sum(1 for _ in csvrows)
                    match=(r.returncode==0 and count==sample['rows'] and header==[c['name'] for c in sample['columns']])
                except (ValueError,csv.Error,StopIteration):match=False;count=-1
                steps.append({'tool':'MDB Tools','status':'verified' if match else 'failed',
                              'operation':'Independent CSV export of '+sample['name'],
                              'evidence':f'Expected {sample["rows"]} rows; got {count}. Headers also compared. This does not prove full type fidelity.'})
            else:
                steps.append({'tool':'MDB Tools','status':'not_run','operation':'Independent CSV export',
                              'evidence':'No suitable small table or mdb-export not installed'})
    steps.append({'tool':'Microsoft SSMA for Access','status':'not_run',
                  'operation':'Windows assessment / SQL Server schema and data conversion',
                  'evidence':'Requires actual SSMA execution on Windows with Access/ACE and SQL Server/Azure SQL'})
    return {'file_sha256':m['file_sha256'],'probes':steps,
            'note':'Verified applies only to the stated operation; it does not establish application or VBA migration success.'}
