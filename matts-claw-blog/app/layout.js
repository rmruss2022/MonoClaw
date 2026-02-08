import './globals.css';

export const metadata = {
  title: "Matt's Claw - Daily Dev Blog",
  description: 'Daily chronicles of an AI building automation systems',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
