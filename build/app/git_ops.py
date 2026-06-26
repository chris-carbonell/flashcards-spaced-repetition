"""
handles all git + markdown file operations.

the flow for mutations is always:
  pull --rebase → make change → commit → push

this keeps things safe even if someone edits the repo directly.
"""
import os
import re
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import frontmatter
import git

from app.config import settings

log = logging.getLogger(__name__)


@dataclass
class Card:
    slug: str
    question: str
    answer: str
    tags: list[str] = field(default_factory=list)
    created: Optional[str] = None
    raw_path: Optional[Path] = None


def _ssh_env() -> dict:
    """build GIT_SSH_COMMAND that uses our mounted key"""
    key = settings.git_ssh_key_path
    return {
        "GIT_SSH_COMMAND": f"ssh -i {key} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
    }


def _cards_dir() -> Path:
    base = settings.git_repo_path
    if settings.cards_subdir == ".":
        return base
    return base / settings.cards_subdir


def _slug_to_path(slug: str) -> Path:
    return _cards_dir() / f"{slug}.md"


def _path_to_slug(path: Path) -> str:
    return path.stem


def _slugify(title: str) -> str:
    """turn a card question/title into a filesystem-safe slug"""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = slug.strip("-")
    return slug[:80]  # keep filenames reasonable


def _get_repo() -> git.Repo:
    return git.Repo(settings.git_repo_path)


def _configure_repo(repo: git.Repo):
    repo.config_writer().set_value("user", "name", settings.git_user_name).release()
    repo.config_writer().set_value("user", "email", settings.git_user_email).release()


def _pull(repo: git.Repo):
    with repo.git.custom_environment(**_ssh_env()):
        repo.git.pull("--rebase", "origin", repo.active_branch.name)


def _push(repo: git.Repo):
    with repo.git.custom_environment(**_ssh_env()):
        repo.git.push("origin", repo.active_branch.name)


def _write_card_file(path: Path, card: Card):
    """serialize a Card to a markdown file with frontmatter"""
    metadata = {
        "tags": card.tags,
        "created": card.created or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    post = frontmatter.Post(
        content=f"## Question\n{card.question}\n\n## Answer\n{card.answer}",
        **metadata,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter.dumps(post), encoding="utf-8")


def _parse_card_file(path: Path) -> Optional[Card]:
    """parse a markdown file into a Card. returns None if malformed."""
    try:
        post = frontmatter.load(str(path))
        content = post.content

        # split on ## Question / ## Answer headers
        q_match = re.search(r"##\s+Question\s*\n(.*?)(?=##\s+Answer|$)", content, re.DOTALL)
        a_match = re.search(r"##\s+Answer\s*\n(.*?)$", content, re.DOTALL)

        if not q_match or not a_match:
            log.warning(f"skipping malformed card: {path}")
            return None

        tags = post.metadata.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]

        return Card(
            slug=_path_to_slug(path),
            question=q_match.group(1).strip(),
            answer=a_match.group(1).strip(),
            tags=tags,
            created=str(post.metadata.get("created", "")),
            raw_path=path,
        )
    except Exception as e:
        log.error(f"failed to parse {path}: {e}")
        return None


# ── public interface ──────────────────────────────────────────────────────────

def clone_or_open_repo():
    """clone the repo if it doesn't exist locally, otherwise open it"""
    repo_path = settings.git_repo_path
    if repo_path.exists() and (repo_path / ".git").exists():
        log.info("repo already exists, pulling latest")
        repo = _get_repo()
        _configure_repo(repo)
        _pull(repo)
    else:
        log.info(f"cloning {settings.git_repo_url} → {repo_path}")
        repo_path.mkdir(parents=True, exist_ok=True)
        env = _ssh_env()
        old_env = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            repo = git.Repo.clone_from(settings.git_repo_url, repo_path)
        finally:
            for k, v in old_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        _configure_repo(repo)

    # make sure cards subdir exists
    _cards_dir().mkdir(parents=True, exist_ok=True)


def sync_pull():
    """pull latest from remote — call this on refresh"""
    repo = _get_repo()
    _pull(repo)


def list_cards() -> list[Card]:
    """read all .md files from the cards directory"""
    cards_dir = _cards_dir()
    if not cards_dir.exists():
        return []
    cards = []
    for path in sorted(cards_dir.glob("*.md")):
        card = _parse_card_file(path)
        if card:
            cards.append(card)
    return cards


def get_card(slug: str) -> Optional[Card]:
    path = _slug_to_path(slug)
    if not path.exists():
        return None
    return _parse_card_file(path)


def all_tags() -> list[str]:
    """collect all unique tags across all cards"""
    tags = set()
    for card in list_cards():
        tags.update(card.tags)
    return sorted(tags)


def create_card(question: str, answer: str, tags: list[str]) -> Card:
    """create a new card, commit, push. returns the created card."""
    repo = _get_repo()
    _pull(repo)

    slug = str(uuid.uuid4())
    path = _slug_to_path(slug)

    card = Card(slug=slug, question=question, answer=answer, tags=tags, raw_path=path)
    _write_card_file(path, card)

    repo.index.add([str(path)])
    repo.index.commit(f"add card: {slug}")
    _push(repo)

    return card


def update_card(slug: str, question: str, answer: str, tags: list[str]) -> Card:
    """update an existing card, commit, push."""
    repo = _get_repo()
    _pull(repo)

    path = _slug_to_path(slug)
    if not path.exists():
        raise FileNotFoundError(f"card not found: {slug}")

    card = Card(slug=slug, question=question, answer=answer, tags=tags, raw_path=path)
    _write_card_file(path, card)

    repo.index.add([str(path)])
    repo.index.commit(f"update card: {slug}")
    _push(repo)

    return card


def delete_card(slug: str):
    """delete a card file, commit, push."""
    repo = _get_repo()
    _pull(repo)

    path = _slug_to_path(slug)
    if not path.exists():
        raise FileNotFoundError(f"card not found: {slug}")

    repo.index.remove([str(path)], working_tree=True)
    repo.index.commit(f"delete card: {slug}")
    _push(repo)