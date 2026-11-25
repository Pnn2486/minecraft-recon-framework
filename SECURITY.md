# Security policy

## Reporting a problem

If you find a security problem in this project, please don't open a public issue. Use the **Report a vulnerability** button on the Security tab of the repository page instead, so only the maintainer sees it until it is fixed.

Please include the version (`recon --version`), your system, and the steps to reproduce it. A short description is enough, I will ask if I need more.

## What counts

- The web interface being reachable from anything other than the computer it runs on
- A way around the permission checkbox, the per-run token or the host and origin checks
- A server being able to crash, hang or exhaust the memory of the client with crafted replies
- Passwords or other secrets ending up in output, logs or files

## What doesn't

- Needing a password for RCON or a settings file you wrote yourself, those are meant to work that way
- The tool talking to a server you pointed it at, that is what it is for
- Findings that only apply when someone already has full control of your computer

## Supported versions

This project is in beta. Fixes go into the newest version only.

## Using it responsibly

Only test servers you own or have written permission to test. See [COPYING.md](./COPYING.md) and [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md).
