"""Object-level migration inventory from extracted native Access metadata."""
import json
import re
from pathlib import Path
from .landing import read_manifest, iter_rows

DANGER_SQL = [
    ('ui_parameter',r'\bForms\s*!|\bReports\s*!','Form/report-bound reference; replace with explicit API parameter'),
    ('domain_aggregate',r'\b(?:DLookup|DSum|DCount|DAvg|DMax|DMin)\s*\(','Jet domain aggregate; rewrite as SQL join/subquery'),
    ('vba_expression',r'\b(?:Nz|IIf|Format|DateDiff|CDate)\s*\(','Access expression; check null, date and rounding semantics'),
    ('crosstab',r'\bTRANSFORM\b','Crosstab/pivot requires a target-specific query'),
    ('parameters',r'\bPARAMETERS\b','Parameter declaration; adapt to the target driver'),
    ('action_query',r'^\s*(?:UPDATE|DELETE|INSERT|SELECT.+INTO)\b','Review the write side effects before conversion'),
    ('wildcard',r"\bLIKE\s+['\"]\*",'Access wildcard differs from SQL LIKE'),
]


def assess(folder):
    folder = Path(folder)
    source = read_manifest(folder,require_export=False)
    findings=[]
    def add(level,code,location,detail):
        findings.append({'level':level,'code':code,'location':location,'detail':detail})
    for table in source['tables']:
        name=table['name']; cols=table['columns']; indexes=table['indexes']
        if not any(i['primary'] for i in indexes):
            add('high','missing_primary_key',name,'Keyless tables can have duplicate rows and ambiguous linked-table updates')
        for col in cols:
            t=col['type']; location=f'{name}.{col["name"]}'
            if t in ('COMPLEX_TYPE','OLE'):
                add('high','complex_or_binary_column',location,'Handle attachments/OLE explicitly, and check actual bytes')
            if t in ('MONEY','NUMERIC'):
                add('medium','exact_decimal',location,'Preserve decimal scale and define an approved rounding policy')
            if t == 'SHORT_DATE_TIME':
                add('info','date_range',location,'Check pre-1753 dates and timestamp precision before SQL Server datetime conversion')
            if col['name'].casefold() in {'order','select','from','user','table','group','where'}:
                add('medium','reserved_identifier',location,'Quote target identifiers or use an explicit mapping')
        if source['exported']:
            dates=[i for i,c in enumerate(cols) if c['type']=='SHORT_DATE_TIME']
            if dates:
                older=0
                for _,row in iter_rows(folder,table):
                    for i in dates:
                        if isinstance(row[i],str) and re.match(r'^(?:0\d\d\d|1[0-6]\d\d|17[0-4]\d|175[0-2])-\d\d-\d\d',row[i]):
                            older+=1
                if older:
                    add('high','pre_1753_dates',name,f'{older} dates predate SQL Server datetime minimum; use date/datetime2')
    for query in source['queries']:
        sql=query.get('sql')
        if not sql:
            add('high','unreadable_query',query['name'],'Query SQL could not be reconstructed; examine in Windows Access')
            continue
        for code,pattern,message in DANGER_SQL:
            if re.search(pattern,sql,re.I|re.S):
                add('medium',code,query['name'],message)
    for warning in source.get('warnings',[]):
        add('medium','extractor_warning','database',warning)
    add('high','uninspected_application_objects','Access frontend','Forms, reports, macros and VBA require Windows Access inventory; Java/Jet table inspection does not certify them')
    return {'source_file_sha256':source['file_sha256'], 'tables':len(source['tables']),
            'rows':source['total_rows'],'saved_queries':len(source['queries']),
            'findings':findings,'scope':'database objects; no Access UI/VBA execution'}


def markdown(report):
    lines=['# Access migration assessment', '',f"Tables: {report['tables']} · Rows: {report['rows']} · Saved queries: {report['saved_queries']}",
           '', 'This inventory is based on native database metadata. Access forms, reports, macros and VBA still need a Windows application audit.',
           '', '| Severity | Object | Issue | Next action |', '|---|---|---|---|']
    for f in report['findings']:
        def clean(s):return str(s).replace('|','\\|').replace('\n',' ')
        lines.append(f"| {clean(f['level'])} | `{clean(f['location'])}` | {clean(f['code'])} | {clean(f['detail'])} |")
    return '\n'.join(lines)+'\n'
