"""Allows `python -m recon ...` as an alternative to the `recon` command"""

import sys
from recon.cli import main

sys.exit(main())
