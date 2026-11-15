"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/auth-provider";

export function AuthRequired({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  useEffect(() => { if (!loading && !user) router.replace("/sign-in"); }, [loading, user, router]);
  if (loading) return <main id="main" className="auth-shell"><div className="auth-card"><p>Checking your session…</p></div></main>;
  if (!user) return <main id="main" className="auth-shell"><div className="auth-card"><p>Redirecting to sign in…</p><Link href="/sign-in">Continue</Link></div></main>;
  return <>{children}</>;
}
