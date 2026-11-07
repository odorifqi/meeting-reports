import os
import sys
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="mn-test-"))
os.environ.setdefault("MN_SUPPORT_DIR", str(_tmp / "support"))
os.environ.setdefault("MN_OUTPUT_DIR", str(_tmp / "out"))
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
