import sys
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
