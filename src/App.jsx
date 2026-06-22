import { useEffect, useMemo, useState, useCallback } from 'react';
import { parseFragment } from './lib/parseFragment';
import { buildGraph } from './lib/buildGraph';
import { REGIONS, fragmentRegions } from './lib/content';
import Controls from './components/Controls';
import StoryGrid from './components/StoryGrid';
import IslandMap from './components/IslandMap';
import Reader from './components/Reader';
import './App.css';

// Load all .md files in fragments/ as raw strings (Vite)
const rawModules = import.meta.glob(
  './content/fragments/*.md',
  { query: '?raw', import: 'default', eager: true }
);

const FRAGMENTS = Object.entries(rawModules)
  .map(([path, raw]) => parseFragment(raw, path))
  .filter(Boolean)
  .map((f) => ({ ...f, regions: fragmentRegions(f) }));

export default function App() {
  const [view, setView] = useState('stories');      // 'stories' | 'map'
  const [query, setQuery] = useState('');
  const [activeTag, setActiveTag] = useState(null);
  const [activeRegion, setActiveRegion] = useState(null);
  const [openFragment, setOpenFragment] = useState(null);   // reader (story)
  const [selectedNode, setSelectedNode] = useState(null);   // map highlight

  const graph = useMemo(() => buildGraph(FRAGMENTS), []);

  const presentRegions = useMemo(() => {
    const set = new Set(FRAGMENTS.flatMap((f) => f.regions));
    return REGIONS.filter((r) => set.has(r.id));
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return FRAGMENTS.filter((f) => {
      if (activeRegion && !f.regions.includes(activeRegion)) return false;
      if (activeTag && !f.tags.includes(activeTag)) return false;
      if (q) {
        const hay = [f.title, f.subtitle, f.mood, ...f.tags, ...f.places, f.body]
          .join(' ')
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [query, activeTag, activeRegion]);

  const hasFilters = !!(query || activeTag || activeRegion);
  const clearFilters = useCallback(() => {
    setQuery('');
    setActiveTag(null);
    setActiveRegion(null);
  }, []);

  const closeReader = useCallback(() => {
    setOpenFragment(null);
    setSelectedNode(null);
  }, []);

  // Esc closes the reader
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') closeReader(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [closeReader]);

  // Lock page scroll while in the full-screen map view
  useEffect(() => {
    document.body.classList.toggle('lock-scroll', view === 'map');
    return () => document.body.classList.remove('lock-scroll');
  }, [view]);

  // Map: selecting an island opens its first story in the reader
  const handleSelectNode = useCallback((node) => {
    setSelectedNode(node);
    setOpenFragment(node ? node.fragments[0] : null);
  }, []);

  // From inside the reader: jump to a tag/region (always lands in stories view)
  const jumpToTag = useCallback((tag) => {
    setView('stories');
    setActiveTag(tag);
    setActiveRegion(null);
    setQuery('');
    closeReader();
  }, [closeReader]);

  const jumpToRegion = useCallback((region) => {
    setView('stories');
    setActiveRegion(region);
    setActiveTag(null);
    setQuery('');
    closeReader();
  }, [closeReader]);

  return (
    <div className={`app view-${view}`}>
      <div className="ocean-bg" aria-hidden="true" />

      <header className="hero">
        <div className="hero-inner">
          <p className="hero-eyebrow">Sophia Chen · Fall 2025</p>
          <h1 className="hero-title">No One Is an Island</h1>
          {view === 'stories' && (
            <p className="hero-intro">
              Island stories across Japan, Taiwan, Hong Kong, and mainland China —
              tied together by gods, tides, salt, and the people who keep crossing
              the water. Search, filter by place, or open the map to see how they connect.
            </p>
          )}
        </div>
      </header>

      <Controls
        view={view}
        onView={setView}
        query={query}
        onQuery={setQuery}
        regions={presentRegions}
        activeRegion={activeRegion}
        onRegion={(r) => setActiveRegion(activeRegion === r ? null : r)}
        allTags={graph.allTags}
        activeTag={activeTag}
        onTag={(t) => setActiveTag(activeTag === t ? null : t)}
        hasFilters={hasFilters}
        onClear={clearFilters}
      />

      {view === 'stories' ? (
        <StoryGrid
          fragments={filtered}
          total={FRAGMENTS.length}
          islandCount={graph.nodes.length}
          hasFilters={hasFilters}
          onClear={clearFilters}
          onOpen={setOpenFragment}
        />
      ) : (
        <IslandMap
          graph={graph}
          activeTag={activeTag}
          selectedNode={selectedNode}
          onSelectNode={handleSelectNode}
        />
      )}

      <Reader
        fragment={openFragment}
        allFragments={FRAGMENTS}
        onClose={closeReader}
        onOpen={setOpenFragment}
        onTag={jumpToTag}
        onRegion={jumpToRegion}
      />
    </div>
  );
}
