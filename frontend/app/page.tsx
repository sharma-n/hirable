import Link from "next/link";

export default function Home() {
  return (
    <main style={{ padding: "2rem" }}>
      <h1>hirable</h1>
      <p>Your job application assistant.</p>
      <Link href="/chat">Open chat →</Link>
    </main>
  );
}
