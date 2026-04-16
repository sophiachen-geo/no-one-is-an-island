import { useEffect, useRef, useState, useCallback } from 'react';
import {
  forceSimulation, forceLink, forceManyBody,
  forceCenter, forceCollide, forceX, forceY
} from 'd3-force';

const RADIUS_BASE  = 10;
const RADIUS_SCALE = 5;
const ISLAND_COLOR = '#c4956a';
const LINK_COLOR   = 'rgba(255,255,255,0.07)';
const LINK_ACTIVE  = 'rgba(196,149,106,0.35)';
const GLOW_COLOR   = 'rgba(196,149,106,0.25)';

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
              fill="url(#island-grad)"
              stroke={selected ? '#e8c49a' : linked ? '#c4956a' : 'rgba(255,255,255,0.15)'}
              strokeWidth={selected ? 2 : 1}
              filter={selected ? 'url(#glow-strong)' : hov ? 'url(#glow)' : undefined}
            />
            {/* label */}
            <text
              y={r + 14}
              textAnchor="middle"
              fontSize={11}
              fill={selected || hov ? '#e8c49a' : 'rgba(255,255,255,0.55)'}
              fontFamily="'Cormorant Garamond', Georgia, serif"
              letterSpacing="0.06em"
              style={{ userSelect: 'none', pointerEvents: 'none' }}
            >
              {node.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
