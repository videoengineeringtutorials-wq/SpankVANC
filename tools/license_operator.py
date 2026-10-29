"""Generate operator-only SQL and a private 30-day activation key; no public admin API."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]


def private_write(path, text):
    path = Path(path).expanduser().resolve()
    if path.is_relative_to(ROOT):
        raise ValueError('Save license credentials outside the project checkout.')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write(text)


def issue(label, prefix, shared=False):
    if not isinstance(label, str) or not 1 <= len(label.strip()) <= 128:
        raise ValueError('Provide a label of 1–128 characters.')
    key = 'SV1-' + secrets.token_urlsafe(32)
    digest = hashlib.sha256(key.encode()).hexdigest()
    label = label.strip()
    sql_label = label.replace("'", "''")
    # Output contains only a hash. Issuance does not start the activation timer.
    sql = ("INSERT INTO dbo.spankvanc_licenses(key_hash,label,issued_at,shared) VALUES ('" + digest +
           "',N'" + sql_label + "',DATEDIFF(second,CONVERT(datetime,'19700101',112),GETUTCDATE())," + ("1" if shared else "0") + ");\n")
    private_write(str(prefix) + '.json', json.dumps({'key': key, 'label': label, 'key_hash': digest, 'shared': shared}, indent=2) + '\n')
    private_write(str(prefix) + '.sql', sql)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True, help='Private customer/operator label')
    parser.add_argument('--output-prefix', type=Path, required=True, help='Private path outside the project; files must not exist')
    parser.add_argument('--shared', action='store_true', help='Public tester key: each installation gets its own 30 days')
    args = parser.parse_args()
    issue(args.label, args.output_prefix, shared=args.shared)
    print('Private key and SQL files created outside the project. Import the SQL, then deliver the key privately.')


if __name__ == '__main__':
    main()
