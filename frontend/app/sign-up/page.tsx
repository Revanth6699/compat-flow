"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiRequest, signUp } from "@/lib/auth-client";

const selectablePlans = new Set(["starter", "growth", "business"]);

function SignUpForm() {
  const search = useSearchParams();
  const router = useRouter();
  const requestedPlan = search.get("plan")?.toLowerCase() || "";
  const selectedPlan = selectablePlans.has(requestedPlan) ? requestedPlan : "";
  const nextParam = search.get("next");
  const next = nextParam && nextParam.startsWith("/") && !nextParam.startsWith("//")
    ? nextParam
    : selectedPlan ? `/billing?plan=${selectedPlan}` : "/workspace";
  const isInvitationFlow = next.split("?")[0] === "/invitations/accept";
  const [fullName,setFullName] = useState(""); const [organizationName,setOrganizationName] = useState(""); const [jobTitle,setJobTitle] = useState(""); const [phone,setPhone] = useState(""); const [companyWebsite,setCompanyWebsite] = useState(""); const [industry,setIndustry] = useState(""); const [teamSize,setTeamSize] = useState(""); const [email,setEmail] = useState(""); const [password,setPassword] = useState(""); const [confirm,setConfirm] = useState("");
  const [message,setMessage] = useState(""); const [error,setError] = useState(""); const [busy,setBusy] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setMessage("");
    if(password.length<10){setError("Use a password with at least 10 characters.");return;}
    if(password!==confirm){setError("The passwords do not match.");return;}
    if(!isInvitationFlow && organizationName.trim().length<2){setError("Enter an organization name with at least 2 characters.");return;}
    if(!isInvitationFlow && jobTitle.trim().length<2){setError("Enter your job title.");return;}
    if(!isInvitationFlow && !industry){setError("Select your industry.");return;}
    if(!isInvitationFlow && !teamSize){setError("Select your team size.");return;}
    if(phone && !/^\+?[0-9() .-]{7,20}$/.test(phone)){setError("Enter a valid phone number, including country code if applicable.");return;}
    if(companyWebsite && !/^https?:\/\//i.test(companyWebsite)){setError("Enter a company website beginning with https:// or http://.");return;}
    setBusy(true);
    try {
      const result=await signUp(email,password,fullName,isInvitationFlow ? "" : organizationName,next,{job_title:jobTitle.trim(),phone:phone.trim(),company_website:companyWebsite.trim(),industry,team_size:teamSize});
      if (result.access_token) {
        if (isInvitationFlow) {
          router.replace(next);
          return;
        }
        await apiRequest("/api/v1/auth/organization", { method: "POST", body: JSON.stringify({ name: organizationName.trim() }) });
        router.replace(next);
        return;
      }
      setMessage(isInvitationFlow
        ? "Account created. Check your email, confirm your address, and then accept the organization invitation."
        : `Account created. Check your email and confirm your address. Your ${selectedPlan ? selectedPlan.charAt(0).toUpperCase()+selectedPlan.slice(1)+" plan selection" : "workspace setup"} will continue automatically after confirmation.`);
    } catch(e) { setError(e instanceof Error?e.message:"Could not create your account."); }
    finally { setBusy(false); }
  }
  return <main id="main" className="auth-shell"><section className="auth-card">
    <span className="eyebrow">GET STARTED</span><h1>{isInvitationFlow ? "Create your invited account" : "Create your account"}</h1><p className="auth-intro">{isInvitationFlow ? "Create an account using the email address that received the invitation. After confirming your email, you can join the inviting organization." : <>Create your account and company workspace. {selectedPlan ? `Your ${selectedPlan.charAt(0).toUpperCase()+selectedPlan.slice(1)} plan choice will be kept through registration.` : "You will be the organization owner and can invite employees after setup."} Your email must be verified before workspace access is activated.</>}</p>
    <form className="auth-form" onSubmit={submit}>
      <label htmlFor="signup-name">Full name</label><input id="signup-name" type="text" autoComplete="name" minLength={2} maxLength={100} required value={fullName} onChange={e=>setFullName(e.target.value)} />
      {!isInvitationFlow && <><label htmlFor="signup-organization">Organization name</label><input id="signup-organization" type="text" minLength={2} maxLength={160} required value={organizationName} onChange={e=>setOrganizationName(e.target.value)} />
      <label htmlFor="signup-job-title">Your job title</label><input id="signup-job-title" type="text" minLength={2} maxLength={100} required value={jobTitle} onChange={e=>setJobTitle(e.target.value)} placeholder="e.g. Ecommerce Operations Manager" />
      <label htmlFor="signup-phone">Phone number</label><input id="signup-phone" type="tel" autoComplete="tel" maxLength={20} pattern="^\+?[0-9() .-]{7,20}$" value={phone} onChange={e=>setPhone(e.target.value)} placeholder="+91 98765 43210" />
      <label htmlFor="signup-website">Company website</label><input id="signup-website" type="url" maxLength={255} value={companyWebsite} onChange={e=>setCompanyWebsite(e.target.value)} placeholder="https://example.com" />
      <label htmlFor="signup-industry">Industry</label><select id="signup-industry" required value={industry} onChange={e=>setIndustry(e.target.value)}><option value="">Select industry</option><option value="ecommerce">Ecommerce / D2C</option><option value="retail">Retail</option><option value="automotive">Automotive / Parts</option><option value="manufacturing">Manufacturing</option><option value="distribution">Wholesale / Distribution</option><option value="technology">Technology / Software</option><option value="other">Other</option></select>
      <label htmlFor="signup-team-size">Team size</label><select id="signup-team-size" required value={teamSize} onChange={e=>setTeamSize(e.target.value)}><option value="">Select team size</option><option value="1">Just me</option><option value="2-5">2–5</option><option value="6-20">6–20</option><option value="21-50">21–50</option><option value="51-200">51–200</option><option value="201+">201+</option></select>
      <label>Account role</label><p className="auth-intro">Company Owner — the first account manages the organization, billing and employee access.</p></>}
      <label htmlFor="signup-email">Work email</label><input id="signup-email" type="email" autoComplete="email" required value={email} onChange={e=>setEmail(e.target.value)} />
      <label htmlFor="signup-password">Password</label><input id="signup-password" type="password" autoComplete="new-password" minLength={10} required value={password} onChange={e=>setPassword(e.target.value)} />
      <label htmlFor="signup-confirm">Confirm password</label><input id="signup-confirm" type="password" autoComplete="new-password" minLength={10} required value={confirm} onChange={e=>setConfirm(e.target.value)} />
      {error && <p className="auth-error" role="alert">{error}</p>}{message && <p className="auth-success" role="status">{message}</p>}
      <button className="button auth-submit" disabled={busy}>{busy?"Creating account…":"Create account"}</button>
    </form>
    <p className="auth-switch">Already registered? <Link href={`/sign-in?next=${encodeURIComponent(next)}`}>Sign in</Link></p>
  </section></main>;
}

export default function SignUpPage() { return <Suspense fallback={<main id="main" className="auth-shell">Loading…</main>}><SignUpForm /></Suspense>; }
