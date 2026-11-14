"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth-provider";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "";
type Review = { id: string; display_name: string; rating: number; comment: string; created_at: string };

export default function ReviewsPage() {
  const { user } = useAuth();
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetch(`${API_BASE.replace(/\\/$/, "")}/api/v1/reviews`)
      .then(async response => {
        const data = await response.json();
        if (!response.ok) throw new Error("Customer reviews are temporarily unavailable.");
        if (active) setReviews(data as Review[]);
      })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : "Could not load reviews."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const average = reviews.length ? reviews.reduce((sum, review) => sum + review.rating, 0) / reviews.length : 0;
  return <main id="main" className="page"><div className="container reviews-page">
    <header className="reviews-heading"><span className="eyebrow">CUSTOMER FEEDBACK</span><h1>Reviews from CompatFlow users</h1><p>Read feedback shared by people using CompatFlow for their catalog and data workflows.</p>
      {user && <Link className="button" href="/reviews/write">Write a review</Link>}
    </header>
    {loading && <p>Loading customer reviews…</p>}
    {error && <p className="auth-error" role="alert">{error}</p>}
    {!loading && !error && reviews.length > 0 && <div className="reviews-summary"><strong>{average.toFixed(1)} / 5</strong><span aria-label={`${average.toFixed(1)} out of 5 stars`} className="review-stars">{"★".repeat(Math.round(average))}{"☆".repeat(5-Math.round(average))}</span><span>{reviews.length} published {reviews.length === 1 ? "review" : "reviews"}</span></div>}
    {!loading && !error && reviews.length === 0 && <section className="panel review-empty"><h2>No reviews published yet</h2><p>Customer feedback will appear here after users share their experience.</p>{user && <Link className="button button-secondary" href="/reviews/write">Be the first to review</Link>}</section>}
    <section className="reviews-grid">{reviews.map(review => <article className="panel review-card" key={review.id}>
      <div className="review-card-top"><strong>{review.display_name}</strong><time dateTime={review.created_at}>{new Date(review.created_at).toLocaleDateString()}</time></div>
      <div className="review-stars" aria-label={`${review.rating} out of 5 stars`}>{"★".repeat(review.rating)}{"☆".repeat(5-review.rating)}</div>
      <p>{review.comment}</p>
    </article>)}</section>
  </div></main>;
}
