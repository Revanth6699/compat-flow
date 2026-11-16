import { NextResponse } from "next/server";
export const runtime = "nodejs";
const emailPattern=/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
export async function POST(request:Request){
 try{
  const body=await request.json();
  const name=String(body.name||"").trim(),email=String(body.email||"").trim().toLowerCase(),organization=String(body.organization||"").trim(),role=String(body.role||"").trim(),message=String(body.message||"").trim(),website=String(body.website||"").trim(),intent=body.intent==="demo"?"demo":"general";
  if(website)return NextResponse.json({ok:true});
  if(!name||name.length>120||!emailPattern.test(email)||email.length>254||!organization||organization.length>160||!role||role.length>120||message.length<10||message.length>3000){
   return NextResponse.json({error:"Please complete all required fields with valid information."},{status:400});
  }
  const supabaseUrl=process.env.SUPABASE_URL,serviceKey=process.env.SUPABASE_SERVICE_ROLE_KEY;
  if(!supabaseUrl||!serviceKey)return NextResponse.json({error:"Form submissions are not configured yet. Please try again later."},{status:503});
  if(intent==="demo"){
   const apiBase=process.env.NEXT_PUBLIC_API_BASE_URL;
   if(!apiBase?.startsWith("https://"))return NextResponse.json({error:"Demo requests are not configured. Please try again later."},{status:503});
   const upstream=await fetch(`${apiBase.replace(/\\/$/,"")}/api/v1/demo-requests`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name,email,organization,role,message})});
   if(!upstream.ok)return NextResponse.json({error:"We could not save your demo request. Please try again later."},{status:upstream.status===422?400:502});
   const saved=await upstream.json().catch(()=>null);
   if(!saved?.id)return NextResponse.json({error:"The demo request was accepted by the API, but its tracking record could not be confirmed. Please contact support before retrying."},{status:502});
   // Mirror the backend request into Supabase using the backend UUID as an idempotency key.
   // Omitting status on conflict preserves any admin review already recorded in Supabase.
   const mirrored=await fetch(`${supabaseUrl.replace(/\\/$/,"")}/rest/v1/contact_requests?on_conflict=id`,{
    method:"POST",
    headers:{apikey:serviceKey,Authorization:`Bearer ${serviceKey}`,"Content-Type":"application/json",Prefer:"resolution=merge-duplicates,return=minimal"},
    body:JSON.stringify({id:saved.id,name,email,organization,role,message,intent:"demo"})
   });
   if(!mirrored.ok){
    console.error("CompatFlow demo request was saved in the backend but its Supabase mirror failed:",mirrored.status,await mirrored.text().catch(()=>""));
    return NextResponse.json({error:"Your demo request was received, but its tracking record is still syncing. Please retry in a moment; your request will not be duplicated."},{status:503});
   }
   return NextResponse.json({ok:true});
  }
  const response=await fetch(`${supabaseUrl.replace(/\\/$/,"")}/rest/v1/contact_requests`,{
   method:"POST",headers:{apikey:serviceKey,Authorization:`Bearer ${serviceKey}`,"Content-Type":"application/json",Prefer:"return=minimal"},
   body:JSON.stringify({name,email,organization,role,message,intent,status:"new"})
  });
  if(!response.ok)return NextResponse.json({error:"We could not save your message. Please try again later."},{status:502});
  const apiBase=process.env.NEXT_PUBLIC_API_BASE_URL;
  const notificationSecret=process.env.CONTACT_NOTIFICATION_SECRET;
  if(apiBase?.startsWith("https://")&&notificationSecret){
   try{
    const notification=await fetch(`${apiBase.replace(/\\/$/,"")}/api/v1/notifications/contact`,{
     method:"POST",
     headers:{"Content-Type":"application/json","X-Contact-Notification-Secret":notificationSecret},
     body:JSON.stringify({name,email,organization,role,message,intent:"general"})
    });
    if(!notification.ok){
     console.error("CompatFlow contact email notification endpoint failed:",notification.status);
    }else{
     const result=await notification.json().catch(()=>null);
     if(result?.email_sent!==true){
      console.error("CompatFlow contact email notification was not delivered:",result);
     }
    }
   }catch(error){console.error("CompatFlow contact email notification request failed:",error);}
  }else{
   console.error("CompatFlow contact email notification is not configured.");
  }
  return NextResponse.json({ok:true});
 }catch(error){
  console.error("CompatFlow contact form submission failed:",error);
  return NextResponse.json({error:"Invalid request. Please check the form and try again."},{status:400});
 }
}
