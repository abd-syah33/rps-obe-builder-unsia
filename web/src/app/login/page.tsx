"use client";
import { useActionState } from "react";
import { masuk } from "./actions";

export default function HalamanMasuk() {
  const [galat, aksi, menunggu] = useActionState(masuk, null);
  return (
    <main className="mx-auto mt-24 max-w-sm rounded-xl border bg-white p-8 shadow-sm">
      <h1 className="text-2xl font-bold">RPS Builder · UNSIA</h1>
      <p className="mb-6 text-sm text-slate-500">Masuk dengan email untuk melanjutkan.</p>
      <form action={aksi} className="space-y-4">
        <label className="block text-sm font-medium">
          Email
          <input name="email" type="email" autoComplete="username" required className="mt-1 w-full rounded-md border px-3 py-2" />
        </label>
        <label className="block text-sm font-medium">
          Password
          <input name="password" type="password" autoComplete="current-password" required className="mt-1 w-full rounded-md border px-3 py-2" />
        </label>
        {galat && <p role="alert" className="text-sm text-red-600">{galat}</p>}
        <button disabled={menunggu} className="w-full rounded-md bg-blue-700 py-2 font-medium text-white disabled:opacity-60">
          {menunggu ? "Memproses..." : "Masuk"}
        </button>
      </form>
    </main>
  );
}
