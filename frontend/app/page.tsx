const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function HomePage() {
  return (
    <main className="dashboard-shell">
      <section className="hero-panel">
        <p className="eyebrow">DispatchAI Staff Dashboard</p>
        <h1>Emergency response dashboard skeleton</h1>
        <p className="summary">
          This is the first Next.js frontend slice. Map rendering, OAuth,
          incident polling, and dispatch controls will be added in later tasks.
        </p>
        <dl className="status-grid" aria-label="Frontend configuration">
          <div>
            <dt>Frontend</dt>
            <dd>ready</dd>
          </div>
          <div>
            <dt>Backend API</dt>
            <dd>{apiBaseUrl}</dd>
          </div>
        </dl>
      </section>
    </main>
  );
}
