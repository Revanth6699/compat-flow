"use client";

import Link from "next/link";
import { useEffect,useState } from "react";
import { AuthRequired } from "@/components/auth-required";
import { useAuth } from "@/components/auth-provider";
import { apiRequest } from "@/lib/auth-client";

type Profile={id:string;organization_id:string;email:string;role:string;is_active:boolean;account_type:string;plan_code:string|null;subscription_status:string|null};
function WorkspaceContent(){
 const {user,signOut}=useAuth();const [profile,setProfile]=useState<Profile|null>(null);const [error,setError]=useState("");const [loading,setLoading]=useState(true);
 useEffect(()=>{let active=true;apiRequest<Profile>("/api/v1/auth/me").then(data=>{if(active)setProfile(data);}).catch(e=>{if(active)setError(e instanceof Error?e.message:"Could not load your workspace profile.");}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;}},[]);
 return <main id="main" className="page"><div className="container"><div className="workspace-heading"><div><span className="eyebrow">YOUR ACCOUNT</span><h1>Workspace access</h1><p>Signed in as {user?.email||"your account"}.</p></div><div className="workspace-actions"><Link className="button button-secondary" href="/settings">Profile settings</Link><button className="button button-secondary" onClick={()=>void signOut()}>Sign out</button></div></div>{loading?<p>Loading your organization profile…</p>:error?<div className="notice"><strong>Account authenticated, workspace not linked.</strong><p>{error}</p><p>If you are the first organization owner, an operator must provision your account. If you were invited, accept the invitation using its link.</p></div>:profile?<section className="panel workspace-profile"><h2>Organization profile</h2><dl><div><dt>Email</dt><dd>{profile.email}</dd></div><div><dt>Role</dt><dd>{profile.role}</dd></div><div><dt>Organization ID</dt><dd>{profile.organization_id}</dd></div><div><dt>Account status</dt><dd>{profile.is_active?"Active":"Inactive"}</dd></div><div><dt>Account type</dt><dd>{profile.account_type}</dd></div><div><dt>Subscription plan</dt><dd>{profile.plan_code ? profile.plan_code.charAt(0).toUpperCase()+profile.plan_code.slice(1) : "No active subscription"}</dd></div><div><dt>Subscription status</dt><dd>{profile.subscription_status || "No active subscription"}</dd></div></dl><Link className="button" href="/catalog/import">Open catalog demo</Link></section>:null}</div></main>;
}
export default function WorkspacePage(){return <AuthRequired><WorkspaceContent/></AuthRequired>;}
