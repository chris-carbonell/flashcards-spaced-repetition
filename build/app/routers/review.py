"""
handles the study/review flow:
  GET  /review          → tag selection page
  GET  /review/session  → start a session for a tag (picks due cards)
  POST /review/{slug}   → submit a rating, advance SM-2 state
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import markdown as md

from app import git_ops
from app.database import get_db
from app.models import CardReview, ReviewLog
from app.sm2 import SM2State, apply_sm2

router = APIRouter(prefix="/review")
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
def review_home(request: Request, db: Session = Depends(get_db)):
    """tag selection — show tags with due card counts"""
    tags = git_ops.all_tags()
    all_cards = git_ops.list_cards()
    now = datetime.now(timezone.utc)

    tag_due_counts = {}
    for tag in tags:
        tag_cards = [c for c in all_cards if tag in c.tags]
        due = 0
        for card in tag_cards:
            review = db.get(CardReview, card.slug)
            if review is None or review.next_review_at <= now:
                due += 1
        tag_due_counts[tag] = {"total": len(tag_cards), "due": due}

    return templates.TemplateResponse(request, "review_home.html", {
        "tag_due_counts": tag_due_counts,
    })


@router.get("/session", response_class=HTMLResponse)
def start_session(
    request: Request,
    tag: str = Query(...),
    db: Session = Depends(get_db),
):
    """pick the next due card for this tag and redirect to it"""
    card = _next_due_card(tag, db)
    if not card:
        return templates.TemplateResponse(request, "review_done.html", {"tag": tag})
    return RedirectResponse(f"/review/{card.slug}?tag={tag}", status_code=303)


@router.get("/done", response_class=HTMLResponse)
def review_done(request: Request, tag: str = Query(...)):
    return templates.TemplateResponse(request, "review_done.html", {"tag": tag})


@router.get("/{slug}", response_class=HTMLResponse)
def review_card(
    request: Request,
    slug: str,
    tag: str = Query(...),
    db: Session = Depends(get_db),
):
    card = git_ops.get_card(slug)
    if not card:
        raise HTTPException(status_code=404, detail="card not found")

    review = db.get(CardReview, slug)
    all_cards = git_ops.list_cards()
    tag_cards = [c for c in all_cards if tag in c.tags]
    now = datetime.now(timezone.utc)
    due_count = sum(
        1 for c in tag_cards
        if (r := db.get(CardReview, c.slug)) is None or r.next_review_at <= now
    )

    return templates.TemplateResponse(request, "review_card.html", {
        "card": card,
        "tag": tag,
        "review": review,
        "due_count": due_count,
        "question_html": md.markdown(card.question),
        "answer_html": md.markdown(card.answer),
    })


@router.post("/{slug}", response_class=HTMLResponse)
def submit_review(
    request: Request,
    slug: str,
    tag: str = Form(...),
    rating: int = Form(...),
    response_seconds: int = Form(None),
    db: Session = Depends(get_db),
):
    if not 0 <= rating <= 5:
        raise HTTPException(status_code=422, detail="rating must be 0-5")

    review = db.get(CardReview, slug)
    state = SM2State(
        ease_factor=review.ease_factor,
        interval_days=review.interval_days,
        repetitions=review.repetitions,
    ) if review else SM2State()

    result = apply_sm2(state, rating)
    now = datetime.now(timezone.utc)

    if review is None:
        review = CardReview(card_slug=slug)
        db.add(review)

    review.ease_factor = result.ease_factor
    review.interval_days = result.interval_days
    review.repetitions = result.repetitions
    review.next_review_at = result.next_review_at
    review.last_reviewed_at = now

    db.add(ReviewLog(
        card_slug=slug,
        rating=rating,
        ease_factor_after=result.ease_factor,
        interval_days_after=result.interval_days,
        reviewed_at=now,
        response_seconds=response_seconds,
    ))
    db.commit()

    next_card = _next_due_card(tag, db, exclude_slug=slug)
    if next_card:
        return RedirectResponse(f"/review/{next_card.slug}?tag={tag}", status_code=303)
    return RedirectResponse(f"/review/done?tag={tag}", status_code=303)


def _next_due_card(tag: str, db: Session, exclude_slug: str = None):
    """pick the highest-priority due card for a tag.

    priority: cards never reviewed first, then by next_review_at asc.
    """
    now = datetime.now(timezone.utc)
    tag_cards = [c for c in git_ops.list_cards() if tag in c.tags]
    if exclude_slug:
        tag_cards = [c for c in tag_cards if c.slug != exclude_slug]

    never_reviewed, due = [], []
    for card in tag_cards:
        review = db.get(CardReview, card.slug)
        if review is None:
            never_reviewed.append(card)
        elif review.next_review_at <= now:
            due.append((review.next_review_at, card))

    if never_reviewed:
        return never_reviewed[0]
    if due:
        return min(due, key=lambda x: x[0])[1]
    return None
