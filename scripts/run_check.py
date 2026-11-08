"""Record commands, exit codes and scrubbed output without persisting raw output."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--secrets-dir',type=Path)
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    command=args.command[1:] if args.command[:1]==['--'] else args.command
    secret_values=set()
    def collect(value):
        if isinstance(value,dict):
            for x in value.values(): collect(x)
        elif isinstance(value,str) and len(value)>=24: secret_values.add(value)
    if args.secrets_dir:
        for p in args.secrets_dir.rglob('*'):
            if p.is_file() and p.suffix=='.password': secret_values.add(p.read_text().strip())
            elif p.is_file() and p.suffix=='.json': collect(json.loads(p.read_text()))
    for p in Path('.local-runtime').glob('*.env'):
        for line in p.read_text().splitlines():
            if '=' in line:
                k,v=line.split('=',1)
                if ('PASSWORD' in k or 'SECRET' in k or 'KEY_HEX' in k) and v: secret_values.add(v)
    result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    output=result.stdout
    for secret in sorted(secret_values,key=len,reverse=True): output=output.replace(secret,'[REDACTED]')
    output=re.sub(r'(?s)-----BEGIN .*?PRIVATE KEY-----.*?-----END .*?PRIVATE KEY-----','[PRIVATE KEY REDACTED]',output)
    output=re.sub(r'(postgresql(?:\+psycopg)?://[^:\s]+:)[^@\s]+@',r'\1[REDACTED]@',output)
    output=re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', output)
    output='\n'.join(line.rstrip() for line in output.splitlines())+'\n'
    text=f'\nUTC: {datetime.now(timezone.utc).isoformat()}\n$ {shlex.join(command)}\n{output}\nEXIT CODE: {result.returncode}\n'
    args.report.parent.mkdir(parents=True,exist_ok=True)
    with args.report.open('a') as report: report.write(text)
    print(text,end='')
    raise SystemExit(result.returncode)


if __name__=='__main__': main()
