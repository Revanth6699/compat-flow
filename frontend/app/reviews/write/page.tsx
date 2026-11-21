"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthRequired } from "@/components/auth-required";
import { useAuth } from "@/components/auth-provider";
import { apiRequest, ApiRequestError } from "@/lib/auth-client";
import { BrandedLoading } from "@/components/branded-loading";

type Review = { id: string; display_name: string; rating: number; comment: string; created_at: string };

function WriteReviewContent() {
  const { user } = useAuth();
  const [displayName, setDisplayName] = useState(user?.user_metadata?.full_name || "");
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);
  const [checkingReview, setCheckingReview] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [hasExistingReview, setHasExistingReview] = useState(false);

  useEffect(() => {
    let active = true;
    void apiRequest<Review>("/api/v1/reviews/mine").then(review => {
      if (!active) return;
      setHasExistingReview(true);
      setDisplayName(review.display_name);
      setRating(review.rating);
      setComment(review.comment);
      setMessage("You already have a review. Submitting this form will update it.");
    }).catch(cause => {
      if (active && !(cause instanceof ApiRequestError && cause.status === 404)) {
        setError(cause instanceof Error ? cause.message : "Could not load your existing review.");
      }
    }).finally(() => { if (active) setCheckingReview(false); });
    return () => { active = false; };
  }, []);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (rating < 1 || rating > 5) {
      setError("Choose a star rating before publishing your review.");
      return;
    }
    setLoading(true);
    try {
      await apiRequest<Review>("/api/v1/reviews/mine", {
        method: "POST",
        body: JSON.stringify({ display_name: displayName, rating, comment }),
      });
      setHasExistingReview(true);
      setRating(0);
      setComment("");
      setMessage(hasExistingReview
        ? "Review sent — your existing review has been updated. The form is ready for another edit."
        : "Review sent successfully. The form is ready. You can update this review any time from Profile settings → Your reviews.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not publish your review.");
    } finally { setLoading(false); }
  }

  return <main id="main" className="page"><div className="container review-form-page">
    <header className="workspace-heading"><div><span className="eyebrow">YOUR FEEDBACK</span><h1>Write a review</h1><p>Share an honest account of your experience with CompatFlow.</p></div><Link className="button button-secondary" href="/reviews">View published reviews</Link></header>
    <section className="panel settings-panel review-compose-panel">
      {checkingReview ? <BrandedLoading label="Checking your review" detail="Loading your existing feedback before opening the form." /> : <form className="auth-form" onSubmit={submit}>
        <label htmlFor="review-display-name">Display name</label>
        <input id="review-display-name" required minLength={2} maxLength={80} value={displayName} onChange={event => setDisplayName(event.target.value)} />
        <fieldset className="review-star-field">
          <legend>Star rating</legend>
          <div className="review-star-picker" role="group" aria-label="Choose a rating from one to five stars">
            {[1, 2, 3, 4, 5].map(value => (
              <button key={value} type="button" className={value <= rating ? "review-star selected" : "review-star"} aria-label={`${value} ${value === 1 ? "star" : "stars"}`} aria-pressed={rating === value} onClick={() => { setRating(value); setError(""); }}>
                {value <= rating ? "★" : "☆"}
              </button>
            ))}
          </div>
          <span className="review-rating-hint">{rating ? `${rating} out of 5 stars selected` : "Select a star to set your rating"}</span>
        </fieldset>
        <label htmlFor="review-comment">Your review</label>
        <textarea id="review-comment" required minLength={15} maxLength={2000} rows={7} value={comment} onChange={event => setComment(event.target.value)} placeholder="What worked well? What should we improve?" />
        <p className="settings-description">Your display name, star rating and comment will be published publicly. Do not include confidential company information or personal data.</p>
        {error && <p className="auth-error" role="alert">{error}</p>}
        {message && <p className="auth-success" role="status">{message}</p>}
        <button className="button auth-submit" disabled={loading || rating === 0}>{loading ? "Publishing…" : hasExistingReview ? "Update review" : "Publish review"}</button>
      </form>}
    </section>
  </div></main>;
}
export default function WriteReviewPage() { return <AuthRequired><WriteReviewContent /></AuthRequired>; }
