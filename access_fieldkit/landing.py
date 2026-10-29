"""Loss-aware SQLite landing zone: preserves source ordinals and duplicate rows.

This is staging, not an automatic normalized schema conversion. No source keys or
foreign keys are invented; duplicate and orphaned records remain inspectable.
"""
import base64
import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path


def quote(name):
    if not isinstance(name, str) or '\x00' in name or not name:
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return '"' + name.replace('"', '""') + '"'


def read_manifest(folder, require_export=True):
    folder = Path(folder)
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format') != 'access-fieldkit-v1':
        raise ValueError('Unrecognized export format')
    if require_export and not manifest.get('exported'):
        raise ValueError('Only an inventory was supplied; run export first')
    ids = [t['name'].casefold() for t in manifest['tables']]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate case-insensitive table names')
    for t in manifest['tables']:
        names = [c['name'].casefold() for c in t['columns']]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate column names in {t['name']}")
        if require_export:
            data_file = t['data_file']
            if data_file != Path(data_file).name or not data_file.startswith('table-') or not data_file.endswith('.jsonl'):
                raise ValueError('Unsafe data file path in export manifest')
    return manifest


def check_checksum(path, expected):
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(block)
    got = digest.hexdigest()
    if got != expected:
        raise ValueError(f'Data checksum mismatch: {path.name} (expected {expected}, got {got})')
    return got


def iter_rows(folder, table):
    source = Path(folder) / table['data_file']
    with source.open(encoding='utf-8', newline='') as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                raise ValueError(f'Blank source record: {source}:{line_num}')
            row = json.loads(line)
            if not isinstance(row, list) or len(row) != len(table['columns']):
                raise ValueError(f'Invalid source record: {source}:{line_num}')
            yield line_num, row


def decode(value):
    if isinstance(value, dict):
        if len(value) != 1:
            raise ValueError('Unknown tagged Access value')
        tag, raw = next(iter(value.items()))
        if not isinstance(raw, str):
            raise ValueError('Malformed tagged Access value')
        if tag == '$binary':
            return base64.b64decode(raw, validate=True)
        if tag == '$decimal':
            # SQLite has no exact decimal storage class. Use TEXT without
            # losing the Access Currency value's original decimal scale.
            return raw
        if tag == '$float':
            return float(raw)
        raise ValueError(f'Unsupported tagged Access value: {tag}')
    if isinstance(value, (list, dict)):
        raise ValueError('Nested Access value must be extracted explicitly')
    return value


def dtype(access_type):
    if access_type in ('BYTE', 'INT', 'LONG', 'BIG_INT', 'SHORT', 'BOOLEAN'):
        return 'INTEGER'
    if access_type in ('DOUBLE', 'FLOAT'):
        return 'REAL'
    if access_type in ('BINARY', 'OLE'):
        return 'BLOB'
    return 'TEXT'


