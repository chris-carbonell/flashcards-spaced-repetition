from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # database
    database_url: str = "postgresql+psycopg_async://flashcards:flashcards@postgres:5432/flashcards"

    # git repo config
    git_repo_url: str  # e.g. git@gitea.local:user/flashcards.git
    git_repo_path: Path = Path("/data/cards")
    git_ssh_key_path: Path = Path("/secrets/ssh/id_rsa")
    git_user_name: str = "Flashcards App"
    git_user_email: str = "flashcards@local"

    # cards subdir inside the repo (set to "." to use repo root)
    cards_subdir: str = "cards"

    @property
    def git_repo_web_url(self) -> str:
        """derive https url from ssh url for display in the UI.
        e.g. git@github.com:user/repo.git -> https://github.com/user/repo
        """
        import re
        url = self.git_repo_url
        # handle git@host:user/repo.git
        m = re.match(r"git@([^:]+):(.+?)(?:\.git)?$", url)
        if m:
            return f"https://{m.group(1)}/{m.group(2)}"
        # already https
        return url.removesuffix(".git")

    class Config:
        env_file = ".env"


settings = Settings()