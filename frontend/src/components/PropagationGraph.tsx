import { useEffect, useRef, useState, useCallback } from "react";
import * as d3 from "d3";
import { ZoomIn, ZoomOut, Maximize2, Crosshair } from "lucide-react";

// Helper: extract node id from d3 link source/target (string | SimulationNodeDatum)
function nodeId(obj: string | number | GraphNode): string {
  if (typeof obj === "object" && obj !== null && "id" in obj) return (obj as GraphNode).id;
  return String(obj);
}

interface GraphNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  platform: string;
  url: string;
  is_original: boolean;
  authority_score: number;
  engagement?: Record<string, number>;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  weight: number;
}

interface PropagationGraphProps {
  data: {
    nodes: GraphNode[];
    edges: GraphEdge[];
  };
  height?: number;
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
};

const EDGE_COLORS: Record<string, string> = {
  repost: "#EF4444",
  quote: "#F59E0B",
  reference: "#3B82F6",
};

export function PropagationGraph({ data, height = 520 }: PropagationGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [highlighted, setHighlighted] = useState<Set<string>>(new Set());
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const simulationRef = useRef<d3.Simulation<GraphNode, d3.SimulationLinkDatum<GraphNode>> | null>(null);

  // Find connected nodes to a selected node
  const getConnectedNodes = useCallback(
    (nodeId: string, edges: GraphEdge[]): Set<string> => {
      const connected = new Set<string>([nodeId]);
      edges.forEach((e) => {
        const src = typeof e.source === "string" ? e.source : (e.source as any)?.id;
        const tgt = typeof e.target === "string" ? e.target : (e.target as any)?.id;
        if (src === nodeId) connected.add(tgt as string);
        if (tgt === nodeId) connected.add(src as string);
      });
      return connected;
    },
    []
  );

  const handleZoomIn = () => {
    if (!svgRef.current || !zoomRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.transition().duration(300).call(zoomRef.current.scaleBy, 1.5);
  };

  const handleZoomOut = () => {
    if (!svgRef.current || !zoomRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.transition().duration(300).call(zoomRef.current.scaleBy, 0.7);
  };

  const handleReset = () => {
    if (!svgRef.current || !zoomRef.current) return;
    const svg = d3.select(svgRef.current);
    const width = svgRef.current.clientWidth;
    svg
      .transition()
      .duration(500)
      .call(zoomRef.current.transform, d3.zoomIdentity.translate(width / 2, height / 2));
    setSelectedNode(null);
    setHighlighted(new Set());
  };

  useEffect(() => {
    if (!svgRef.current || !data.nodes.length) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const width = svgRef.current.clientWidth || 800;
    const aspectHeight = height;

    svg.attr("viewBox", `0 0 ${width} ${aspectHeight}`).attr("preserveAspectRatio", "xMidYMid meet");

    // Main container group for zoom/pan
    const g = svg.append("g");

    // Zoom behavior
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 5])
      .on("zoom", (event) => {
        g.attr("transform", event.transform.toString());
      });

    svg.call(zoom);
    // Initial transform: center the graph
    svg.call(zoom.transform, d3.zoomIdentity.translate(width / 2, aspectHeight / 2));
    zoomRef.current = zoom;

    // Create simulation
    const simulation = d3
      .forceSimulation<GraphNode>(data.nodes)
      .force(
        "link",
        d3
          .forceLink<GraphNode, d3.SimulationLinkDatum<GraphNode>>(data.edges)
          .id((d: any) => d.id)
          .distance((d: any) => 120 / Math.max(0.5, d.weight))
      )
      .force("charge", d3.forceManyBody().strength(-400))
      .force("center", d3.forceCenter(0, 0))
      .force("collision", d3.forceCollide<GraphNode>().radius((d) => (d.is_original ? 30 : 20)))
      .force("x", d3.forceX(0).strength(0.02))
      .force("y", d3.forceY(0).strength(0.02));

    simulationRef.current = simulation;

    // --- Draw edges ---
    const linkGroup = g.append("g").attr("class", "links");

    const link = linkGroup
      .selectAll<SVGLineElement, GraphEdge>("line")
      .data(data.edges)
      .join("line")
      .attr("stroke", (d) => EDGE_COLORS[d.type] || "#999")
      .attr("stroke-width", (d) => Math.max(1, d.weight * 3))
      .attr("stroke-opacity", 0.5)
      .attr("stroke-linecap", "round")
      .attr("class", (d) => `edge edge-${d.id}`);

    // Edge arrows
    const defs = svg.append("defs");
    Object.entries(EDGE_COLORS).forEach(([type, color]) => {
      defs
        .append("marker")
        .attr("id", `arrow-${type}`)
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 22)
        .attr("refY", 0)
        .attr("markerWidth", 6)
        .attr("markerHeight", 6)
        .attr("orient", "auto")
        .append("path")
        .attr("d", "M0,-5L10,0L0,5")
        .attr("fill", color)
        .attr("opacity", 0.5);
    });

    link.attr("marker-end", (d) => `url(#arrow-${d.type})`);

    // --- Draw nodes ---
    const nodeGroup = g.append("g").attr("class", "nodes");

    const node = nodeGroup
      .selectAll<SVGGElement, GraphNode>("g")
      .data(data.nodes)
      .join("g")
      .attr("class", (d) => `node node-${d.id}`)
      .style("cursor", "pointer")
      .call(
        d3
          .drag<SVGGElement, GraphNode>()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }) as any
      );

    // Node circles
    node
      .append("circle")
      .attr("r", (d) => (d.is_original ? 18 : 10))
      .attr("fill", (d) => PLATFORM_COLORS[d.platform] || PLATFORM_COLORS.general)
      .attr("stroke", (d) => (d.is_original ? "#FBBF24" : "var(--background, #fff)"))
      .attr("stroke-width", (d) => (d.is_original ? 3 : 2))
      .attr("opacity", 0.9)
      .attr("class", (d) => `node-circle node-circle-${d.id}`);

    // Pulsing ring for original sources
    node
      .filter((d) => d.is_original)
      .append("circle")
      .attr("r", 22)
      .attr("fill", "none")
      .attr("stroke", "#FBBF24")
      .attr("stroke-width", 1.5)
      .attr("stroke-dasharray", "4 2")
      .attr("opacity", 0.6)
      .append("animate")
      .attr("attributeName", "opacity")
      .attr("values", "0.6;0.1;0.6")
      .attr("dur", "2s")
      .attr("repeatCount", "indefinite");

    // Labels
    node
      .append("text")
      .text((d) => d.label.slice(0, 10))
      .attr("dx", 22)
      .attr("dy", 4)
      .attr("font-size", "11px")
      .attr("font-family", "system-ui, sans-serif")
      .attr("fill", "currentColor")
      .attr("class", "fill-muted-foreground dark:fill-gray-400");

    // Original source star icon
    node
      .filter((d) => d.is_original)
      .append("text")
      .text("⭐")
      .attr("dx", -7)
      .attr("dy", -20)
      .attr("font-size", "12px")
      .style("pointer-events", "none");

    // Tooltip (title)
    node.append("title").text(
      (d) =>
        `${d.label}\n平台: ${d.platform}\n${d.is_original ? "🎯 疑似原始来源\n" : ""}权威度: ${d.authority_score.toFixed(1)}`
    );

    // Click handler: highlight connected nodes
    node.on("click", (event, d: GraphNode) => {
      event.stopPropagation();

      if (selectedNode?.id === d.id) {
        // Deselect
        setSelectedNode(null);
        setHighlighted(new Set());
        g.selectAll<SVGGElement, GraphNode>(".node").style("opacity", "1");
        link.attr("stroke-opacity", 0.5);
      } else {
        const connected = getConnectedNodes(d.id, data.edges);
        setSelectedNode(d);
        setHighlighted(connected);

        // Highlight connected, dim others
        g.selectAll<SVGGElement, GraphNode>(".node").style("opacity", (n: GraphNode) =>
          connected.has(n.id) ? "1" : "0.15"
        );
        link.attr("stroke-opacity", (l: GraphEdge) => {
          const src = nodeId(l.source); const tgt = nodeId(l.target);
          return connected.has(src) && connected.has(tgt) ? "0.9" : "0.05";
        });
        link.attr("stroke-width", (l: GraphEdge) => {
          const src = nodeId(l.source); const tgt = nodeId(l.target);
          return connected.has(src) && connected.has(tgt) ? Math.max(2, (l.weight || 1) * 4) : Math.max(0.5, (l.weight || 1) * 2);
        });
      }
    });

    // Click background to deselect
    svg.on("click", () => {
      setSelectedNode(null);
      setHighlighted(new Set());
      g.selectAll<SVGGElement, GraphNode>(".node").style("opacity", "1");
      link.attr("stroke-opacity", 0.5).attr("stroke-width", (d) => Math.max(0.5, (d.weight || 1) * 3));
    });

    // Simulation tick
    simulation.on("tick", () => {
      link
        .attr("x1", (d: any) => d.source.x)
        .attr("y1", (d: any) => d.source.y)
        .attr("x2", (d: any) => d.target.x)
        .attr("y2", (d: any) => d.target.y);

      node.attr("transform", (d: any) => `translate(${d.x},${d.y})`);
    });

    // Warm up + cool down
    simulation.alpha(1).restart();
    setTimeout(() => simulation.alphaTarget(0), 3000);

    return () => {
      simulation.stop();
    };
  }, [data, height]);

  // Re-apply highlights when selectedNode/edges change externally
  useEffect(() => {
    if (!svgRef.current || !selectedNode || highlighted.size === 0) return;
    const svg = d3.select(svgRef.current);
    const g = svg.select("g"); // main zoom group

    g.selectAll<SVGGElement, GraphNode>(".node").style("opacity", (d) =>
      highlighted.has(d.id) ? "1" : "0.15"
    );
    g.selectAll<SVGLineElement, GraphEdge>("line").attr("stroke-opacity", (d) => {
      const src = nodeId(d.source); const tgt = nodeId(d.target);
      return highlighted.has(src) && highlighted.has(tgt) ? "0.9" : "0.05";
    });
  }, [highlighted, selectedNode]);

  if (!data.nodes.length) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground text-sm">
        暂无传播图数据
      </div>
    );
  }

  return (
    <div className="propagation-graph relative" ref={containerRef}>
      {/* Zoom controls */}
      <div className="absolute top-3 right-3 z-10 flex gap-1">
        <button
          onClick={handleZoomIn}
          className="p-1.5 rounded-md bg-card border hover:bg-accent transition-colors"
          title="放大"
        >
          <ZoomIn className="h-4 w-4" />
        </button>
        <button
          onClick={handleZoomOut}
          className="p-1.5 rounded-md bg-card border hover:bg-accent transition-colors"
          title="缩小"
        >
          <ZoomOut className="h-4 w-4" />
        </button>
        <button
          onClick={handleReset}
          className="p-1.5 rounded-md bg-card border hover:bg-accent transition-colors"
          title="重置视图"
        >
          <Maximize2 className="h-4 w-4" />
        </button>
      </div>

      {/* Selected node info */}
      {selectedNode && (
        <div className="absolute top-3 left-3 z-10 p-3 rounded-lg bg-card border shadow-md max-w-xs">
          <div className="flex items-center gap-2 mb-1">
            <span
              className="inline-block w-3 h-3 rounded-full"
              style={{ backgroundColor: PLATFORM_COLORS[selectedNode.platform] || PLATFORM_COLORS.general }}
            />
            <span className="text-xs font-medium capitalize">{selectedNode.platform}</span>
            {selectedNode.is_original && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-yellow-100 text-yellow-800">
                🎯 原始来源
              </span>
            )}
          </div>
          <p className="text-sm font-medium truncate">{selectedNode.label}</p>
          <p className="text-xs text-muted-foreground">
            权威度: {selectedNode.authority_score.toFixed(1)}
            {selectedNode.engagement && (
              <>
                {" "}| 互动: {Object.values(selectedNode.engagement).reduce((a, b) => a + b, 0)}
              </>
            )}
          </p>
          {selectedNode.url && (
            <a
              href={selectedNode.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-primary hover:underline truncate block mt-1"
            >
              {selectedNode.url.slice(0, 60)}...
            </a>
          )}
        </div>
      )}

      <svg ref={svgRef} className="w-full" style={{ minHeight: height, cursor: "grab" }} />

      {/* Legend */}
      <div className="flex flex-wrap gap-4 p-4 text-xs text-muted-foreground border-t bg-card">
        {Object.entries(PLATFORM_COLORS)
          .filter(([k]) => k !== "general" && k !== "unknown")
          .map(([platform, color]) => (
            <div key={platform} className="flex items-center gap-1">
              <span className="inline-block w-3 h-3 rounded-full" style={{ backgroundColor: color }} />{" "}
              {platform === "weibo" ? "微博" :
               platform === "zhihu" ? "知乎" :
               platform === "wechat" ? "微信" :
               platform === "twitter" ? "Twitter" :
               platform === "reddit" ? "Reddit" : platform}
            </div>
          ))}
        <span className="mx-1">|</span>
        <span>⭐ = 原始来源</span>
        <span className="mx-1">|</span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-0.5 bg-[#EF4444]" /> 转发
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-0.5 bg-[#F59E0B]" /> 引用
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-0.5 bg-[#3B82F6]" /> 参考
        </span>
        <span className="mx-1">|</span>
        <span>🖱 点击节点高亮传播链 | 拖拽移动 | 滚轮缩放</span>
      </div>
    </div>
  );
}
