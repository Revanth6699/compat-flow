from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user
from app.core.database import get_db
from app.models import Review

router = APIRouter(prefix="/reviews", tags=["reviews"])


class ReviewCreateRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=80)
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=15, max_length=2000)

    @field_validator("display_name", "comment")
    @classmethod
    def trim_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("This field cannot be blank.")
        return normalized


class ReviewResponse(BaseModel):
    id: UUID
    display_name: str
    rating: int
    comment: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("/mine", response_model=ReviewResponse)\ndef get_my_review(\n    current: AuthenticatedUser = Depends(get_current_user),\n    db: Session = Depends(get_db),\n):\n    review = db.scalar(select(Review).where(Review.user_id == current.profile.id))\n    if review is None:\n        raise HTTPException(status_code=404, detail="You have not submitted a review yet.")\n    return review\n\n\n@router.get("", response_model=list[ReviewResponse])
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
