export default function Loading() {
  return (
    <main id="main" className="route-loading" aria-label="Loading page" aria-busy="true">
      <div className="route-loading-card">
        <div className="route-loading-mark" aria-hidden="true"><span>C</span><i /></div>
        <p className="route-loading-brand">COMPAT<span>FLOW</span></p>
        <div className="route-loading-dots" aria-hidden="true"><i /><i /><i /></div>
        <p className="route-loading-label">Preparing your workspace</p>
      </div>
    </main>
  );
}
