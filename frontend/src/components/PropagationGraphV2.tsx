import { useEffect, useRef, useState, useCallback } from "react";
import cytoscape, { Core, EventObject } from "cytoscape";
import { ZoomIn, ZoomOut, Maximize2, GitBranch, Clock } from "lucide-react";

// ── Reuse existing data interfaces from PropagationGraph ──

interface GraphNode {
  id: string;
  label: string;
  platform: string;
  url: string;
  is_original: boolean;
  authority_score: number;
  engagement?: Record<string, number>;
  published_at?: string;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;       // repost | quote | reference | causal
  weight: number;
  causal_type?: string; // CAUSES | ENABLES | PREVENTS | SUPPORTS | CONTRADICTS | CORRELATES_WITH
}

interface PropagationGraphV2Props {
  data: {
    nodes: GraphNode[];
    edges: GraphEdge[];
  };
  height?: number;
  showTimeline?: boolean;
}

const PLATFORM_COLORS: Record<string, string> = {
  weibo: "#E6162D",
  zhihu: "#0084FF",
  wechat: "#07C160",
  twitter: "#1DA1F2",
  reddit: "#FF4500",
  news: "#10B981",
  general: "#6B7280",
  unknown: "#9CA3AF",
  xiaohongshu: "#FF2442",
  douyin: "#000000",
  kuaishou: "#FF5000",
  bilibili: "#FB7299",
  youtube: "#FF0000",
};

const EDGE_STYLES: Record<string, { color: string; dash: number[]; width: number }> = {
  repost: { color: "#EF4444", dash: [], width: 2 },
  quote: { color: "#F59E0B", dash: [6, 3], width: 1.5 },
  reference: { color: "#3B82F6", dash: [], width: 1.5 },
  causal: { color: "#8B5CF6", dash: [4, 4], width: 2 },
  supports: { color: "#10B981", dash: [], width: 1.5 },
  contradicts: { color: "#EF4444", dash: [8, 3, 2, 3], width: 2 },
};

