"""PyInstaller entry point for the Kokoro sidecar."""

from src.api.server import main


if __name__ == "__main__":
    main()
