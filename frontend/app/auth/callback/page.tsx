"use client";

import Link from "next/link";
import { useEffect,useState } from "react";
import { useRouter } from "next/navigation";
import { setSessionFromCallback } from "@/lib/auth-client";

export default function AuthCallbackPage(){
 const router=useRouter();const [error,setError]=useState("");
 useEffect(()=>{
  const hash=new URLSearchParams(window.location.hash.replace(/^#/,""));
  const access_token=hash.get("access_token");const refresh_token=hash.get("refresh_token");const expires_in=Number(hash.get("expires_in")||3600);
  if(access_token&&refresh_token){
   const userId=hash.get("user_id");
   fetch(`${process.env.NEXT_PUBLIC_SUPABASE_URL}/auth/v1/user`,{headers:{apikey:process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY||"",Authorization:`Bearer ${access_token}`}})
    .then(r=>{if(!r.ok)throw new Error("The confirmation link is invalid or expired.");return r.json();})
    .then(user=>{setSessionFromCallback({access_token,refresh_token,expires_at:Date.now()/1000+expires_in,user:{id:user.id||userId||"",email:user.email}});router.replace("/workspace");})
    .catch(e=>setError(e instanceof Error?e.message:"Could not verify your account."));
  }else{
   const params=new URLSearchParams(window.location.search);const code=params.get("code");
   if(code)setError("This confirmation link uses a code-based flow that is not supported by this build. Check Supabase email template settings and use the default confirmation link flow.");
   else setError("The confirmation link is missing or expired. Request a new confirmation email.");
  }
 },[router]);
 return <main id="main" className="auth-shell"><section className="auth-card"><span className="eyebrow">EMAIL CONFIRMATION</span><h1>Confirming your account</h1>{error?<><p className="auth-error" role="alert">{error}</p><Link href="/sign-in">Return to sign in</Link></>:<p className="auth-intro">Verifying your email confirmation. This may take a moment…</p>}</section></main>;
}
