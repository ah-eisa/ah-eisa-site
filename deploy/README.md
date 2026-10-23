# ah-eisa.com production boundaries

- Public static source and generated pages: `/var/www/ah-eisa.com`, owned by root. The web worker has read access only; `.git` is root-only.
- Contact process: existing `tara-publisher.service` name, running as dedicated `ah-eisa-contact`; use `ah-eisa-contact.service` as its unit definition. The loopback listener remains port 8099. It supports inquiry intake only; article publishing is retired at both Nginx and application layers.
- Private lead records: `/var/lib/ah-eisa-contact/leads.json`, directory mode 700 and file mode 600. Migrate existing records while the old contact service is stopped; verify byte equality without displaying contents.
- Runtime secrets: `/etc/ah-eisa/contact.env`, root-owned mode 600. systemd reads this file before dropping service privileges. Copy only environment names from `contact.env.example` into version control.
- Deployment: root-owned `/usr/local/sbin/ah-eisa-deploy` copied from `sync_articles.sh`; root cron runs it each minute. The script refreshes the installed copy only after a successful deployment. It uses root-only state under `/var/lib/ah-eisa-deploy`, lock under `/run/ah-eisa-deploy`, and temporary snapshots under `/var/backups/ah-eisa-deploy`.
- Nginx: install `ah-eisa.nginx.conf` and `deploy/ah-eisa-security-headers.conf`. Existing global Cloudflare `set_real_ip_from` plus `real_ip_header CF-Connecting-IP` provide trusted `$remote_addr`; the contact proxy overwrites `X-Ah-Eisa-Client-IP` with that value. Do not substitute an arbitrary request header directly. Preserve TLS, canonical routes and private/source/auth/publish denial rules.

## Credential retirement and replacement

The old shared publishing credential has no accepted application path. Legacy CMS/PAT bridge files are removed, and the shared browser script clears both retired CMS token keys. A GitHub PAT that was previously used must be revoked by its owner in GitHub; removing browser storage does not revoke a provider credential.

A Telegram credential present in earlier Git history must be revoked/replaced by the bot owner in BotFather. Removing it from current source does not revoke it. To preserve existing notification behavior during the transition, the existing value may be provisioned only into the protected runtime file, pending owner rotation. Never print it, validate it with provider calls, or send a replacement through chat.

After replacing the credential in BotFather, run `/usr/local/sbin/ah-eisa-set-telegram-token` with sudo in an interactive owner terminal. This helper reads hidden input, atomically updates the root-only environment file and restarts contact intake. It makes no provider calls or test notifications. The SMTP and durable private inquiry paths remain available independently of Telegram configuration.

## Rollback

Keep a root-only pre-change snapshot of site, service, Nginx, cron and private records. Restore a compatible code/unit/configuration set together; verify record-store ownership and effective write permissions. Never restore backups into a public served directory, and never restore a revoked credential. A code rollback alone is insufficient after moving state outside the document root.
