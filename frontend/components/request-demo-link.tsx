"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth-provider";
import { apiRequest } from "@/lib/auth-client";

/** Shows a re-request link only when a signed-in user's previous demo request was revoked or rejected. */
export function RequestDemoLink({ className = "" }: { className?: string }) {
  const { user } = useAuth();
  const [eligible, setEligible] = useState(false);

  useEffect(() => {
    let active = true;
    setEligible(false);
    if (!user) return () => { active = false; };
    apiRequest<{ status?: string }>("/api/v1/demo-requests/mine")
      .then((request) => {
        if (active) setEligible(request.status === "revoked" || request.status === "rejected");
      })
      .catch(() => {
        if (active) setEligible(false);
      });
    return () => { active = false; };
  }, [user?.id]);

  if (!user || !eligible) return null;
  return <Link className={className} href="/contact?intent=demo">Request demo access</Link>;
}
