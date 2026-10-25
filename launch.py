import sys
from assetflow.gui import main

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
        from assetflow.smoke import run
        raise SystemExit(run(sys.argv[2]))
    main()
