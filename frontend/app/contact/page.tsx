"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
function ContactForm() {
 const searchParams=useSearchParams();
 const isDemo=searchParams.get("intent")==="demo";
 const [status,setStatus]=useState<"idle"|"sending"|"success"|"error">("idle");
 const [message,setMessage]=useState("");
 const [form,setForm]=useState({name:"",email:"",organization:"",role:"",message:"",website:""});
 function update(field:keyof typeof form,value:string){setForm(current=>({...current,[field]:value}));}
 async function submit(event:React.FormEvent<HTMLFormElement>){
  event.preventDefault();if(status==="sending")return;setStatus("sending");setMessage("");
  try{
   const response=await fetch("/api/contact",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...form,intent:isDemo?"demo":"general"})});
   const data=await response.json();
   if(!response.ok)throw new Error(data.error||"We could not submit your message. Please try again.");
   setStatus("success");setMessage(isDemo?"Your demo request has been received. Access is not automatic; requests are reviewed before invitations are sent.":"Your message has been received. We will review it and get back to you.");
   setForm({name:"",email:"",organization:"",role:"",message:"",website:""});
  }catch(error){setStatus("error");setMessage(error instanceof Error?error.message:"Something went wrong. Please try again.");}
 }
 return <main id="main" className="contact-page">
  <div className="container">
   <section className="contact-hero"><span className="eyebrow">{isDemo?"REQUEST ACCESS":"GET IN TOUCH"}</span><h1>{isDemo?"Request a CompatFlow demo":"Contact Us"}</h1><p>{isDemo?"Tell us a little about your team and how you would evaluate CompatFlow. Demo access is reviewed and granted individually.":"Have a question about supplier catalog workflows or CompatFlow? Send us a message using the form below."}</p></section>
   <div className="contact-layout">
    <form className="contact-form" onSubmit={submit}>
     <div className="contact-form-grid">
      <div className="contact-field"><label htmlFor="contact-name">Name *</label><input id="contact-name" name="name" autoComplete="name" required maxLength={120} value={form.name} onChange={e=>update("name",e.target.value)} /></div>
      <div className="contact-field"><label htmlFor="contact-email">Email address *</label><input id="contact-email" name="email" type="email" autoComplete="email" required maxLength={254} value={form.email} onChange={e=>update("email",e.target.value)} /></div>
      <div className="contact-field"><label htmlFor="contact-organization">Organization *</label><input id="contact-organization" name="organization" autoComplete="organization" required maxLength={160} value={form.organization} onChange={e=>update("organization",e.target.value)} /></div>
      <div className="contact-field"><label htmlFor="contact-role">Role *</label><input id="contact-role" name="role" required maxLength={120} placeholder="e.g. Ecommerce Operations Manager" value={form.role} onChange={e=>update("role",e.target.value)} /></div>
      <div className="contact-field contact-field-full"><label htmlFor="contact-message">Message *</label><textarea id="contact-message" name="message" required minLength={10} maxLength={3000} value={form.message} onChange={e=>update("message",e.target.value)} placeholder={isDemo?"Tell us about your catalog workflow and what you would like to evaluate.":"How can we help?"} /></div>
      <div className="contact-honeypot" aria-hidden="true"><label htmlFor="contact-website">Leave this field empty</label><input id="contact-website" tabIndex={-1} autoComplete="off" value={form.website} onChange={e=>update("website",e.target.value)} /></div>
     </div>
     <div className="contact-submit-row"><button className="button" type="submit" disabled={status==="sending"}>{status==="sending"?"Submitting...":isDemo?"Submit demo request":"Send message"}</button><span className={`contact-status ${status}`} role="status">{message}</span></div>
    </form>
    <aside className="contact-aside"><h2>{isDemo?"What happens next?":"Talk to CompatFlow"}</h2><p>{isDemo?"We review each request individually. If approved, an invitation will be sent to the email address you provided. Submitting this form does not grant demo access.":"Share the context of your supplier catalog workflow and the question you are trying to solve. We will review your message and respond by email."}</p><a href={`mailto:${process.env.NEXT_PUBLIC_CONTACT_EMAIL||"sarvasettyrevanth.66@gmail.com"}`}>Email CompatFlow</a></aside>
   </div>
  </div>
 </main>;
}
export default function ContactPage(){return <Suspense fallback={<main id="main" className="contact-page"><div className="container">Loading contact form...</div></main>}><ContactForm/></Suspense>;}