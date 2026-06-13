import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    data_dir: str = field(default_factory=lambda: os.environ.get("DATA_DIR", "./data"))
    content_dir: str = field(default_factory=lambda: os.environ.get("CONTENT_DIR", "./content"))
    password: str = field(default_factory=lambda: os.environ.get("APP_PASSWORD", "changeme"))
    secret_key: str = field(default_factory=lambda: os.environ.get("SECRET_KEY", "dev-insecure-secret"))
    anthropic_api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))

    @property
    def db_path(self) -> str:
        return os.path.join(self.data_dir, "app.db")

    @property
    def claude_enabled(self) -> bool:
        return bool(self.anthropic_api_key.strip())


settings = Settings()
