import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(CURRENT_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from frontend.flask_app import create_app

app = create_app()

if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5050"))
    app.run(host=host, port=port, debug=True)
