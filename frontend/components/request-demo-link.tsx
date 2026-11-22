"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth-provider";
import { apiRequest } from "@/lib/auth-client";

/** Shows a re-request link only when a signed-in user's previous demo request was revoked or rejected. */
export function RequestDemoLink({ className = "" }: { className?: string }) {
  const { user } = useAuth();
  const [eligibleUserId, setEligibleUserId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!user) return () => { active = false; };

    apiRequest<{ status?: string }>("/api/v1/demo-requests/mine")
      .then((request) => {
        if (active) {
          setEligibleUserId(
            request.status === "revoked" || request.status === "rejected" ? user.id : null,
          );
        }
      })
      .catch(() => {
        if (active) setEligibleUserId(null);
      });

    return () => { active = false; };
  }, [user]);

  if (!user || eligibleUserId !== user.id) return null;
  return <Link className={className} href="/contact?intent=demo">Request demo access</Link>;
}
