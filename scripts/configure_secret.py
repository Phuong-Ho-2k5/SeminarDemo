"""Set production DEMO_TOKEN through Wrangler stdin; never display the value."""
import argparse
import getpass
from pathlib import Path
import secrets
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generate', action='store_true',
                        help='Create/reuse the ignored .demo-token file for the presenter')
    args = parser.parse_args()
    if args.generate:
        path = ROOT / '.demo-token'
        if path.exists():
            token = path.read_text(encoding='utf-8').strip()
        else:
            token = secrets.token_urlsafe(32)
            with path.open('x', encoding='utf-8') as output:
                output.write(token + '\n')
        print('Production demo credential is in ignored .demo-token; value will not be printed.', flush=True)
    else:
        token = getpass.getpass('Production DEMO_TOKEN (hidden): ')
    if not token or '\n' in token or '\r' in token:
        raise ValueError('Token must be nonempty and contain no newlines')
    command = [shutil.which('node'), str(ROOT / 'node_modules/wrangler/bin/wrangler.js'),
               'secret', 'put', 'DEMO_TOKEN']
    return subprocess.run(command, cwd=ROOT, input=token + '\n', text=True, check=False).returncode


if __name__ == '__main__':
    sys.exit(main())
