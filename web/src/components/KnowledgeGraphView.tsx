import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Search, HelpCircle, ChevronDown, ChevronRight, X } from 'lucide-react';
import { collectionsApi } from '../api/client';
import type { KnowledgeGraph } from '../types';
import './KnowledgeGraphView.css';

interface Props {
  collectionId: string;
}

interface SimNode {
  id: string;
  name: string;
  entityType: string;
  description?: string;
  labels: string[];
  entityId?: string;
  createdAt?: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  color: string;
  connections: number;
  pinned: boolean;
}

interface SimLink {
  source: string;
  target: string;
  id: string;
  relationshipType?: string;
  description?: string;
  fact?: string;
  weight?: number;
  keywords?: string;
  sourceId?: string;
  filePath?: string;
  createdAt?: number;
  episodes?: string;
  validFrom?: number;
}

type FilterType = 'All' | 'Entities' | 'Edges' | 'Facts';

const ENTITY_TYPE_COLORS: Record<string, string> = {
  entity: '#ff6b9d',
  event: '#5b9cf6',
  location: '#2dd4a8',
  object: '#fbbf24',
  preference: '#a78bfa',
  topic: '#f97316',
  user: '#34d399',
  person: '#ff6b9d',
  organization: '#ff6b9d',
  concept: '#a78bfa',
  category: '#f97316',
  time: '#5b9cf6',
  date: '#5b9cf6',
};
const DEFAULT_COLOR = '#ff6b9d';

/** 根据字符串生成确定性颜色（用于未在预设中的标签） */
function colorFromLabel(label: string): string {
  let h = 0;
  for (let i = 0; i < label.length; i++) {
    h = (h * 31 + label.charCodeAt(i)) >>> 0;
  }
  const hue = h % 360;
  const saturation = 72;
  const lightness = 58;
  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
}

function getEntityColor(entityType?: string): string {
  if (!entityType) return DEFAULT_COLOR;
  const key = entityType.toLowerCase().trim();
  return ENTITY_TYPE_COLORS[key] || colorFromLabel(key);
}

function capitalizeFirst(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}

function formatTimestamp(ts?: number): string {
  if (!ts) return '';
  try {
    const d = new Date(ts * 1000);
    return d.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return '';
  }
}

function extractRelType(edge: { id: string; type?: string; source: string; target: string }): string {
  if (edge.type && edge.type !== 'DIRECTED') return edge.type;
  const id = edge.id;
  const srcIdx = id.indexOf(edge.source);
  const tgtIdx = id.indexOf(edge.target);
  if (srcIdx !== -1 && tgtIdx !== -1) {
    const start = srcIdx + edge.source.length;
    const end = tgtIdx;
    if (start < end) {
      const sep = id.substring(start, end).replace(/^[-_]+|[-_]+$/g, '');
      if (sep) return sep;
    }
  }
  return edge.type || '';
}

/** Distance from point (px, py) to line segment (ax, ay)-(bx, by) in world coords */
function distanceToSegment(px: number, py: number, ax: number, ay: number, bx: number, by: number): number {
  const abx = bx - ax;
  const aby = by - ay;
  const apx = px - ax;
  const apy = py - ay;
  const ab2 = abx * abx + aby * aby;
  let t = ab2 <= 0 ? 0 : (apx * abx + apy * aby) / ab2;
  t = Math.max(0, Math.min(1, t));
  const qx = ax + t * abx;
  const qy = ay + t * aby;
  return Math.sqrt((px - qx) ** 2 + (py - qy) ** 2);
}

