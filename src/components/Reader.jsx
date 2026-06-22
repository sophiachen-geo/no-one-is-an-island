import { useEffect, useRef } from 'react';
import { marked } from 'marked';
import {
  MOOD_COLOR, placeLabel, regionMeta, travelRange, relatedFragments,
} from '../lib/content';

marked.setOptions({ breaks: true });

export default function Reader({ fragment, allFragments, onClose, onOpen, onTag, onRegion }) {
  const scrollRef = useRef(null);

  // Reset scroll to top whenever a new story opens
  useEffect(() => {
    if (fragment && scrollRef.current) scrollRef.current.scrollTop = 0;
  }, [fragment]);

  if (!fragment) return null;

  const moodColor = MOOD_COLOR[fragment.mood] || '#c4956a';
  const when = travelRange(fragment.travel);
  const related = relatedFragments(fragment, allFragments);

  return (
    <div className="reader-overlay" onClick={onClose}>
      <div
        className="reader"
        role="dialog"
        aria-modal="true"
        aria-label={fragment.title}
        onClick={(e) => e.stopPropagation()}
      >
        <button className="reader-close" onClick={onClose} aria-label="Close">✕</button>

        <div className="reader-scroll" ref={scrollRef}>
          <div className="reader-head">
            <div className="reader-tagline">
              {fragment.mood && (
                <span className="mood-badge" style={{ '--mood': moodColor }}>{fragment.mood}</span>
              )}
              {when && <span className="reader-when">{when}</span>}
            </div>

            <h2 className="reader-title">{fragment.title}</h2>
            {fragment.subtitle && <p className="reader-subtitle">{fragment.subtitle}</p>}

            <div className="reader-places">
              {fragment.regions.map((rid) => {
                const r = regionMeta(rid);
                return r ? (
                  <button
                    key={rid}
                    className="reader-region"
                    style={{ '--region': r.color }}
                    onClick={() => onRegion(r.id)}
                  >
                    <span className="region-dot" style={{ background: r.color }} />
                    {r.label}
                  </button>
                ) : null;
              })}
              {fragment.places.map((p) => (
                <span key={p} className="island-pill">{placeLabel(p)}</span>
              ))}
            </div>
          </div>

          <div
            className="reader-body"
            dangerouslySetInnerHTML={{ __html: marked(fragment.body) }}
          />

          {fragment.tags.length > 0 && (
            <div className="reader-tags">
              {fragment.tags.map((t) => (
                <button key={t} className="tag-pill" onClick={() => onTag(t)}>{t}</button>
              ))}
            </div>
          )}

          {related.length > 0 && (
            <div className="reader-related">
              <h4 className="related-heading">Connected stories</h4>
              {related.map(({ frag, sharedPlaces, sharedTags }) => {
                const reason = sharedPlaces.length
                  ? `Also on ${placeLabel(sharedPlaces[0])}`
                  : `Shares ${sharedTags.slice(0, 2).join(', ')}`;
                return (
                  <button
                    key={frag.slug}
                    className="related-row"
                    onClick={() => onOpen(frag)}
                  >
                    <span className="related-text">
                      <span className="related-title">{frag.title}</span>
                      <span className="related-reason">{reason}</span>
                    </span>
                    <span className="related-arrow">→</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
