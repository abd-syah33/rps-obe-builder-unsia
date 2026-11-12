"use server";
import { redirect } from "next/navigation";
import { supabaseServer } from "@/lib/supabase/server";

export async function masuk(_: string | null, form: FormData): Promise<string | null> {
  const sb = await supabaseServer();
  const { error } = await sb.auth.signInWithPassword({
    email: String(form.get("email") ?? "").trim(),
    password: String(form.get("password") ?? ""),
  });
  if (error) return "Email atau password salah.";
  redirect("/");
}

export async function keluar() {
  const sb = await supabaseServer();
  await sb.auth.signOut();
  redirect("/login");
}
