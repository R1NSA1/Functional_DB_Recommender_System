from __future__ import annotations

import json
from pathlib import Path

from recommenders import DEFAULT_DATABASE_URL, build_demo


OUTPUT_PATH = Path(__file__).resolve().parent / "demo_results.json"


def main() -> None:
    result = build_demo(
        database_url=DEFAULT_DATABASE_URL,
        user_id=15,
        seed_movie_id=318,
        top_n=10,
    )
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
