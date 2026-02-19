import sys
from pathlib import Path

# Add project root to sys.path so modules can be imported directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
