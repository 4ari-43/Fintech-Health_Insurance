import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv('POLICYIQ_DATA_DIR', str(Path.home() / '.policyiq'))).resolve())
    production: bool = field(default_factory=lambda: os.getenv('POLICYIQ_ENV') == 'production')
    origin: str = field(default_factory=lambda: os.getenv('POLICYIQ_ORIGIN', 'http://127.0.0.1:5173'))
    questions_enabled: bool = field(default_factory=lambda: os.getenv('POLICYIQ_ENABLE_QUESTIONS') == 'true')
    session_seconds: int = 8 * 60 * 60
    auth_limit: int = 10
    max_upload: int = 20 * 1024 * 1024

    def validate(self):
        if self.production and not self.origin.startswith('https://'):
            raise RuntimeError('Production requires an explicit HTTPS POLICYIQ_ORIGIN.')
        if os.getenv('POLICYIQ_AUTH_MODE', 'real') != 'real':
            raise RuntimeError('The API supports real authentication only.')
        self.data_dir.mkdir(parents=True, exist_ok=True)
