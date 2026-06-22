import { useEffect, useRef, useState, useCallback } from 'react';
import {
  forceSimulation, forceLink, forceManyBody,
  forceCenter, forceCollide, forceX, forceY
} from 'd3-force';
import { REGIONS, regionForPlace } from '../lib/content';

// Lighten a hex color toward white by amount t (0..1) for gradient highlights.
function lighten(hex, t) {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const mix = (c) => Math.round(c + (255 - c) * t);
  return `rgb(${mix(r)}, ${mix(g)}, ${mix(b)})`;
}

const RADIUS_BASE  = 11;
const RADIUS_SCALE = 5;
const LINK_COLOR   = 'rgba(120,180,180,0.16)';
const LINK_ACTIVE  = 'rgba(95,188,214,0.6)';
const GLOW_COLOR   = 'rgba(232,196,154,0.35)';

function nodeRadius(n) {
  return RADIUS_BASE + n.weight * RADIUS_SCALE;
}

export default function IslandMap({ graph, activeTag, selectedNode, onSelectNode }) {
  const svgRef        = useRef(null);
  const simRef        = useRef(null);
  const [positions, setPositions] = useState({ nodes: [], links: [] });
  const [hovered,   setHovered]   = useState(null);
  const [dims,      setDims]      = useState({ w: window.innerWidth, h: window.innerHeight });

  // resize
  useEffect(() => {
    const handle = () => setDims({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener('resize', handle);
    return () => window.removeEventListener('resize', handle);
  }, []);

  // simulation
  useEffect(() => {
    if (!graph.nodes.length) return;
    simRef.current?.stop();

    const simNodes = graph.nodes.map(n => ({ ...n, x: dims.w / 2, y: dims.h / 2 }));
    const idToNode = Object.fromEntries(simNodes.map(n => [n.id, n]));
    const simLinks = graph.links.map(l => ({
      ...l,
      source: idToNode[l.source] || l.source,
      target: idToNode[l.target] || l.target,
    }));

    const sim = forceSimulation(simNodes)
      .force('link',    forceLink(simLinks).id(d => d.id).distance(130).strength(0.6))
      .force('charge',  forceManyBody().strength(-280))
      .force('center',  forceCenter(dims.w / 2, dims.h / 2))
      .force('collide', forceCollide().radius(d => nodeRadius(d) + 18))
      .force('x',       forceX(dims.w / 2).strength(0.04))
      .force('y',       forceY(dims.h / 2).strength(0.04))
      .on('tick', () => setPositions({ nodes: [...simNodes], links: [...simLinks] }));

    simRef.current = sim;
    return () => sim.stop();
  }, [graph, dims]);

  const isDimmed = useCallback((node) => {
    if (!activeTag) return false;
    return !node.tags.includes(activeTag);
  }, [activeTag]);

  const isConnected = useCallback((nodeId) => {
    if (!selectedNode) return false;
    return graph.links.some(l => {
      const s = typeof l.source === 'object' ? l.source.id : l.source;
      const t = typeof l.target === 'object' ? l.target.id : l.target;
      return (s === selectedNode.id && t === nodeId) ||
             (t === selectedNode.id && s === nodeId);
    });
  }, [selectedNode, graph.links]);

  return (
    <div className="map-stage">
      <p className="map-hint">Each circle is an island · larger means more stories · tap to read</p>

    <svg
      ref={svgRef}
      width={dims.w}
      height={dims.h}
      className="island-svg"
    >
      <defs>
        <filter id="glow">
          <feGaussianBlur stdDeviation="6" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <filter id="glow-strong">
          <feGaussianBlur stdDeviation="10" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <radialGradient id="island-grad" cx="40%" cy="35%" r="65%">
          <stop offset="0%"   stopColor="#e8c49a" />
          <stop offset="100%" stopColor="#a06030" />
        </radialGradient>
        {REGIONS.map((r) => (
          <radialGradient key={r.id} id={`isl-${r.id}`} cx="40%" cy="35%" r="68%">
            <stop offset="0%"   stopColor={lighten(r.color, 0.35)} />
            <stop offset="100%" stopColor={r.color} />
          </radialGradient>
        ))}
      </defs>

      {/* Connection lines */}
      {positions.links.map((link, i) => {
        const sx = link.source?.x ?? 0;
        const sy = link.source?.y ?? 0;
        const tx = link.target?.x ?? 0;
        const ty = link.target?.y ?? 0;
        const mx = (sx + tx) / 2;
        const my = (sy + ty) / 2 - 30;
        const sid = link.source?.id;
        const tid = link.target?.id;
        const isActive = selectedNode &&
          (sid === selectedNode.id || tid === selectedNode.id);

        return (
          <path
            key={i}
            d={`M ${sx} ${sy} Q ${mx} ${my} ${tx} ${ty}`}
            fill="none"
            stroke={isActive ? LINK_ACTIVE : LINK_COLOR}
            strokeWidth={isActive ? 1.5 : 1}
            opacity={activeTag ? 0.3 : 1}
          />
        );
      })}

      {/* Island nodes */}
      {positions.nodes.map(node => {
        const r        = nodeRadius(node);
        const dimmed   = isDimmed(node);
        const selected = selectedNode?.id === node.id;
        const linked   = isConnected(node.id);
        const hov      = hovered === node.id;
        const region   = regionForPlace(node.id);
        const fill     = region ? `url(#isl-${region})` : 'url(#island-grad)';

        return (
          <g
            key={node.id}
            transform={`translate(${node.x ?? 0}, ${node.y ?? 0})`}
            style={{ cursor: 'pointer', opacity: dimmed ? 0.12 : 1 }}
            onClick={() => !dimmed && onSelectNode(selected ? null : node)}
            onMouseEnter={() => setHovered(node.id)}
            onMouseLeave={() => setHovered(null)}
          >
            {/* glow ring */}
            {(selected || hov || linked) && (
              <circle
                r={r + 10}
                fill={GLOW_COLOR}
                filter="url(#glow)"
              />
            )}
            {/* island body */}
            <circle
              r={r}
              fill={fill}
              stroke={selected ? '#ffffff' : linked ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.25)'}
              strokeWidth={selected ? 2.5 : 1.25}
              filter={selected ? 'url(#glow-strong)' : hov ? 'url(#glow)' : undefined}
            />
            {/* label */}
            <text
              y={r + 16}
              textAnchor="middle"
              fontSize={selected || hov ? 13 : 12}
              fontWeight={selected || hov ? 600 : 400}
              fill={selected || hov ? '#f4e6cf' : 'rgba(245,236,222,0.72)'}
              fontFamily="'Cormorant Garamond', Georgia, serif"
              letterSpacing="0.05em"
              style={{ userSelect: 'none', pointerEvents: 'none', paintOrder: 'stroke' }}
              stroke="rgba(8,10,16,0.85)"
              strokeWidth="3"
            >
              {node.label}
            </text>
          </g>
        );
      })}
    </svg>

      <div className="map-legend">
        {REGIONS.map((r) => (
          <span key={r.id} className="legend-item">
            <span className="region-dot" style={{ background: r.color }} />
            {r.label}
          </span>
        ))}
      </div>
    </div>
  );
}
