import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.data_generator import generate_dataset

if __name__ == "__main__":
    print(generate_dataset())
