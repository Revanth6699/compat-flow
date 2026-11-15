"use client";

import Link from "next/link";
import { useSearchParams,useRouter } from "next/navigation";
import { Suspense,useState } from "react";
import { apiRequest } from "@/lib/auth-client";
import { useAuth } from "@/components/auth-provider";

function AcceptInvitation(){
 const params=useSearchParams();const router=useRouter();const {user,loading}=useAuth();const token=params.get("token")||"";const [error,setError]=useState("");const [busy,setBusy]=useState(false);const [done,setDone]=useState(false);
 async function accept(){setBusy(true);setError("");try{await apiRequest("/api/v1/invitations/accept",{method:"POST",body:JSON.stringify({token})});setDone(true);router.replace("/workspace");}catch(e){setError(e instanceof Error?e.message:"Could not accept this invitation.");}finally{setBusy(false);}}
 if(loading)return <main id="main" className="auth-shell"><section className="auth-card">Checking your session…</section></main>;
 return <main id="main" className="auth-shell"><section className="auth-card"><span className="eyebrow">ORGANIZATION INVITATION</span><h1>Join your organization</h1>{done?<p className="auth-success">Invitation accepted. Opening your workspace…</p>:!token?<p className="auth-error">The invitation link is missing its token.</p>:!user?<><p className="auth-intro">Sign in or create an account using the email address that received this invitation. You must confirm that email before accepting.</p><Link className="button auth-submit" href={`/sign-in?next=${encodeURIComponent(`/invitations/accept?token=${token}`)}`}>Sign in to continue</Link><p className="auth-switch">New user? <Link href={`/sign-up?next=${encodeURIComponent(`/invitations/accept?token=${token}`)}`}>Create account</Link></p></>:<><p className="auth-intro">Signed in as {user.email}. Accepting this invitation links your account to the inviting organization.</p>{error&&<p className="auth-error" role="alert">{error}</p>}<button className="button auth-submit" disabled={busy} onClick={accept}>{busy?"Accepting…":"Accept invitation"}</button></>}</section></main>;
}
export default function AcceptInvitationPage(){return <Suspense fallback={<main id="main" className="auth-shell">Loading invitation…</main>}><AcceptInvitation/></Suspense>;}
