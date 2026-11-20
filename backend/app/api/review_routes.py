from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.database import get_db
from app.models import Review, ReviewReply

router = APIRouter(prefix="/reviews", tags=["reviews"])


def clean_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("This field cannot be blank.")
    return normalized


class ReviewCreateRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=80)
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=15, max_length=2000)

    _trim_display_name = field_validator("display_name")(clean_text)
    _trim_comment = field_validator("comment")(clean_text)


class ReviewReplyCreateRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=80)
    comment: str = Field(min_length=2, max_length=2000)

    _trim_display_name = field_validator("display_name")(clean_text)
    _trim_comment = field_validator("comment")(clean_text)


class ReviewResponse(BaseModel):
    id: UUID
    display_name: str
    rating: int
    comment: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewReplyResponse(BaseModel):
    id: UUID
    review_id: UUID
    display_name: str
    comment: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("/mine", response_model=ReviewResponse)
def get_my_review(
    current: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review = db.scalar(select(Review).where(Review.user_id == current.profile.id))
    if review is None:
        raise HTTPException(status_code=404, detail="You have not submitted a review yet.")
    return review


@router.get("", response_model=list[ReviewResponse])
def list_published_reviews(db: Session = Depends(get_db)):
    return list(
        db.scalars(
            select(Review)
            .where(Review.is_published.is_(True))
            .order_by(Review.created_at.desc())
            .limit(100)
        ).all()
    )


@router.post("/mine", response_model=ReviewResponse)
def submit_review(
    payload: ReviewCreateRequest,
    current: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review = db.scalar(select(Review).where(Review.user_id == current.profile.id).with_for_update())
    if review is None:
        review = Review(
            id=uuid4(),
            organization_id=current.profile.organization_id,
            user_id=current.profile.id,
            display_name=payload.display_name,
            rating=payload.rating,
            comment=payload.comment,
            is_published=True,
        )
        db.add(review)
    else:
        review.display_name = payload.display_name
        review.rating = payload.rating
        review.comment = payload.comment
        review.is_published = True
    db.commit()
    db.refresh(review)
    return review


@router.delete("/mine")
def delete_my_review(
    current: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review = db.scalar(select(Review).where(Review.user_id == current.profile.id).with_for_update())
    if review is None:
        raise HTTPException(status_code=404, detail="You have not submitted a review yet.")
    db.delete(review)
    db.commit()
    return {"deleted": True}


@router.get("/{review_id}/replies", response_model=list[ReviewReplyResponse])
def list_review_replies(review_id: UUID, db: Session = Depends(get_db)):
    review = db.scalar(
        select(Review).where(Review.id == review_id, Review.is_published.is_(True))
    )
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found.")
    return list(
        db.scalars(
            select(ReviewReply)
            .where(ReviewReply.review_id == review_id)
            .order_by(ReviewReply.created_at.asc())
            .limit(200)
        ).all()
    )


@router.post("/{review_id}/replies", response_model=ReviewReplyResponse, status_code=201)
def create_review_reply(
    review_id: UUID,
    payload: ReviewReplyCreateRequest,
    db: Session = Depends(get_db),
):
    review = db.scalar(
        select(Review).where(Review.id == review_id, Review.is_published.is_(True))
    )
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found.")
    reply = ReviewReply(
        id=uuid4(),
        review_id=review_id,
        display_name=payload.display_name,
        comment=payload.comment,
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return reply
