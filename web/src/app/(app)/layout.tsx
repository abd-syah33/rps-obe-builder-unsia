import Link from "next/link";
import { redirect } from "next/navigation";
import { penggunaSaatIni } from "@/lib/supabase/server";
import { keluar } from "@/app/login/actions";

// Menu menyesuaikan peran (FR-A05). Hak akses sebenarnya tetap dijaga RLS.
const MENU: { href: string; label: string; peran?: string[] }[] = [
  { href: "/isi-rps", label: "Isi RPS" },
  { href: "/rps-saya", label: "RPS Saya" },
  { href: "/tervalidasi", label: "RPS Tervalidasi" },
  { href: "/review", label: "Review Kaprodi", peran: ["kaprodi"] },
  { href: "/validasi", label: "Validasi BPM", peran: ["bpm"] },
  { href: "/admin", label: "Panel Admin", peran: ["admin"] },
];

export default async function TataLetakAplikasi({ children }: { children: React.ReactNode }) {
  const p = await penggunaSaatIni();
  if (!p) redirect("/login");
  return (
    <div className="min-h-screen">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-3">
          <span className="font-bold">RPS Builder</span>
          <nav className="flex flex-wrap gap-3 text-sm">
            {MENU.filter((m) => !m.peran || m.peran.includes(p.role)).map((m) => (
              <Link key={m.href} href={m.href} className="rounded px-2 py-1 hover:bg-slate-100">{m.label}</Link>
            ))}
          </nav>
          <span className="ml-auto text-sm text-slate-500">{p.nama ?? p.email} · {p.role}</span>
          <form action={keluar}><button className="text-sm text-blue-700 hover:underline">Keluar</button></form>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}