def load(folder, target, force=False):
    folder, target = Path(folder), Path(target)
    manifest = read_manifest(folder)
    if target.exists() and not force:
        raise FileExistsError(f'{target} exists (use --force to replace a disposable target)')
    if target.is_symlink():
        raise ValueError('Refusing to replace a symlink target')
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmpname = tempfile.mkstemp(prefix='.access-fieldkit-', suffix='.sqlite', dir=target.parent)
    os.close(fd)
    tmp = Path(tmpname)
    conn = None
    stats = []
    try:
        conn = sqlite3.connect(tmp)
        conn.execute('PRAGMA journal_mode=DELETE')
        conn.execute('PRAGMA synchronous=FULL')
        conn.execute('CREATE TABLE _af_metadata (table_name TEXT PRIMARY KEY, ordinal_field TEXT NOT NULL, data_file TEXT NOT NULL, sha256 TEXT NOT NULL)')
        for table in manifest['tables']:
            name = table['name']
            columns = table['columns']
            ordinal = '_af_source_row'
            existing = {c['name'].casefold() for c in columns}
            while ordinal.casefold() in existing:
                ordinal += '_'
            fields = [quote(ordinal) + ' INTEGER PRIMARY KEY']
            fields += [quote(c['name']) + ' ' + dtype(c['type']) for c in columns]
            if name.casefold() == '_af_metadata':
                raise ValueError('Source table name collides with internal metadata table')
            conn.execute('CREATE TABLE ' + quote(name) + ' (' + ','.join(fields) + ')')
            check_checksum(folder / table['data_file'], table['sha256'])
            placeholders = ','.join('?' for _ in range(len(columns)+1))
            insert = 'INSERT INTO ' + quote(name) + ' VALUES (' + placeholders + ')'
            count = 0
            batch = []
            for num, values in iter_rows(folder, table):
                batch.append([num, *(decode(v) for v in values)])
                if len(batch) >= 500:
                    conn.executemany(insert, batch)
                    batch.clear()
                count += 1
            if batch:
                conn.executemany(insert, batch)
            if count != table['rows']:
                raise ValueError(f'Row-count mismatch for {name}: {count} != {table["rows"]}')
            conn.execute('INSERT INTO _af_metadata VALUES (?,?,?,?)', (name, ordinal, table['data_file'], table['sha256']))
            stats.append({'name':name,'rows':count})
        conn.commit()
        conn.close()
        conn = None
        # An atomic replacement keeps any prior target intact on a failed load.
        os.replace(tmp, target)
        return {'target':str(target),'tables':len(stats),'rows':sum(x['rows'] for x in stats),'status':'loaded','detail':stats}
    finally:
        if conn is not None:
            conn.close()
        if tmp.exists():
            tmp.unlink()


def reconcile(folder, target):
    folder, target = Path(folder), Path(target)
    manifest = read_manifest(folder)
    issues = []
    total = 0
    with sqlite3.connect(f'file:{target.resolve()}?mode=ro', uri=True) as conn:
        try:
            mappings = {name:(ordinal,filename,digest) for name,ordinal,filename,digest in conn.execute('SELECT * FROM _af_metadata')}
        except sqlite3.Error as ex:
            raise ValueError('Not an access-fieldkit SQLite landing database') from ex
        if set(mappings) != {t['name'] for t in manifest['tables']}:
            issues.append('Table inventory differs between source export and target')
        for table in manifest['tables']:
            name = table['name']
            if name not in mappings:
                continue
            ordinal,filename,digest=mappings[name]
            try:
                check_checksum(folder/table['data_file'],table['sha256'])
                if digest!=table['sha256'] or filename!=table['data_file']:
                    issues.append(f'{name}: source fingerprint does not match landing metadata')
                got = conn.execute('SELECT * FROM ' + quote(name) + ' ORDER BY ' + quote(ordinal))
                count = 0
                for (num,source), row in zip(iter_rows(folder,table),got):
                    gotordinal,*values = row
                    if gotordinal!=num:
                        issues.append(f'{name}: row ordinal mismatch at {num}')
                    for col,original,actual in zip(table['columns'],source,values):
                        expected=decode(original)
                        if isinstance(expected,float):
                            equal = expected == actual
                        else:
                            equal = expected == actual and type(expected) is type(actual)
                            # SQLite stores Boolean as 0/1 rather than bool.
                            if isinstance(expected,bool):
                                equal = int(expected) == actual
                        if not equal:
                            issues.append(f'{name}: value mismatch row {num} column {col["name"]}')
                        if len(issues)>=20:
                            break
                    count+=1
                    if len(issues)>=20:
                        break
                count_db=conn.execute('SELECT COUNT(*) FROM '+quote(name)).fetchone()[0]
                if count_db!=table['rows'] or count!=table['rows']:
                    issues.append(f'{name}: source={table["rows"]} compared={count} target={count_db}')
                total+=count_db
            except (ValueError,sqlite3.Error) as ex:
                issues.append(f'{name}: {ex}')
            if len(issues)>=20:
                break
    return {'valid':not issues,'source_file_sha256':manifest['file_sha256'],'tables':len(manifest['tables']),
            'rows':total,'issues':issues[:25]}
