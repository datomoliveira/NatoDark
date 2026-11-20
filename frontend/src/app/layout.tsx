import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NatoDark — Estúdio de Vídeos",
  description: "Crie vídeos dark/dramáticos de alto impacto para YouTube, TikTok e Shorts.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" className="h-full antialiased dark">
      <body className="min-h-full flex flex-col bg-bg-dark text-[#f5f5f5] font-sans">
        {children}
      </body>
    </html>
  );
}
