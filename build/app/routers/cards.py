from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import select

from app import git_ops
from app.database import get_db
from app.models import CardReview, ReviewLog

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    cards = git_ops.list_cards()
    tags = git_ops.all_tags()
    return templates.TemplateResponse(request, "index.html", {
        "cards": cards,
        "tags": tags,
        "total": len(cards),
    })


@router.post("/sync", response_class=HTMLResponse)
def sync(request: Request):
    """pull latest from remote"""
    try:
        git_ops.sync_pull()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return RedirectResponse("/", status_code=303)


@router.get("/cards/new", response_class=HTMLResponse)
def new_card_form(request: Request):
    tags = git_ops.all_tags()
    return templates.TemplateResponse(request, "card_form.html", {
        "card": None,
        "tags": tags,
        "all_tags": tags,
    })


@router.post("/cards/new", response_class=HTMLResponse)
def create_card(
    request: Request,
    question: str = Form(...),
    answer: str = Form(...),
    tags: str = Form(""),
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    try:
        card = git_ops.create_card(question=question, answer=answer, tags=tag_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return RedirectResponse(f"/cards/{card.slug}", status_code=303)


@router.get("/cards/{slug}", response_class=HTMLResponse)
def view_card(request: Request, slug: str, db: Session = Depends(get_db)):
    card = git_ops.get_card(slug)
    if not card:
        raise HTTPException(status_code=404, detail="card not found")

    import markdown as md
    review = db.get(CardReview, slug)
    logs = db.execute(
        select(ReviewLog)
        .where(ReviewLog.card_slug == slug)
        .order_by(ReviewLog.reviewed_at.desc())
        .limit(10)
    ).scalars().all()

    return templates.TemplateResponse(request, "card_detail.html", {
        "card": card,
        "review": review,
        "logs": logs,
        "question_html": md.markdown(card.question),
        "answer_html": md.markdown(card.answer),
    })


@router.get("/cards/{slug}/edit", response_class=HTMLResponse)
def edit_card_form(request: Request, slug: str):
    card = git_ops.get_card(slug)
    if not card:
        raise HTTPException(status_code=404, detail="card not found")
    all_tags = git_ops.all_tags()
    return templates.TemplateResponse(request, "card_form.html", {
        "card": card,
        "all_tags": all_tags,
    })


@router.post("/cards/{slug}/edit", response_class=HTMLResponse)
def update_card(
    request: Request,
    slug: str,
    question: str = Form(...),
    answer: str = Form(...),
    tags: str = Form(""),
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    try:
        git_ops.update_card(slug=slug, question=question, answer=answer, tags=tag_list)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="card not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return RedirectResponse(f"/cards/{slug}", status_code=303)


@router.post("/cards/{slug}/delete")
def delete_card(slug: str, db: Session = Depends(get_db)):
    try:
        git_ops.delete_card(slug)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="card not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    review = db.get(CardReview, slug)
    if review:
        db.delete(review)
        db.commit()

    return RedirectResponse("/", status_code=303)
