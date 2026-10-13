import os
from pathlib import Path
import tempfile

# This machine's shared TEMP pytest directory has inherited inaccessible ACLs.
# Use a dedicated project-local temp root without touching global directories.
temp_root = Path(__file__).resolve().parents[1] / '.runtime' / 'tmp'
temp_root.mkdir(parents=True, exist_ok=True)
os.environ['TMP'] = os.environ['TEMP'] = str(temp_root)
tempfile.tempdir = str(temp_root)
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
