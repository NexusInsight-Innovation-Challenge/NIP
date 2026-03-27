"use client";

import { signIn } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { NexusLogo } from "@/components/nexus-logo";

function LoginContent() {
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") || "/";

  return (
    <div className="relative flex flex-col items-center justify-center min-h-screen overflow-hidden bg-[#f8f9fa]">
      {/* Background orbs */}
      <div className="absolute top-[10%] left-[-10%] w-[50vw] h-[50vw] rounded-full bg-[radial-gradient(circle,rgba(16,148,210,0.15)_0%,rgba(255,255,255,0)_70%)] animate-pulse" />
      <div className="absolute bottom-[10%] right-[-10%] w-[60vw] h-[60vw] rounded-full bg-[radial-gradient(circle,rgba(108,53,212,0.1)_0%,rgba(255,255,255,0)_70%)] animate-pulse" style={{ animationDelay: "2s", animationDuration: "8s" }} />

      <div className="relative z-10 w-full max-w-lg px-4">
        {/* Glow behind the card */}
        <div className="absolute -inset-1 bg-gradient-to-r from-[#1094D2] via-[#6C35D4] to-[#C62287] rounded-[2.5rem] blur-2xl opacity-40 hover:opacity-60 transition-opacity duration-700 animate-pulse"></div>
        
        {/* Glassmorphism Card */}
        <div className="relative bg-white/80 backdrop-blur-3xl border border-white p-12 rounded-[2.5rem] shadow-2xl text-center flex flex-col items-center">
          <NexusLogo className="w-24 h-24 mb-8 transform hover:scale-110 transition-transform duration-700" />
          
          <h1 className="text-4xl font-bold tracking-tight text-[#201F1E] mb-4">
            Nexus <span className="bg-gradient-to-r from-[#1094D2] via-[#6C35D4] to-[#C62287] bg-clip-text text-transparent">Insight</span>
          </h1>
          
          <p className="text-lg text-[#605E5C] mb-8 leading-relaxed">
            Analytical AI with Measured Results. Inicia sesión para acceder a inteligencia ejecutiva.
          </p>
          
          <Button 
            className="w-full bg-[#201F1E] hover:bg-[#201F1E]/90 text-white shadow-lg shadow-black/10 rounded-xl h-12 text-md transition-all hover:-translate-y-1" 
            size="lg"
            onClick={() => signIn("azure-ad", { callbackUrl })}
          >
            Iniciar sesión con Entra ID
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="flex min-h-screen items-center justify-center bg-[#f8f9fa]">
        <p className="text-[#605E5C]">Cargando...</p>
      </div>
    }>
      <LoginContent />
    </Suspense>
  );
}
