import {
  MOOD_COLOR, placeLabel, plainExcerpt, regionMeta, travelRange,
} from '../lib/content';

function StoryCard({ frag, onOpen }) {
  const mood = frag.mood;
  const moodColor = MOOD_COLOR[mood] || '#c4956a';
  const when = travelRange(frag.travel);

  return (
    <article
      className="card"
      tabIndex={0}
      role="button"
      onClick={() => onOpen(frag)}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(frag); } }}
    >
      <div className="card-top">
        {mood && (
          <span className="mood-badge" style={{ '--mood': moodColor }}>{mood}</span>
        )}
        <div className="card-regions">
          {frag.regions.map((rid) => {
            const r = regionMeta(rid);
            return r ? (
              <span key={rid} className="card-region">
                <span className="region-dot" style={{ background: r.color }} />
                {r.label}
              </span>
            ) : null;
          })}
        </div>
      </div>

      <h3 className="card-title">{frag.title}</h3>
      {frag.subtitle && <p className="card-subtitle">{frag.subtitle}</p>}
      <p className="card-excerpt">{plainExcerpt(frag.body)}</p>

      <div className="card-islands">
        {frag.places.map((p) => (
          <span key={p} className="island-pill">{placeLabel(p)}</span>
        ))}
      </div>

      <div className="card-foot">
        {when && <span className="card-when">{when}</span>}
        <span className="read-link">Read<span className="read-arrow"> →</span></span>
      </div>
    </article>
  );
}

export default function StoryGrid({
  fragments, total, islandCount, hasFilters, onClear, onOpen,
}) {
  return (
    <main className="grid-wrap">
      <div className="grid-meta">
        <span className="grid-count">
          {hasFilters
            ? `${fragments.length} of ${total} ${total === 1 ? 'story' : 'stories'}`
            : `${total} stories · ${islandCount} islands`}
        </span>
      </div>

      {fragments.length > 0 ? (
        <div className="story-grid">
          {fragments.map((frag) => (
            <StoryCard key={frag.slug} frag={frag} onOpen={onOpen} />
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <p className="empty-title">Nothing here yet</p>
          <p className="empty-sub">No stories match these filters.</p>
          {hasFilters && (
            <button className="empty-clear" onClick={onClear}>Clear filters</button>
          )}
        </div>
      )}
    </main>
  );
}