export function PropagationGraphV2({
  data,
  height = 560,
  showTimeline = false,
}: PropagationGraphV2Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [viewMode, setViewMode] = useState<"force" | "tree" | "timeline">("force");

  // ── Initialize Cytoscape ──
  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      style: [
        // Node styles
        {
          selector: "node",
          style: {
            "background-color": "#6B7280",
            label: "data(label)",
            "text-valign": "bottom",
            "text-halign": "center",
            "font-size": "11px",
            "font-family": "'Noto Sans SC', Inter, sans-serif",
            color: "#374151",
            "text-wrap": "ellipsis",
            "text-max-width": "100px",
            width: 24,
            height: 24,
            "border-width": 2,
            "border-color": "#fff",
            "transition-property": "background-color, width, height",
            "transition-duration": 250,
          },
        },
        // Platform colors
        ...Object.entries(PLATFORM_COLORS).map(([platform, color]) => ({
          selector: `node[platform="${platform}"]`,
          style: { "background-color": color },
        })),
        // Original source highlight
        {
          selector: "node[is_original=true]",
          style: {
            width: 34,
            height: 34,
            "border-width": 4,
            "border-color": "#F59E0B",
            "border-style": "double",
          },
        },
        // Edge styles
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "#9CA3AF",
            "target-arrow-color": "#9CA3AF",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.8,
            "curve-style": "bezier",
            "transition-property": "line-color, width",
            "transition-duration": 250,
          },
        },
        ...Object.entries(EDGE_STYLES).map(([type, style]) => ({
          selector: type === "causal" ? `edge[causal_type]` : `edge[type="${type}"]`,
          style: {
            "line-color": style.color,
            "target-arrow-color": style.color,
            width: style.width,
            "line-style": style.dash.length > 0 ? "dashed" : "solid",
            ...(style.dash.length > 0 ? { "line-dash-pattern": style.dash as any } : {}),
          },
        })),
        // Highlighted elements
        {
          selector: ".highlighted",
          style: {
            "border-color": "#3B82F6",
            "border-width": 3,
          },
        },
        {
          selector: ".dimmed",
          style: {
            opacity: 0.2,
          },
        },
      ],
      layout: viewMode === "tree"
        ? { name: "breadthfirst", directed: true, spacingFactor: 1.3 }
        : { name: "cose", animate: true, nodeRepulsion: () => 6000, idealEdgeLength: () => 120 },
      wheelSensitivity: 0.3,
      minZoom: 0.15,
      maxZoom: 4,
    });

    cyRef.current = cy;

    // Cleanup
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, []);

  // ── Update graph data ──
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !data.nodes.length) return;

    // Remove old elements
    cy.elements().remove();

    // Add nodes
    data.nodes.forEach((n) => {
      cy.add({
        group: "nodes",
        data: {
          id: n.id,
          label: n.label.length > 20 ? n.label.slice(0, 20) + "…" : n.label,
          fullLabel: n.label,
          platform: n.platform || "unknown",
          url: n.url,
          is_original: n.is_original,
          authority_score: n.authority_score,
          engagement: n.engagement,
          published_at: n.published_at,
        },
      });
    });

    // Add edges
    data.edges.forEach((e) => {
      cy.add({
        group: "edges",
        data: {
          id: e.id,
          source: e.source,
          target: e.target,
          type: e.type,
          weight: e.weight,
          causal_type: e.causal_type,
        },
      });
    });

    // Apply layout
    const layoutName = viewMode === "tree" ? "breadthfirst" : "cose";
    cy.layout(
      layoutName === "breadthfirst"
        ? { name: "breadthfirst", directed: true, spacingFactor: 1.3, animate: true }
        : { name: "cose", animate: true, nodeRepulsion: () => 6000, idealEdgeLength: () => 120 }
    ).run();
  }, [data, viewMode]);

  // ── Node click handler ──
  const handleNodeClick = useCallback((cy: Core, nodeId: string) => {
    const node = data.nodes.find((n) => n.id === nodeId);
    if (!node) return;

    setSelectedNode(node);

    // Highlight connected nodes
    const connected = new Set<string>();
    connected.add(nodeId);
    cy.edges().forEach((edge) => {
      const src = edge.data("source") as string;
      const tgt = edge.data("target") as string;
      if (src === nodeId) connected.add(tgt);
      if (tgt === nodeId) connected.add(src);
    });

    cy.nodes().forEach((n) => {
      const id = n.data("id") as string;
      if (connected.has(id)) {
        n.removeClass("dimmed").addClass("highlighted");
      } else {
        n.removeClass("highlighted").addClass("dimmed");
      }
    });
    cy.edges().forEach((e) => {
      const src = e.data("source") as string;
      const tgt = e.data("target") as string;
      if (src === nodeId || tgt === nodeId) {
        e.removeClass("dimmed");
      } else {
        e.addClass("dimmed");
      }
    });
  }, [data.nodes]);

  // ── Cytoscape event binding ──
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    const onTap = (evt: EventObject) => {
      const target = evt.target;
      if (target.isNode()) {
        const nodeId = target.data("id") as string;
        handleNodeClick(cy, nodeId);
      } else {
        // Click background — reset
        setSelectedNode(null);
        cy.nodes().forEach((n) => { n.removeClass("highlighted").removeClass("dimmed"); });
        cy.edges().forEach((e) => { e.removeClass("dimmed"); });
      }
    };

    cy.on("tap", onTap);
    return () => {
      cy.off("tap", onTap);
    };
  }, [handleNodeClick]);

  // ── Control handlers ──
  const zoomIn = () => {
    const cy = cyRef.current;
    if (cy) cy.zoom(cy.zoom() * 1.3);
  };
  const zoomOut = () => {
    const cy = cyRef.current;
    if (cy) cy.zoom(cy.zoom() * 0.7);
  };
  const resetView = () => {
    const cy = cyRef.current;
    if (cy) {
      cy.fit(undefined, 50);
      cy.center();
    }
  };
  const toggleView = () => {
    setViewMode((prev) => (prev === "force" ? "tree" : "force"));
  };

  return (
    <div className="relative rounded-lg border bg-white dark:bg-gray-900 overflow-hidden">
      {/* Toolbar */}
      <div className="absolute top-3 right-3 z-10 flex items-center gap-1">
        <button
          onClick={toggleView}
          className="p-1.5 rounded-md bg-white/90 dark:bg-gray-800/90 shadow-sm border hover:bg-gray-100 transition-colors"
          title={viewMode === "force" ? "切换到树形布局" : "切换到力导向布局"}
        >
          <GitBranch size={15} className="text-gray-600" />
        </button>
        {showTimeline && (
          <button
            onClick={() => setViewMode((p) => (p === "timeline" ? "force" : "timeline"))}
            className={`p-1.5 rounded-md shadow-sm border transition-colors ${
              viewMode === "timeline"
                ? "bg-blue-100 dark:bg-blue-900 border-blue-300"
                : "bg-white/90 dark:bg-gray-800/90 hover:bg-gray-100"
            }`}
            title="时间线视图"
          >
            <Clock size={15} className="text-gray-600" />
          </button>
        )}
        <div className="w-px h-5 bg-gray-300 mx-1" />
        <button
          onClick={zoomIn}
          className="p-1.5 rounded-md bg-white/90 dark:bg-gray-800/90 shadow-sm border hover:bg-gray-100 transition-colors"
          title="放大"
        >
          <ZoomIn size={15} className="text-gray-600" />
        </button>
        <button
          onClick={zoomOut}
          className="p-1.5 rounded-md bg-white/90 dark:bg-gray-800/90 shadow-sm border hover:bg-gray-100 transition-colors"
          title="缩小"
        >
          <ZoomOut size={15} className="text-gray-600" />
        </button>
        <button
          onClick={resetView}
          className="p-1.5 rounded-md bg-white/90 dark:bg-gray-800/90 shadow-sm border hover:bg-gray-100 transition-colors"
          title="适应视图"
        >
          <Maximize2 size={15} className="text-gray-600" />
        </button>
      </div>

      {/* Cytoscape container */}
      <div
        ref={containerRef}
        style={{ width: "100%", height: `${height}px` }}
        className="bg-gray-50 dark:bg-gray-950"
      />

      {/* Info panel for selected node */}
      {selectedNode && (
        <div className="absolute bottom-4 left-4 z-10 bg-white/95 dark:bg-gray-800/95 rounded-lg shadow-lg border p-3 max-w-xs text-sm">
          <div className="flex items-center gap-2 mb-1.5">
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{
                backgroundColor:
                  PLATFORM_COLORS[selectedNode.platform] || PLATFORM_COLORS.unknown,
              }}
            />
            <span className="font-medium truncate">
              {selectedNode.label}
            </span>
            {selectedNode.is_original && (
              <span className="text-[10px] bg-amber-100 text-amber-700 px-1 rounded">
                原始
              </span>
            )}
          </div>
          <div className="text-gray-500 dark:text-gray-400 space-y-0.5">
            <div>平台: {selectedNode.platform || "未知"}</div>
            <div>权威度: {selectedNode.authority_score}</div>
            {selectedNode.url && (
              <a
                href={selectedNode.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-500 hover:underline truncate block"
              >
                {selectedNode.url.slice(0, 60)}…
              </a>
            )}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-4 right-4 z-10 bg-white/90 dark:bg-gray-800/90 rounded-lg shadow-sm border px-2.5 py-1.5 text-[11px] text-gray-500 space-y-1">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-0.5 bg-amber-500 inline-block" />
          原始来源
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-0.5 bg-red-500 inline-block" />
          转发
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-0.5 bg-blue-500 inline-block" />
          引用
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-0.5 bg-purple-500 inline-block" style={{ borderTop: "1.5px dashed #8B5CF6" }} />
          因果
        </div>
      </div>
    </div>
  );
}

export default PropagationGraphV2;
