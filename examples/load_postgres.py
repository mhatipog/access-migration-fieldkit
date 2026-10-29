"""One-off PostgreSQL landing loader. Usage in guides/postgresql.md.

Requires psycopg 3. Creates new tables in a dedicated schema; refuses to reuse
an occupied schema. Run with a disposable or explicitly approved database DSN.
"""
import argparse
import json
import re
from pathlib import Path

from access_fieldkit.landing import check_checksum, decode, iter_rows, quote, read_manifest


TYPES = {
    'BOOLEAN':'BOOLEAN', 'BYTE':'SMALLINT', 'INT':'SMALLINT',
    'LONG':'INTEGER', 'BIG_INT':'BIGINT', 'SHORT':'SMALLINT',
    'FLOAT':'REAL', 'DOUBLE':'DOUBLE PRECISION',
    'MONEY':'NUMERIC(19,4)', 'NUMERIC':'NUMERIC',
    'SHORT_DATE_TIME':'TIMESTAMP WITHOUT TIME ZONE',
    'OLE':'BYTEA', 'BINARY':'BYTEA',
}


def run(folder, dsn, schema):
    import psycopg
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,62}',schema):
        raise ValueError('Choose a simple new schema name')
    source = read_manifest(folder)
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            exists = cur.execute('SELECT 1 FROM information_schema.schemata WHERE schema_name=%s',(schema,)).fetchone()
            if exists:
                raise ValueError(f'Schema {schema} already exists. Use a fresh schema; no destructive overwrite is allowed.')
            cur.execute('CREATE SCHEMA '+quote(schema))
            for table in source['tables']:
                columns=table['columns']
                if len(table['name'].encode('utf-8'))>63 or any(len(c['name'].encode('utf-8'))>63 for c in columns):
                    raise ValueError(f'PostgreSQL 63-byte identifier limit hit in {table["name"]}; explicitly map names')
                ordinal='_af_source_row'
                while ordinal.casefold() in {x['name'].casefold() for x in columns}:
                    ordinal+='_'
                spec=quote(ordinal)+' BIGINT PRIMARY KEY'
                spec+=''.join(','+quote(c['name'])+' '+TYPES.get(c['type'],'TEXT') for c in columns)
                relation=quote(schema)+'.'+quote(table['name'])
                cur.execute('CREATE TABLE '+relation+' ('+spec+')')
                check_checksum(Path(folder)/table['data_file'],table['sha256'])
                batch=[]; n=0
                ins='INSERT INTO '+relation+' VALUES ('+','.join('%s' for _ in range(len(columns)+1))+')'
                for row_number, values in iter_rows(folder, table):
                    batch.append([row_number,*[decode(value) for value in values]])
                    n+=1
                    if len(batch)>=500:
                        cur.executemany(ins,batch);batch.clear()
                if batch:cur.executemany(ins,batch)
                if n!=table['rows'] or cur.execute('SELECT COUNT(*) FROM '+relation).fetchone()[0]!=n:
                    raise ValueError('Source/target row mismatch for '+table['name'])
                print(f'{table["name"]}: {n} rows')
        conn.commit()
    print(f'Loaded {source["total_rows"]} rows into schema {schema}. Validate business rules before cutover.')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('export',type=Path)
    p.add_argument('--dsn',required=True,help='Dedicated PostgreSQL connection string')
    p.add_argument('--schema',default='access_landing')
    args=p.parse_args()
    run(args.export,args.dsn,args.schema)