export default function KnowledgeGraphView({ collectionId }: Props) {
  const [rawGraph, setRawGraph] = useState<KnowledgeGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<FilterType>('All');
  const [showFilterDropdown, setShowFilterDropdown] = useState(false);
  const [legendCollapsed, setLegendCollapsed] = useState(false);
  const [highlightType, setHighlightType] = useState<string | null>(null);
  const [graphLabels, setGraphLabels] = useState<string[]>([]);
  const [showHelp, setShowHelp] = useState(false);
  const [hoveredNode, setHoveredNode] = useState<SimNode | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [selectedNode, setSelectedNode] = useState<SimNode | null>(null);
  const [selectedLink, setSelectedLink] = useState<SimLink | null>(null);
  const [hoveredLink, setHoveredLink] = useState<SimLink | null>(null);
  const [linkTooltipPos, setLinkTooltipPos] = useState({ x: 0, y: 0 });

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const nodesRef = useRef<SimNode[]>([]);
  const linksRef = useRef<SimLink[]>([]);
  const animRef = useRef<number>(0);
  const dragNodeRef = useRef<SimNode | null>(null);
  const panRef = useRef({ x: 0, y: 0 });
  const zoomRef = useRef(1);
  const mouseDownPosRef = useRef<{ x: number; y: number } | null>(null);
  const isPanningRef = useRef(false);
  const tickRef = useRef(0);
  const selectedNodeIdRef = useRef<string | null>(null);
  const selectedLinkIdRef = useRef<string | null>(null);
  const clickedLinkRef = useRef<SimLink | null>(null);
  const didDragRef = useRef(false);

  useEffect(() => {
    selectedNodeIdRef.current = selectedNode?.id ?? null;
  }, [selectedNode]);

  useEffect(() => {
    selectedLinkIdRef.current = selectedLink?.id ?? null;
  }, [selectedLink]);

  const loadGraph = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await collectionsApi.getKnowledgeGraph(collectionId);
      setRawGraph(data);
    } catch (err) {
      console.error('Failed to load knowledge graph:', err);
      setError(err instanceof Error ? err.message : 'Failed to load knowledge graph');
    } finally {
      setLoading(false);
    }
  }, [collectionId]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  // Get Graph Labels: GET /api/v1/collections/{collection_id}/graphs/labels
  useEffect(() => {
    let cancelled = false;
    collectionsApi
      .getGraphLabels(collectionId)
      .then((res) => {
        if (!cancelled && res.labels && res.labels.length) {
          setGraphLabels(res.labels.map((l) => (typeof l === 'string' ? l : String(l)).toLowerCase()));
        }
      })
      .catch((err) => {
        if (!cancelled) console.warn('Failed to load graph labels:', err);
      });
    return () => { cancelled = true; };
  }, [collectionId]);

  const entityTypes = useMemo(() => {
    if (graphLabels.length) return graphLabels;
    if (!rawGraph) return [];
    const typeSet = new Set<string>();
    rawGraph.nodes.forEach((n) => {
      const et = n.properties?.entity_type;
      if (et) typeSet.add(et.toLowerCase());
    });
    return Array.from(typeSet).sort();
  }, [rawGraph, graphLabels]);

  useEffect(() => {
    if (!rawGraph) return;

    const connCount: Record<string, number> = {};
    rawGraph.edges.forEach((e) => {
      connCount[e.source] = (connCount[e.source] || 0) + 1;
      connCount[e.target] = (connCount[e.target] || 0) + 1;
    });

    const validIds = new Set(rawGraph.nodes.map((n) => n.id));
    const labelSet = new Set(graphLabels.map((l) => l.toLowerCase().trim()));

    const nodes: SimNode[] = rawGraph.nodes.map((n, i) => {
      // 1) 优先使用后端返回的 labels 与 graphLabels 交集作为实体类型
      let entityType = '';
      if (labelSet.size && n.labels && n.labels.length) {
        const matched = n.labels.find((label) =>
          labelSet.has(label.toLowerCase().trim())
        );
        if (matched) {
          entityType = matched.toLowerCase().trim();
        }
      }
      // 2) 否则回退到 properties.entity_type
      if (!entityType) {
        entityType = (n.properties?.entity_type || 'entity').toLowerCase().trim();
      }

      const conns = connCount[n.id] || 0;
      const angle = (2 * Math.PI * i) / rawGraph.nodes.length;
      const spread = Math.sqrt(rawGraph.nodes.length) * 25;
      const displayName =
        typeof n.properties?.name === 'string' ? n.properties.name : n.id;
      return {
        id: n.id,
        name: displayName,
        entityType,
        description:
          n.properties?.description ?? (typeof n.properties?.summary === 'string' ? n.properties.summary : undefined),
        labels: n.labels || [],
        entityId: n.properties?.entity_id,
        createdAt: n.properties?.created_at,
        x: Math.cos(angle) * spread * (0.5 + Math.random() * 0.5),
        y: Math.sin(angle) * spread * (0.5 + Math.random() * 0.5),
        vx: 0,
        vy: 0,
        radius: Math.max(4, Math.min(18, conns * 1.8 + 4)),
        color: getEntityColor(entityType),
        connections: conns,
        pinned: false,
      };
    });

    const links: SimLink[] = rawGraph.edges
      .filter((e) => validIds.has(e.source) && validIds.has(e.target))
      .map((e) => ({
        source: e.source,
        target: e.target,
        id: e.id,
        relationshipType: e.properties?.name || extractRelType(e),
        description: e.properties?.description || e.properties?.fact,
        fact: e.properties?.fact,
        weight: e.properties?.weight,
        keywords: e.properties?.keywords,
        sourceId: e.properties?.source_id,
        filePath: e.properties?.file_path,
        createdAt: e.properties?.created_at,
        episodes: e.properties?.episodes,
        validFrom: e.properties?.valid_from,
      }));

    nodesRef.current = nodes;
    linksRef.current = links;
    tickRef.current = 0;
  }, [rawGraph, graphLabels]);

  const filteredIds = useMemo(() => {
    const nodes = nodesRef.current;
    const links = linksRef.current;
    if (!searchQuery) return null;

    const q = searchQuery.toLowerCase();
    if (filterType === 'All' || filterType === 'Entities') {
      return new Set(
        nodes
          .filter(
            (n) =>
              n.name.toLowerCase().includes(q) ||
              n.entityType.includes(q) ||
              (n.description && n.description.toLowerCase().includes(q))
          )
          .map((n) => n.id)
      );
    }
    if (filterType === 'Edges' || filterType === 'Facts') {
      const matchedLinks = links.filter(
        (l) =>
          l.id.toLowerCase().includes(q) ||
          (l.description && l.description.toLowerCase().includes(q)) ||
          (l.relationshipType && l.relationshipType.toLowerCase().includes(q))
      );
      const ids = new Set<string>();
      matchedLinks.forEach((l) => { ids.add(l.source); ids.add(l.target); });
      return ids;
    }
    return null;
  }, [searchQuery, filterType, rawGraph]);

  // Force simulation + render loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !rawGraph || rawGraph.nodes.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const nodeMap = new Map<string, SimNode>();

    const simulate = () => {
      const nodes = nodesRef.current;
      const links = linksRef.current;
      nodeMap.clear();
      nodes.forEach((n) => nodeMap.set(n.id, n));

      const alpha = tickRef.current < 300 ? Math.max(0.001, 1 - tickRef.current / 300) : 0.001;
      tickRef.current++;

      for (let i = 0; i < nodes.length; i++) {
        const ni = nodes[i];
        if (ni.pinned) continue;
        for (let j = i + 1; j < nodes.length; j++) {
          const nj = nodes[j];
          let dx = ni.x - nj.x;
          let dy = ni.y - nj.y;
          let dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const minDist = (ni.radius + nj.radius) * 2;
          if (dist < minDist) dist = minDist;
          const force = (300 * alpha) / (dist * dist);
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          ni.vx += fx;
          ni.vy += fy;
          if (!nj.pinned) { nj.vx -= fx; nj.vy -= fy; }
        }
      }

      links.forEach((l) => {
        const src = nodeMap.get(l.source);
        const tgt = nodeMap.get(l.target);
        if (!src || !tgt) return;
        const dx = tgt.x - src.x;
        const dy = tgt.y - src.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const idealLen = 80;
        const force = ((dist - idealLen) / dist) * 0.05 * alpha;
        const fx = dx * force;
        const fy = dy * force;
        if (!src.pinned) { src.vx += fx; src.vy += fy; }
        if (!tgt.pinned) { tgt.vx -= fx; tgt.vy -= fy; }
      });

      nodes.forEach((n) => {
        if (n.pinned) return;
        n.vx -= n.x * 0.001 * alpha;
        n.vy -= n.y * 0.001 * alpha;
      });

      const damping = 0.85;
      nodes.forEach((n) => {
        if (n.pinned) return;
        n.vx *= damping;
        n.vy *= damping;
        const speed = Math.sqrt(n.vx * n.vx + n.vy * n.vy);
        if (speed > 10) { n.vx = (n.vx / speed) * 10; n.vy = (n.vy / speed) * 10; }
        n.x += n.vx;
        n.y += n.vy;
      });
    };

    const render = () => {
      const dpr = window.devicePixelRatio || 1;
      const w = canvas.width / dpr;
      const h = canvas.height / dpr;
      const zoom = zoomRef.current;
      const pan = panRef.current;
      const nodes = nodesRef.current;
      const links = linksRef.current;
      const selId = selectedNodeIdRef.current;
      const selLinkId = selectedLinkIdRef.current;

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = '#0d1117';
      ctx.fillRect(0, 0, w, h);

      ctx.save();
      ctx.translate(w / 2 + pan.x, h / 2 + pan.y);
      ctx.scale(zoom, zoom);

      const nMap = new Map<string, SimNode>();
      nodes.forEach((n) => nMap.set(n.id, n));

      // If a node or edge is selected, only show the subgraph directly related to it
      let visibleNodeIds: Set<string> | null = null;
      let visibleLinkIds: Set<string> | null = null;
      const hasSelection = Boolean(selId || selLinkId);
      if (hasSelection) {
        visibleNodeIds = new Set<string>();
        visibleLinkIds = new Set<string>();

        if (selId) {
          visibleNodeIds.add(selId);
          links.forEach((l) => {
            if (l.source === selId || l.target === selId) {
              visibleLinkIds!.add(l.id);
              visibleNodeIds!.add(l.source);
              visibleNodeIds!.add(l.target);
            }
          });
        } else if (selLinkId) {
          const selectedEdge = links.find((l) => l.id === selLinkId);
          if (selectedEdge) {
            visibleLinkIds.add(selectedEdge.id);
            visibleNodeIds.add(selectedEdge.source);
            visibleNodeIds.add(selectedEdge.target);
            // Also include immediate neighbors of source/target for context
            const focusIds = new Set([selectedEdge.source, selectedEdge.target]);
            links.forEach((l) => {
              if (focusIds.has(l.source) || focusIds.has(l.target)) {
                visibleLinkIds!.add(l.id);
                visibleNodeIds!.add(l.source);
                visibleNodeIds!.add(l.target);
              }
            });
          }
        }
      }

      // Draw links + labels
      links.forEach((l) => {
        const src = nMap.get(l.source);
        const tgt = nMap.get(l.target);
        if (!src || !tgt) return;

        if (hasSelection && visibleLinkIds && !visibleLinkIds.has(l.id)) {
          return;
        }

        const isSelectedLink = l.id === selLinkId;
        const isConnectedToSelected = selId && (src.id === selId || tgt.id === selId);
        const srcHighlighted = !highlightType || src.entityType === highlightType;
        const tgtHighlighted = !highlightType || tgt.entityType === highlightType;
        let linkAlpha = 0.2;
        if (filteredIds) {
          linkAlpha = filteredIds.has(src.id) && filteredIds.has(tgt.id) ? 0.4 : 0.05;
        }
        if (highlightType) {
          // Only strongly show edges whose both endpoints match the highlight type
          linkAlpha = srcHighlighted && tgtHighlighted ? linkAlpha : linkAlpha * 0.25;
        }
        if (isConnectedToSelected) linkAlpha = 0.6;
        if (isSelectedLink) linkAlpha = 0.9;

        ctx.beginPath();
        ctx.moveTo(src.x, src.y);
        ctx.lineTo(tgt.x, tgt.y);
        ctx.strokeStyle = isSelectedLink
          ? 'rgba(255, 255, 255, 0.9)'
          : isConnectedToSelected
            ? `rgba(255, 255, 255, ${linkAlpha})`
            : `rgba(136, 146, 176, ${linkAlpha})`;
        ctx.lineWidth = (isSelectedLink ? 2.5 : isConnectedToSelected ? 1.5 : 0.8) / zoom;
        ctx.stroke();

        // Edge label
        if (l.relationshipType && zoom > 0.6) {
          const mx = (src.x + tgt.x) / 2;
          const my = (src.y + tgt.y) / 2;
          const fontSize = Math.max(8 / zoom, 2);
          ctx.font = `${isSelectedLink ? 'bold ' : ''}${fontSize}px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillStyle = isSelectedLink
            ? 'rgba(255, 255, 255, 0.95)'
            : isConnectedToSelected
              ? `rgba(255, 255, 255, 0.6)`
              : `rgba(136, 146, 176, ${linkAlpha * 1.5})`;
          ctx.fillText(l.relationshipType, mx, my);
        }
      });

      // Draw nodes
      nodes.forEach((n) => {
        if (hasSelection && visibleNodeIds && !visibleNodeIds.has(n.id)) {
          return;
        }

        const isSelected = n.id === selId;
        let nodeAlpha = 1;
        if (filteredIds && !filteredIds.has(n.id)) nodeAlpha = 0.15;
        if (highlightType && n.entityType !== highlightType && !isSelected) {
          nodeAlpha *= 0.25;
        }

        // Glow for selected node
        if (isSelected) {
          ctx.beginPath();
          ctx.arc(n.x, n.y, n.radius + 4 / zoom, 0, 2 * Math.PI);
          ctx.fillStyle = `rgba(255, 255, 255, 0.12)`;
          ctx.fill();
        }

        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius, 0, 2 * Math.PI);
        ctx.globalAlpha = nodeAlpha;
        ctx.fillStyle = n.color;
        ctx.fill();

        if (isSelected || (filteredIds && filteredIds.has(n.id))) {
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = (isSelected ? 2.5 : 2) / zoom;
          ctx.stroke();
        }

        ctx.globalAlpha = 1;

        // Node name label
        const showLabel = n.radius >= 8 || zoom > 1.5 || isSelected;
        if (showLabel && nodeAlpha > 0.3) {
          const fontSize = Math.max(10 / zoom, 2.5);
          ctx.font = `${isSelected ? 'bold ' : ''}${fontSize}px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'top';
          ctx.fillStyle = `rgba(255, 255, 255, ${isSelected ? 1 : nodeAlpha * 0.85})`;
          ctx.fillText(n.name, n.x, n.y + n.radius + 3 / zoom);
        }
      });

      ctx.restore();
    };

    const loop = () => {
      simulate();
      render();
      animRef.current = requestAnimationFrame(loop);
    };

    animRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animRef.current);
  }, [rawGraph, filteredIds, highlightType]);

  // Resize canvas
  useEffect(() => {
    const resize = () => {
      const canvas = canvasRef.current;
      const container = containerRef.current;
      if (!canvas || !container) return;
      const rect = container.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
    };
    resize();
    const observer = new ResizeObserver(resize);
    if (containerRef.current) observer.observe(containerRef.current);
    window.addEventListener('resize', resize);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', resize);
    };
  }, [rawGraph]);

  // Mouse interactions
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const screenToWorld = (sx: number, sy: number) => {
      const rect = canvas.getBoundingClientRect();
      const cx = rect.width / 2 + panRef.current.x;
      const cy = rect.height / 2 + panRef.current.y;
      return {
        x: (sx - rect.left - cx) / zoomRef.current,
        y: (sy - rect.top - cy) / zoomRef.current,
      };
    };

    const findNode = (wx: number, wy: number): SimNode | null => {
      const nodes = nodesRef.current;
      for (let i = nodes.length - 1; i >= 0; i--) {
        const n = nodes[i];
        const dx = n.x - wx;
        const dy = n.y - wy;
        if (dx * dx + dy * dy <= (n.radius + 4) * (n.radius + 4)) return n;
      }
      return null;
    };

    const LINK_HIT_THRESHOLD = 8;
    const findLink = (wx: number, wy: number): SimLink | null => {
      const nodes = nodesRef.current;
      const links = linksRef.current;
      const nMap = new Map<string, SimNode>();
      nodes.forEach((n) => nMap.set(n.id, n));
      let best: { link: SimLink; d: number } | null = null;
      for (const l of links) {
        const src = nMap.get(l.source);
        const tgt = nMap.get(l.target);
        if (!src || !tgt) continue;
        const d = distanceToSegment(wx, wy, src.x, src.y, tgt.x, tgt.y);
        if (d <= LINK_HIT_THRESHOLD && (!best || d < best.d)) best = { link: l, d };
      }
      return best ? best.link : null;
    };

    const onMouseDown = (e: MouseEvent) => {
      const { x, y } = screenToWorld(e.clientX, e.clientY);
      const node = findNode(x, y);
      const link = findLink(x, y);
      mouseDownPosRef.current = { x: e.clientX, y: e.clientY };
      didDragRef.current = false;
      clickedLinkRef.current = null;
      if (node) {
        dragNodeRef.current = node;
        node.pinned = true;
      } else if (link) {
        clickedLinkRef.current = link;
      } else {
        isPanningRef.current = true;
      }
    };

    const onMouseMove = (e: MouseEvent) => {
      if (mouseDownPosRef.current) {
        const dx = e.clientX - mouseDownPosRef.current.x;
        const dy = e.clientY - mouseDownPosRef.current.y;
        if (Math.abs(dx) > 3 || Math.abs(dy) > 3) didDragRef.current = true;
      }

      if (dragNodeRef.current) {
        const { x, y } = screenToWorld(e.clientX, e.clientY);
        dragNodeRef.current.x = x;
        dragNodeRef.current.y = y;
        dragNodeRef.current.vx = 0;
        dragNodeRef.current.vy = 0;
        canvas.style.cursor = 'grabbing';
      } else if (isPanningRef.current && mouseDownPosRef.current) {
        const dx = e.clientX - mouseDownPosRef.current.x;
        const dy = e.clientY - mouseDownPosRef.current.y;
        mouseDownPosRef.current = { x: e.clientX, y: e.clientY };
        panRef.current = {
          x: panRef.current.x + dx,
          y: panRef.current.y + dy,
        };
        canvas.style.cursor = 'move';
      } else {
        const { x, y } = screenToWorld(e.clientX, e.clientY);
        const node = findNode(x, y);
        const link = findLink(x, y);
        if (node) {
          canvas.style.cursor = 'pointer';
          setHoveredNode(node);
          setHoveredLink(null);
          setTooltipPos({ x: e.clientX, y: e.clientY });
        } else if (link) {
          canvas.style.cursor = 'pointer';
          setHoveredNode(null);
          setHoveredLink(link);
          setLinkTooltipPos({ x: e.clientX, y: e.clientY });
        } else {
          canvas.style.cursor = 'default';
          setHoveredNode(null);
          setHoveredLink(null);
        }
      }
    };

    const onMouseUp = () => {
      const wasDrag = didDragRef.current;
      const dragged = dragNodeRef.current;
      const clickedLink = clickedLinkRef.current;

      if (dragged) {
        dragged.pinned = false;
        dragNodeRef.current = null;
        clickedLinkRef.current = null;
        if (!wasDrag) {
          setSelectedNode(dragged);
          setSelectedLink(null);
        }
      } else if (clickedLink && !wasDrag) {
        setSelectedLink(clickedLink);
        setSelectedNode(null);
        clickedLinkRef.current = null;
      } else if (!wasDrag && isPanningRef.current) {
        setSelectedNode(null);
        setSelectedLink(null);
      }
      clickedLinkRef.current = null;
      isPanningRef.current = false;
      mouseDownPosRef.current = null;
      didDragRef.current = false;
      canvas.style.cursor = 'default';
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const factor = e.deltaY > 0 ? 0.92 : 1.08;
      zoomRef.current = Math.max(0.1, Math.min(10, zoomRef.current * factor));
    };

    canvas.addEventListener('mousedown', onMouseDown);
    canvas.addEventListener('mousemove', onMouseMove);
    canvas.addEventListener('mouseup', onMouseUp);
    canvas.addEventListener('mouseleave', () => {
      if (dragNodeRef.current) { dragNodeRef.current.pinned = false; dragNodeRef.current = null; }
      isPanningRef.current = false;
      mouseDownPosRef.current = null;
      clickedLinkRef.current = null;
      canvas.style.cursor = 'default';
      setHoveredNode(null);
      setHoveredLink(null);
    });
    canvas.addEventListener('wheel', onWheel, { passive: false });

    return () => {
      canvas.removeEventListener('mousedown', onMouseDown);
      canvas.removeEventListener('mousemove', onMouseMove);
      canvas.removeEventListener('mouseup', onMouseUp);
      canvas.removeEventListener('wheel', onWheel);
    };
  }, [rawGraph]);

  useEffect(() => {
    if (!showFilterDropdown) return;
    const handler = (e: MouseEvent) => {
      if (!(e.target as HTMLElement).closest('.kg-filter-wrapper')) setShowFilterDropdown(false);
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [showFilterDropdown]);

  const nodeCount = nodesRef.current.length;
  const linkCount = linksRef.current.length;

  if (loading) {
    return (
      <div className="kg-container">
        <div className="kg-loading">
          <div className="kg-loading-spinner" />
          <span>Loading knowledge graph...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="kg-container">
        <div className="kg-error">
          <span>Failed to load graph: {error}</span>
          <button onClick={loadGraph} className="kg-retry-btn">Retry</button>
        </div>
      </div>
    );
  }

  if (!rawGraph || rawGraph.nodes.length === 0) {
    return (
      <div className="kg-container">
        <div className="kg-empty">No knowledge graph data available.</div>
      </div>
    );
  }

  return (
    <div className="kg-container" ref={containerRef}>
      <canvas ref={canvasRef} className="kg-canvas" />

      {/* Legend Panel */}
      <div className={`kg-legend ${legendCollapsed ? 'collapsed' : ''}`}>
        <button className="kg-legend-header" onClick={() => setLegendCollapsed(!legendCollapsed)}>
          {legendCollapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
          <span>Entity Types</span>
        </button>
        {!legendCollapsed && (
          <div className="kg-legend-items">
            {entityTypes.map((type) => (
              <button
                key={type}
                type="button"
                className={`kg-legend-item ${highlightType === type ? 'active' : ''}`}
                onClick={() =>
                  setHighlightType((prev) => (prev === type ? null : type))
                }
              >
                <span className="kg-legend-dot" style={{ backgroundColor: getEntityColor(type) }} />
                <span className="kg-legend-label">{capitalizeFirst(type)}</span>
              </button>
            ))}
            {highlightType && (
              <button
                type="button"
                className="kg-legend-clear"
                onClick={() => setHighlightType(null)}
              >
                × Clear highlight
              </button>
            )}
          </div>
        )}
      </div>

      {/* Toolbar */}
      <div className="kg-toolbar">
        <div className="kg-search-wrapper">
          <Search size={14} className="kg-search-icon" />
          <input
            type="text"
            className="kg-search-input"
            placeholder="Search graph"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <div className="kg-filter-wrapper">
          <button
            className="kg-filter-btn"
            onClick={(e) => { e.stopPropagation(); setShowFilterDropdown(!showFilterDropdown); }}
          >
            <span>{filterType}</span>
            <ChevronDown size={14} />
          </button>
          {showFilterDropdown && (
            <div className="kg-filter-dropdown">
              {(['All', 'Entities', 'Edges', 'Facts'] as FilterType[]).map((type) => (
                <button
                  key={type}
                  className={`kg-filter-option ${filterType === type ? 'active' : ''}`}
                  onClick={() => { setFilterType(type); setShowFilterDropdown(false); }}
                >
                  {type}
                  {filterType === type && <span className="kg-filter-check">✓</span>}
                </button>
              ))}
            </div>
          )}
        </div>
        <button className="kg-help-btn" onClick={() => setShowHelp(!showHelp)} title="Help">
          <HelpCircle size={18} />
        </button>
      </div>

      {/* Help Panel */}
      {showHelp && (
        <div className="kg-help-panel">
          <h4>Knowledge Graph</h4>
          <ul>
            <li>Scroll to zoom in/out</li>
            <li>Drag background to pan</li>
            <li>Drag nodes to rearrange</li>
            <li>Click a node or edge for details</li>
            <li>Use search to highlight nodes</li>
          </ul>
          <button className="kg-help-close" onClick={() => setShowHelp(false)}>Got it</button>
        </div>
      )}

      {/* Node Details Panel */}
      {selectedNode && (
        <div className="kg-detail-panel">
          <div className="kg-detail-header">
            <h3 className="kg-detail-title">Node Details</h3>
            <span
              className="kg-detail-type-badge"
              style={{ backgroundColor: selectedNode.color }}
            >
              {capitalizeFirst(selectedNode.entityType)}
            </span>
            <button
              className="kg-detail-close"
              onClick={() => setSelectedNode(null)}
            >
              <X size={16} />
            </button>
          </div>

          <div className="kg-detail-body">
            <div className="kg-detail-field">
              <span className="kg-detail-label">Name:</span>
              <span className="kg-detail-value">{selectedNode.name}</span>
            </div>

            <div className="kg-detail-field">
              <span className="kg-detail-label">UUID:</span>
              <span className="kg-detail-value kg-detail-uuid">{selectedNode.id}</span>
            </div>

            {selectedNode.createdAt && (
              <div className="kg-detail-field">
                <span className="kg-detail-label">Created:</span>
                <span className="kg-detail-value">{formatTimestamp(selectedNode.createdAt)}</span>
              </div>
            )}

            {selectedNode.description && (
              <div className="kg-detail-field kg-detail-field-block">
                <span className="kg-detail-label">Summary:</span>
                <p className="kg-detail-summary">{selectedNode.description}</p>
              </div>
            )}

            {selectedNode.labels.length > 0 && (
              <div className="kg-detail-field kg-detail-field-block">
                <span className="kg-detail-label">Labels:</span>
                <div className="kg-detail-labels">
                  {selectedNode.labels.map((label) => (
                    <span key={label} className="kg-detail-label-tag">{label}</span>
                  ))}
                </div>
              </div>
            )}

            <div className="kg-detail-field">
              <span className="kg-detail-label">Connections:</span>
              <span className="kg-detail-value">{selectedNode.connections}</span>
            </div>
          </div>
        </div>
      )}

      {/* Edge Details Panel - 按图样式：顶部摘要 + Relationship，仅展示有值的字段 */}
      {selectedLink && (() => {
        const sourceName = nodesRef.current.find((n) => n.id === selectedLink.source)?.name ?? selectedLink.source;
        const targetName = nodesRef.current.find((n) => n.id === selectedLink.target)?.name ?? selectedLink.target;
        const label = selectedLink.relationshipType;
        return (
          <div className="kg-detail-panel kg-edge-detail-panel">
            <div className="kg-detail-header kg-edge-detail-header">
              <h3 className="kg-detail-title">Relationship</h3>
              <button
                className="kg-detail-close"
                onClick={() => setSelectedLink(null)}
              >
                <X size={16} />
              </button>
            </div>

            <div className="kg-edge-summary-box">
              {sourceName} → {label || '—'} → {targetName}
            </div>

            <div className="kg-detail-body">
              <div className="kg-detail-field">
                <span className="kg-detail-label">UUID:</span>
                <span className="kg-detail-value kg-detail-uuid">{selectedLink.id}</span>
              </div>

              {label != null && String(label).trim() !== '' && (
                <div className="kg-detail-field">
                  <span className="kg-detail-label">Label:</span>
                  <span className="kg-detail-value">{label}</span>
                </div>
              )}

              {selectedLink.fact != null && String(selectedLink.fact).trim() !== '' && (
                <div className="kg-detail-field kg-detail-field-block">
                  <span className="kg-detail-label">Fact:</span>
                  <p className="kg-detail-summary">{selectedLink.fact}</p>
                </div>
              )}

              {selectedLink.episodes != null && String(selectedLink.episodes).trim() !== '' && (
                <div className="kg-detail-field">
                  <span className="kg-detail-label">Episodes:</span>
                  <span className="kg-detail-value kg-detail-uuid">{selectedLink.episodes}</span>
                </div>
              )}

              {selectedLink.createdAt != null && (
                <div className="kg-detail-field">
                  <span className="kg-detail-label">Created:</span>
                  <span className="kg-detail-value">{formatTimestamp(selectedLink.createdAt)}</span>
                </div>
              )}

              {selectedLink.validFrom != null && (
                <div className="kg-detail-field">
                  <span className="kg-detail-label">Valid From:</span>
                  <span className="kg-detail-value">{formatTimestamp(selectedLink.validFrom)}</span>
                </div>
              )}

              {selectedLink.description != null && String(selectedLink.description).trim() !== '' && selectedLink.description !== selectedLink.fact && (
                <div className="kg-detail-field kg-detail-field-block">
                  <span className="kg-detail-label">Description:</span>
                  <p className="kg-detail-summary">{selectedLink.description}</p>
                </div>
              )}

              {selectedLink.weight != null && (
                <div className="kg-detail-field">
                  <span className="kg-detail-label">Weight:</span>
                  <span className="kg-detail-value">{selectedLink.weight}</span>
                </div>
              )}

              {selectedLink.keywords != null && String(selectedLink.keywords).trim() !== '' && (
                <div className="kg-detail-field kg-detail-field-block">
                  <span className="kg-detail-label">Keywords:</span>
                  <span className="kg-detail-value">{selectedLink.keywords}</span>
                </div>
              )}

              {selectedLink.filePath != null && String(selectedLink.filePath).trim() !== '' && (
                <div className="kg-detail-field">
                  <span className="kg-detail-label">File:</span>
                  <span className="kg-detail-value kg-detail-uuid">{selectedLink.filePath}</span>
                </div>
              )}
            </div>
          </div>
        );
      })()}

      {/* Hover Tooltip - Node */}
      {hoveredNode && !selectedNode && !selectedLink && (
        <div className="kg-tooltip" style={{ left: tooltipPos.x + 12, top: tooltipPos.y - 12 }}>
          <div className="kg-tooltip-name">{hoveredNode.name}</div>
          <div className="kg-tooltip-type">
            <span className="kg-tooltip-dot" style={{ backgroundColor: hoveredNode.color }} />
            {capitalizeFirst(hoveredNode.entityType)}
          </div>
          {hoveredNode.description && (
            <div className="kg-tooltip-desc">{hoveredNode.description}</div>
          )}
        </div>
      )}

      {/* Hover Tooltip - Link */}
      {hoveredLink && !selectedLink && (
        <div className="kg-tooltip" style={{ left: linkTooltipPos.x + 12, top: linkTooltipPos.y - 12 }}>
          <div className="kg-tooltip-name">{hoveredLink.relationshipType || 'Edge'}</div>
          {hoveredLink.description && (
            <div className="kg-tooltip-desc">{hoveredLink.description}</div>
          )}
        </div>
      )}

      {/* Stats */}
      <div className="kg-stats">
        {nodeCount} nodes · {linkCount} edges
        {rawGraph.is_truncated && <span className="kg-truncated"> (truncated)</span>}
      </div>
    </div>
  );
}
