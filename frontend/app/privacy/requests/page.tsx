"use client";
import { useState } from "react";
import Link from "next/link";
const requestTypes = [["access","Access my personal data"],["correction","Correct or complete my personal data"],["erasure","Erase personal data"],["withdraw_consent","Withdraw consent"],["grievance","Raise a privacy grievance"]];
export default function DataRightsRequestPage() {
 const [form,setForm]=useState({name:"",email:"",request_type:"access",details:""});
 const [status,setStatus]=useState<"idle"|"sending"|"sent"|"error">("idle"); const [message,setMessage]=useState("");
 async function submit(event:React.FormEvent<HTMLFormElement>){
  event.preventDefault();setStatus("sending");setMessage("");
  try{
   const apiBase=(process.env.NEXT_PUBLIC_API_BASE_URL||"").replace(/\/$/,"");
   if(!apiBase.startsWith("https://"))throw new Error("The secure privacy-request endpoint is not configured.");
   const response=await fetch(`${apiBase}/api/v1/privacy/requests`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(form)});
   const payload=await response.json();if(!response.ok)throw new Error(payload.detail||"Your request could not be submitted.");
   setStatus("sent");setMessage(`Request received. Reference: ${payload.request_id}. We may contact you to verify your identity.`);
   setForm({name:"",email:"",request_type:"access",details:""});
  }catch(error){setStatus("error");setMessage(error instanceof Error?error.message:"Request failed.");}
 }
 return <main id="main" className="page"><div className="container review-form-page">
  <header className="workspace-heading"><div><span className="eyebrow">PRIVACY / YOUR RIGHTS</span><h1>Data-rights request</h1><p>Submit an access, correction, erasure, consent-withdrawal or grievance request.</p></div><Link className="button button-secondary" href="/privacy">Read Privacy Notice</Link></header>
  <section className="panel settings-panel"><form className="auth-form" onSubmit={submit}>
   <label htmlFor="rights-name">Your name</label><input id="rights-name" required minLength={2} maxLength={120} value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/>
   <label htmlFor="rights-email">Email address</label><input id="rights-email" type="email" required maxLength={254} value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/>
   <label htmlFor="rights-type">Request type</label><select id="rights-type" value={form.request_type} onChange={e=>setForm({...form,request_type:e.target.value})}>{requestTypes.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select>
   <label htmlFor="rights-details">Details (do not include passwords or sensitive documents)</label><textarea id="rights-details" required minLength={10} maxLength={3000} rows={6} value={form.details} onChange={e=>setForm({...form,details:e.target.value})}/>
   <p className="settings-description">Submitting records your request. We may verify your identity and contact you before taking action. This form does not itself delete data or guarantee that a request can be fulfilled.</p>
   {message&&<p className={status==="error"?"auth-error":"auth-success"} role="status">{message}</p>}
   <button className="button auth-submit" disabled={status==="sending"}>{status==="sending"?"Submitting…":"Submit privacy request"}</button>
  </form></section></div></main>;
}
