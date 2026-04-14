import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Header from "@/components/Header";
import { PriceProvider } from "@/context/PriceContext";
import { NotificationProvider } from "@/context/NotificationContext";
import NotificationToast from "@/components/NotificationToast";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "PerpYield | Delta-Neutral Funding Rate Vault",
  description:
    "Earn yield from perpetual funding rates with delta-neutral strategies",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased dark`}
    >
      <body className="min-h-full bg-background text-foreground">
        <NotificationProvider>
          <PriceProvider>
            <Header />
            <NotificationToast />
            <main className="max-w-[1400px] mx-auto px-6 py-6">{children}</main>
          </PriceProvider>
        </NotificationProvider>
      </body>
    </html>
  );
}
