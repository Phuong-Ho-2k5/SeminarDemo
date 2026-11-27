"""Create a local demo secret without displaying it or overwriting existing data."""
from pathlib import Path
import secrets

destination = Path(__file__).resolve().parents[1] / '.dev.vars'
if destination.exists():
    print('.dev.vars already exists; unchanged.')
else:
    with destination.open('x', encoding='utf-8') as output:
        output.write(f'DEMO_TOKEN="{secrets.token_urlsafe(32)}"\n')
    print('Created .dev.vars. Secret stays in this ignored local file.')
