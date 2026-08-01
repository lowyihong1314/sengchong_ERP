export function DebtorInfo({ debtor, showEmpty = false }) {
  if (!debtor?.code && !showEmpty) return null;

  const detailItems = debtor
    ? [
        ["Term", debtor.displayTerm],
        ["Currency", debtor.currencyCode],
        ["Agent", debtor.agent],
        ["Area", debtor.area],
        ["Phone", debtor.phone],
      ].filter(([, value]) => value)
    : [];

  return (
    <section className="account-strip" aria-label="Debtor detail">
      <article className={`account-card ${debtor?.code ? "" : "empty"}`}>
        <div className="account-card-label">Debtor</div>
        {debtor?.code ? (
          <>
            <div className="account-code">{debtor.code}</div>
            <div className="account-name">{debtor.name || "No debtor name"}</div>
            {detailItems.length > 0 && (
              <dl className="account-meta">
                {detailItems.map(([label, value]) => (
                  <div key={label}>
                    <dt>{label}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
            )}
          </>
        ) : (
          <div className="account-empty-text">Select Debtor Code to show debtor name</div>
        )}
      </article>
    </section>
  );
}
