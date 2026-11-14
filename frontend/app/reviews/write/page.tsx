"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthRequired } from "@/components/auth-required";
import { useAuth } from "@/components/auth-provider";
import { apiRequest } from "@/lib/auth-client";

type Review = { id: string; display_name: string; rating: number; comment: string; created_at: string };

function WriteReviewContent() {
  const { user } = useAuth();
  const [displayName, setDisplayName] = useState(user?.user_metadata?.full_name || "");
  const [rating, setRating] = useState("5");
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    void apiRequest<Review>("/api/v1/reviews/mine").then(review => {
      setDisplayName(review.display_name); setRating(String(review.rating)); setComment(review.comment);
    }).catch(() => {});
  }, []);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setMessage(""); setLoading(true);
    try {
      await apiRequest<Review>("/api/v1/reviews/mine", {
        method: "POST",
        body: JSON.stringify({ display_name: displayName, rating: Number(rating), comment }),
      });
      setMessage("Your review has been published on the public CompatFlow reviews page.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not publish your review.");
    } finally { setLoading(false); }
  }

  return <main id="main" className="page"><div className="container review-form-page">
    <header className="workspace-heading"><div><span className="eyebrow">YOUR FEEDBACK</span><h1>Write a review</h1><p>Share an honest account of your experience with CompatFlow.</p></div><Link className="button button-secondary" href="/reviews">View published reviews</Link></header>
    <section className="panel settings-panel">
      <form className="auth-form" onSubmit={submit}>
        <label htmlFor="review-display-name">Display name</label><input id="review-display-name" required minLength={2} maxLength={80} value={displayName} onChange={event => setDisplayName(event.target.value)} />
        <label htmlFor="review-rating">Star rating</label><select id="review-rating" value={rating} onChange={event => setRating(event.target.value)}><option value="5">★★★★★ — Excellent</option><option value="4">★★★★☆ — Good</option><option value="3">★★★☆☆ — Average</option><option value="2">★★☆☆☆ — Poor</option><option value="1">★☆☆☆☆ — Very poor</option></select>
        <label htmlFor="review-comment">Your review</label><textarea id="review-comment" required minLength={15} maxLength={2000} rows={7} value={comment} onChange={event => setComment(event.target.value)} placeholder="What worked well? What should we improve?" />
        <p className="settings-description">Your display name, star rating and comment will be published publicly. Do not include confidential company information or personal data.</p>
        {error && <p className="auth-error" role="alert">{error}</p>}
        {message && <p className="auth-success" role="status">{message}</p>}
        <button className="button auth-submit" disabled={loading}>{loading ? "Publishing…" : "Publish review"}</button>
      </form>
    </section>
  </div></main>;
}
export default function WriteReviewPage() { return <AuthRequired><WriteReviewContent /></AuthRequired>; }
