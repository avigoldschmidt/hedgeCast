import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hedgecast.main import create_app  # noqa: E402

TARGET = Path(__file__).resolve().parents[2] / "frontend" / "src" / "api" / "openapi.json"


def spec():
    return create_app().openapi()


def render():
    return json.dumps(spec(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(render())
    print(f"wrote {TARGET}")
