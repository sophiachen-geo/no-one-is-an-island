import { useState } from 'react';

export default function Controls({
  view, onView,
  query, onQuery,
  regions, activeRegion, onRegion,
  allTags, activeTag, onTag,
  hasFilters, onClear,
}) {
  const [showTags, setShowTags] = useState(false);

  return (
    <div className="controls">
      <div className="controls-row">
        {/* Search */}
        <div className="search">
          <svg className="search-icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
            <circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" strokeWidth="2" />
            <line x1="16.5" y1="16.5" x2="21" y2="21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <input
            type="search"
            className="search-input"
            placeholder="Search stories, places, tags…"
            value={query}
            onChange={(e) => onQuery(e.target.value)}
            aria-label="Search stories"
          />
          {query && (
            <button className="search-clear" onClick={() => onQuery('')} aria-label="Clear search">✕</button>
          )}
        </div>

        {/* View toggle */}
        <div className="view-toggle" role="tablist" aria-label="View">
          <button
            role="tab"
            aria-selected={view === 'stories'}
            className={`view-btn${view === 'stories' ? ' active' : ''}`}
            onClick={() => onView('stories')}
          >
            <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
              <rect x="3" y="4" width="7" height="7" rx="1.5" fill="currentColor" />
              <rect x="14" y="4" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.55" />
              <rect x="3" y="14" width="7" height="7" rx="1.5" fill="currentColor" opacity="0.55" />
              <rect x="14" y="14" width="7" height="7" rx="1.5" fill="currentColor" />
            </svg>
            Stories
          </button>
          <button
            role="tab"
            aria-selected={view === 'map'}
            className={`view-btn${view === 'map' ? ' active' : ''}`}
            onClick={() => onView('map')}
          >
            <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
              <circle cx="6" cy="7" r="2.4" fill="currentColor" />
              <circle cx="17" cy="9" r="2.4" fill="currentColor" />
              <circle cx="12" cy="17" r="2.4" fill="currentColor" />
              <line x1="6" y1="7" x2="17" y2="9" stroke="currentColor" strokeWidth="1.4" opacity="0.6" />
              <line x1="17" y1="9" x2="12" y2="17" stroke="currentColor" strokeWidth="1.4" opacity="0.6" />
              <line x1="6" y1="7" x2="12" y2="17" stroke="currentColor" strokeWidth="1.4" opacity="0.6" />
            </svg>
            Map
          </button>
        </div>
      </div>

      {/* Region filters */}
      <div className="filter-row">
        <button
          className={`region-pill${!activeRegion ? ' active' : ''}`}
          onClick={() => activeRegion && onRegion(activeRegion)}
        >
          All places
        </button>
        {regions.map((r) => (
          <button
            key={r.id}
            className={`region-pill${activeRegion === r.id ? ' active' : ''}`}
            style={activeRegion === r.id ? { '--region': r.color } : { '--region': r.color }}
            onClick={() => onRegion(r.id)}
          >
            <span className="region-dot" style={{ background: r.color }} />
            {r.label}
          </button>
        ))}

        <button
          className={`tags-toggle${showTags ? ' open' : ''}${activeTag ? ' has-active' : ''}`}
          onClick={() => setShowTags((s) => !s)}
          aria-expanded={showTags}
        >
          {activeTag ? `Tag: ${activeTag}` : 'Tags'}
          <span className="tags-caret">{showTags ? '▴' : '▾'}</span>
        </button>

        {hasFilters && (
          <button className="clear-filters" onClick={onClear}>Clear all</button>
        )}
      </div>

      {/* Tag cloud (collapsible) */}
      {showTags && (
        <div className="tag-cloud">
          {allTags.map((tag) => (
            <button
              key={tag}
              className={`tag-pill${activeTag === tag ? ' active' : ''}`}
              onClick={() => onTag(tag)}
            >
              {tag}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
