import { NextResponse } from "next/server";
export const runtime = "nodejs";
const emailPattern=/^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export async function POST(request:Request){
 try{
  const body=await request.json();
  const name=String(body.name||"").trim(),email=String(body.email||"").trim().toLowerCase(),organization=String(body.organization||"").trim(),role=String(body.role||"").trim(),message=String(body.message||"").trim(),website=String(body.website||"").trim(),intent=body.intent==="demo"?"demo":"general";
  if(website)return NextResponse.json({ok:true});
  if(!name||name.length>120||!emailPattern.test(email)||email.length>254||!organization||organization.length>160||!role||role.length>120||message.length<10||message.length>3000){
   return NextResponse.json({error:"Please complete all required fields with valid information."},{status:400});
  }
  const supabaseUrl=process.env.SUPABASE_URL,serviceKey=process.env.SUPABASE_SERVICE_ROLE_KEY;
  if(!supabaseUrl||!serviceKey)return NextResponse.json({error:"Contact submissions are not configured yet. Please email CompatFlow directly."},{status:503});
  const response=await fetch(`${supabaseUrl.replace(/\/$/,"")}/rest/v1/contact_requests`,{
   method:"POST",headers:{apikey:serviceKey,Authorization:`Bearer ${serviceKey}`,"Content-Type":"application/json",Prefer:"return=minimal"},
   body:JSON.stringify({name,email,organization,role,message,intent,status:"new"})
  });
  if(!response.ok)return NextResponse.json({error:"We could not save your message. Please try again later."},{status:502});
  return NextResponse.json({ok:true});
 }catch{return NextResponse.json({error:"Invalid request. Please check the form and try again."},{status:400});}
}