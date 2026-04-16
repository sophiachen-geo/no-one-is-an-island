import { useState } from 'react';
import { marked } from 'marked';

marked.setOptions({ breaks: true });

export default function Reader({ node, onClose }) {
  const [openSlug, setOpenSlug] = useState(null);

  if (!node) return null;

  return (
    <div className="reader-panel">
      <button className="reader-close" onClick={onClose} aria-label="Close">✕</button>

      <div className="reader-header">
        <h2 className="reader-island-name">{node.label}</h2>
        <p className="reader-meta">{node.fragments.length} {node.fragments.length === 1 ? 'fragment' : 'fragments'}</p>
      </div>

      <div className="reader-fragments">
        {node.fragments.map(frag => (
          <div key={frag.slug} className="reader-card">
            <button
              className="reader-card-header"
              onClick={() => setOpenSlug(openSlug === frag.slug ? null : frag.slug)}
            >
              <div className="reader-card-top">
                <span className="reader-card-title">{frag.title}</span>
                <span className="reader-card-chevron">{openSlug === frag.slug ? '▲' : '▼'}</span>
              </div>
              {frag.subtitle && <p className="reader-card-subtitle">{frag.subtitle}</p>}
              <div className="reader-card-chips">
                {frag.mood && <span className="chip chip-mood">{frag.mood}</span>}
                {frag.tags.slice(0, 4).map(t => (
                  <span key={t} className="chip chip-tag">{t}</span>
                ))}
              </div>
            </button>

            {openSlug === frag.slug && (
              <div
                className="reader-card-body"
                dangerouslySetInnerHTML={{ __html: marked(frag.body) }}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
