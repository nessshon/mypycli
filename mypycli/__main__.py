import shutil
import sys
from importlib.resources import as_file, files
from pathlib import Path


def main() -> None:
    if sys.argv[1:] != ["init"]:
        print("usage: mypycli init")
        raise SystemExit(2)

    target = Path.cwd() / "locales"
    if target.exists():
        print(f"error: {target} already exists")
        raise SystemExit(1)

    with as_file(files("mypycli").joinpath("components/translator/locales")) as source:
        shutil.copytree(source, target)
    print(f"created: {target}")


if __name__ == "__main__":
    main()
