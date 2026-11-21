import type { Metadata } from "next";
import { Inter, IBM_Plex_Sans_Thai } from "next/font/google";
import { cookies } from "next/headers";
import "./globals.css";
import { I18nProvider } from "@/lib/i18n";
import { FilterProvider } from "@/components/context/FilterContext";
import { PageContextProvider } from "@/components/chat/PageContextProvider";
import type { Locale } from "@/types/marts";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const ibmPlexSansThai = IBM_Plex_Sans_Thai({
  subsets: ["thai", "latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-ibm-thai",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Skill Demand Intelligence — ระบบวิเคราะห์ความต้องการทักษะตลาดแรงงานไทย",
  description:
    "ระบบวิเคราะห์ความต้องการทักษะในตลาดแรงงานไทยจากประกาศงาน ด้วยคลังข้อมูลและการเรียนรู้ของเครื่อง (E′)",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const cookieStore = await cookies();
  const localeCookie = cookieStore.get("skillbi_locale")?.value;
  const initialLocale: Locale = localeCookie === "en" ? "en" : "th";

  return (
    <html
      lang={initialLocale}
      className={`${inter.variable} ${ibmPlexSansThai.variable}`}
    >
      <body className="min-h-screen antialiased">
        <I18nProvider initialLocale={initialLocale}>
          <FilterProvider>
            <PageContextProvider>{children}</PageContextProvider>
          </FilterProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
