import "./globals.css";

export const metadata = {
  title: "DispatchAI",
  description: "AI-assisted emergency volunteer dispatch dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
