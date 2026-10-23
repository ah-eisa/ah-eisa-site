#!/usr/bin/env python3
"""Owner-operated, hidden-input credential replacement. No provider calls."""
import getpass
import os
from pathlib import Path
import re
import subprocess
import tempfile

def main():
    if os.geteuid() != 0:
        raise SystemExit("Run with sudo in your own interactive terminal.")
    destination = Path('/etc/ah-eisa/contact.env')
    if destination.is_symlink() or not destination.is_file():
        raise SystemExit("Expected a regular protected runtime environment file.")
    token = getpass.getpass('New BotFather token (hidden): ').strip()
    if not re.fullmatch(r'[0-9]{5,}:[A-Za-z0-9_-]{20,}', token):
        raise SystemExit('Unexpected token format; nothing changed.')
    lines = destination.read_text().splitlines()
    previous = next((line.split('=',1)[1] for line in lines if line.startswith('TELEGRAM_BOT_TOKEN=')), '')
    if previous and token.split(':',1)[0] != previous.split(':',1)[0]:
        raise SystemExit('Different bot identity; configuration unchanged.')
    lines = [line for line in lines if not line.startswith('TELEGRAM_BOT_TOKEN=')]
    lines.append('TELEGRAM_BOT_TOKEN=' + token)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=destination.parent, delete=False) as output:
            temporary = output.name
            os.chmod(temporary, 0o600)
            output.write('\n'.join(lines)+'\n')
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            os.unlink(temporary)
    unit = Path('/etc/systemd/system/tara-publisher.service').read_text()
    if 'EnvironmentFile=/etc/ah-eisa/contact.env' in unit and 'User=ah-eisa-contact' in unit:
        subprocess.run(['systemctl','restart','tara-publisher.service'],check=True)
        print('Protected configuration updated and contact service restarted.')
    else:
        print('Protected configuration saved; activation awaits the service deployment.')
    print('No Telegram message or API request was sent.')

if __name__ == '__main__':
    main()
