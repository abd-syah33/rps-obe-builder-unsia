import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

// Selalu memakai anon key + sesi pengguna: semua akses data tunduk pada RLS (NFR-01).
export async function supabaseServer() {
  const store = await cookies();
  return createServerClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!, {
    cookies: {
      getAll: () => store.getAll(),
      setAll: (list) => {
        try {
          list.forEach(({ name, value, options }) => store.set(name, value, options));
        } catch {
          // Dipanggil dari Server Component: penyegaran sesi ditangani middleware.
        }
      },
    },
  });
}

export type Pengguna = { id: string; email: string | null; nama: string | null; role: string; prodi_id: string | null };

export async function penggunaSaatIni(): Promise<Pengguna | null> {
  const sb = await supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return null;
  const { data } = await sb.from("pengguna").select("id, email, nama, role, prodi_id").eq("id", user.id).single();
  return data;
}
