"""Allows `python -m recon ...` as an alternative to `recon` command """

import sys
from recon.cli import main

sys.exit(main())
