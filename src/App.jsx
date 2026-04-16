import { useMemo, useState } from 'react';
import { parseFragment } from './lib/parseFragment';
import { buildGraph }    from './lib/buildGraph';
import IslandMap         from './components/IslandMap';
import Reader            from './components/Reader';
import TagBar            from './components/TagBar';
import './App.css';

// Load all .md files in fragments/ as raw strings (Vite)
const rawModules = import.meta.glob(
  './content/fragments/*.md',
  { query: '?raw', import: 'default', eager: true }
);

const FRAGMENTS = Object.entries(rawModules)
  .map(([path, raw]) => parseFragment(raw, path))
  .filter(Boolean);

export default function App() {
  const [activeTag,     setActiveTag]     = useState(null);
  const [selectedNode,  setSelectedNode]  = useState(null);

  const graph = useMemo(() => buildGraph(FRAGMENTS), []);

  return (
    <div className="app">
      {/* Ocean background */}
      <div className="ocean-bg" />

      {/* Site title */}
      <header className="site-header">
        <h1 className="site-title">No One Is an Island</h1>
        <p className="site-byline">Sophia Chen · Fall 2025</p>
      </header>

      {/* Tag filter bar */}
      <TagBar
        allTags={graph.allTags}
        activeTag={activeTag}
        onTagClick={setActiveTag}
      />

      {/* Force-directed map */}
      <IslandMap
        graph={graph}
        activeTag={activeTag}
        selectedNode={selectedNode}
        onSelectNode={setSelectedNode}
      />

      {/* Reading panel */}
      <Reader
        node={selectedNode}
        onClose={() => setSelectedNode(null)}
      />

      {/* Fragment count */}
      <div className="fragment-count">
        {FRAGMENTS.length} fragments · {graph.nodes.length} islands
      </div>
    </div>
  );
}
