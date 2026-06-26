import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db
from app.git_ops import clone_or_open_repo
from app.routers import cards, review

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("starting up — initializing db and git repo")
    init_db()
    clone_or_open_repo()
    yield
    log.info("shutting down")


app = FastAPI(title="flashcards", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(cards.router)
app.include_router(review.router)

# make repo_web_url available in all templates
from fastapi.templating import Jinja2Templates
from app.routers.cards import templates as cards_templates
from app.routers.review import templates as review_templates
for t in [cards_templates, review_templates]:
    t.env.globals["repo_web_url"] = settings.git_repo_web_url