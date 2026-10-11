import "./globals.css";
import { Inter } from "next/font/google";

export const metadata = {
  title: "IDO Assistant",
};

const inter = Inter({ subsets: ["latin"], weight: ["300","400","500","600","700"] });

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body
        className={inter.className}
      >
        {children}
      </body>
    </html>
  );
}
