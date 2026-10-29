"""Command-line entry point; read-only Access handling by default."""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from .assessment import assess, markdown
from .landing import load, reconcile, read_manifest
from .runtime import run_reader
from .tool_probe import probe


def main(argv=None):
    parser=argparse.ArgumentParser(prog='access-fieldkit',description='Inspect and stage Access databases without silently losing legacy data')
    parser.add_argument('--jackcess-jar',help='Use a local Jackcess 5.0.4 jar; useful for offline work')
    cmd=parser.add_subparsers(dest='command',required=True)
    for action in ('inspect','export'):
        p=cmd.add_parser(action, help=f'{action.title()} a source Access file (never writes to source)')
        p.add_argument('source',type=Path)
        p.add_argument('--out',type=Path,required=True)
    p=cmd.add_parser('assess',help='Write a migration assessment based on exported native metadata')
    p.add_argument('folder',type=Path);p.add_argument('--out',type=Path)
    p=cmd.add_parser('load-sqlite',help='Load raw data into a loss-aware SQLite landing database')
    p.add_argument('folder',type=Path);p.add_argument('target',type=Path);p.add_argument('--force',action='store_true')
    p=cmd.add_parser('reconcile',help='Compare every exported Access value against the landing database')
    p.add_argument('folder',type=Path);p.add_argument('target',type=Path)
    p=cmd.add_parser('probe-tools',help='Compare the native inventory with any installed alternative readers')
    p.add_argument('source',type=Path);p.add_argument('folder',type=Path);p.add_argument('--out',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.command in ('inspect','export'):
            if args.out.exists():
                raise FileExistsError('Output folder already exists; choose a new directory')
            args.out.parent.mkdir(parents=True,exist_ok=True)
            folder=Path(tempfile.mkdtemp(prefix='.access-fieldkit-',dir=args.out.parent))
            try:
                run_reader(args.command,args.source,folder,args.jackcess_jar)
                folder.rename(args.out)
            finally:
                if folder.exists():shutil.rmtree(folder)
            print('Manifest:',args.out/'manifest.json')
        elif args.command=='assess':
            result=assess(args.folder)
            md=markdown(result)
            if args.out:
                args.out.parent.mkdir(parents=True,exist_ok=True)
                args.out.write_text(md,encoding='utf-8')
            else:print(md)
            print(json.dumps({'findings':len(result['findings']),'tables':result['tables'],'rows':result['rows']}))
        elif args.command=='probe-tools':
            result=probe(args.source,args.folder)
            output=json.dumps(result,indent=2)
            if args.out:
                args.out.parent.mkdir(parents=True,exist_ok=True)
                args.out.write_text(output+'\n',encoding='utf-8')
            print(output)
        elif args.command=='load-sqlite':
            print(json.dumps(load(args.folder,args.target,args.force),indent=2))
        elif args.command=='reconcile':
            result=reconcile(args.folder,args.target)
            print(json.dumps(result,indent=2))
            if not result['valid']: return 2
        return 0
    except Exception as exc:
        print(f'{args.command}: {exc}',file=sys.stderr)
        return 1

if __name__=='__main__':raise SystemExit(main())
