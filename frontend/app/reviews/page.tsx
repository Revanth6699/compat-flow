"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth-provider";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "").replace(/\/$/, "");
type Review = { id: string; display_name: string; rating: number; comment: string; created_at: string };
type ReviewReply = { id: string; review_id: string; display_name: string; comment: string; created_at: string };

export default function ReviewsPage() {
  const { user } = useAuth();
  const [reviews, setReviews] = useState<Review[]>([]);
  const [replies, setReplies] = useState<Record<string, ReviewReply[]>>({});
  const [replyNames, setReplyNames] = useState<Record<string, string>>({});
  const [replyDrafts, setReplyDrafts] = useState<Record<string, string>>({});
  const [sending, setSending] = useState<string | null>(null);
  const [replyErrors, setReplyErrors] = useState<Record<string, string>>({});
  const [replyMessages, setReplyMessages] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetch(`${API_BASE}/api/v1/reviews`)
      .then(async response => {
        const data = await response.json();
        if (!response.ok) throw new Error("Customer reviews are temporarily unavailable.");
        if (!active) return;
        const published = data as Review[];
        setReviews(published);
        const replyResults = await Promise.all(published.map(async review => {
          const response = await fetch(`${API_BASE}/api/v1/reviews/${review.id}/replies`);
          if (!response.ok) return [review.id, []] as const;
          return [review.id, await response.json() as ReviewReply[]] as const;
        }));
        if (active) setReplies(Object.fromEntries(replyResults));
      })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : "Could not load reviews."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  async function submitReply(reviewId: string) {
    const displayName = (replyNames[reviewId] || user?.user_metadata?.full_name || "").trim();
    const comment = (replyDrafts[reviewId] || "").trim();
    setReplyErrors(current => ({ ...current, [reviewId]: "" }));
    setReplyMessages(current => ({ ...current, [reviewId]: "" }));
    if (displayName.length < 2 || comment.length < 2) {
      setReplyErrors(current => ({ ...current, [reviewId]: "Enter your name and a reply of at least 2 characters." }));
      return;
    }
    setSending(reviewId);
    try {
      const response = await fetch(`${API_BASE}/api/v1/reviews/${reviewId}/replies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: displayName, comment }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not send your reply.");
      setReplies(current => ({ ...current, [reviewId]: [...(current[reviewId] || []), data as ReviewReply] }));
      setReplyDrafts(current => ({ ...current, [reviewId]: "" }));
      setReplyMessages(current => ({ ...current, [reviewId]: "Reply posted." }));
    } catch (cause) {
      setReplyErrors(current => ({ ...current, [reviewId]: cause instanceof Error ? cause.message : "Could not send your reply." }));
    } finally {
      setSending(null);
    }
  }

  const average = reviews.length ? reviews.reduce((sum, review) => sum + review.rating, 0) / reviews.length : 0;
  return <main id="main" className="page"><div className="container reviews-page">
    <header className="reviews-heading">
      <span className="eyebrow">CUSTOMER FEEDBACK</span>
      <h1>Reviews from CompatFlow users</h1>
      <p>Read feedback shared by people using CompatFlow for their catalog and data workflows. Anyone can join the conversation.</p>
      {user && <Link className="button button-secondary" href="/settings#your-reviews">Manage your review</Link>}
      {!user && <Link className="button button-secondary" href="/sign-in">Sign in to write a review</Link>}
    </header>
    {loading && <p>Loading customer reviews and replies…</p>}
    {error && <p className="auth-error" role="alert">{error}</p>}
    {!loading && !error && reviews.length > 0 && <div className="reviews-summary"><strong>{average.toFixed(1)} / 5</strong><span aria-label={`${average.toFixed(1)} out of 5 stars`} className="review-stars">{"★".repeat(Math.round(average))}{"☆".repeat(5-Math.round(average))}</span><span>{reviews.length} published {reviews.length === 1 ? "review" : "reviews"}</span></div>}
    {!loading && !error && reviews.length === 0 && <section className="panel review-empty"><h2>No reviews published yet</h2><p>Customer feedback will appear here after users share their experience.</p></section>}
    <section className="reviews-grid">{reviews.map(review => <article className="panel review-card" key={review.id}>
      <div className="review-card-top"><strong>{review.display_name}</strong><time dateTime={review.created_at}>{new Date(review.created_at).toLocaleDateString()}</time></div>
      <div className="review-stars" aria-label={`${review.rating} out of 5 stars`}>{"★".repeat(review.rating)}{"☆".repeat(5-review.rating)}</div>
      <p>{review.comment}</p>
      <div className="review-replies">
        <h3>Replies ({(replies[review.id] || []).length})</h3>
        {(replies[review.id] || []).map(reply => <div className="review-reply" key={reply.id}>
          <div className="review-reply-meta"><strong>{reply.display_name}</strong><time dateTime={reply.created_at}>{new Date(reply.created_at).toLocaleString()}</time></div>
          <p>{reply.comment}</p>
        </div>)}
        <div className="review-reply-form">
          <label htmlFor={`reply-name-${review.id}`}>Your name</label>
          <input id={`reply-name-${review.id}`} maxLength={80} minLength={2} value={replyNames[review.id] ?? user?.user_metadata?.full_name ?? ""} onChange={event => setReplyNames(current => ({ ...current, [review.id]: event.target.value }))} placeholder="Display name" />
          <label htmlFor={`reply-text-${review.id}`}>Add a reply</label>
          <textarea id={`reply-text-${review.id}`} maxLength={2000} minLength={2} rows={3} value={replyDrafts[review.id] || ""} onChange={event => setReplyDrafts(current => ({ ...current, [review.id]: event.target.value }))} placeholder="Write a respectful reply…" />
          {replyErrors[review.id] && <p className="auth-error" role="alert">{replyErrors[review.id]}</p>}
          {replyMessages[review.id] && <p className="auth-success" role="status">{replyMessages[review.id]}</p>}
          <button className="button button-secondary" type="button" disabled={sending === review.id} onClick={() => void submitReply(review.id)}>{sending === review.id ? "Posting…" : "Post reply"}</button>
        </div>
      </div>
    </article>)}</section>
  </div></main>;
}
