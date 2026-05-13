import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.recommend import generate_recommendations

if __name__ == "__main__":
    output = generate_recommendations(horizon=30)
    print({key: len(value) for key, value in output.items()})
