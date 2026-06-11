import { useEffect, useRef, useState } from "react";
import cytoscape, { Core } from "cytoscape";
import { Play, Pause, SkipBack, SkipForward, Clock } from "lucide-react";

interface TimelineNode {
  id: string;
  label: string;
  timestamp: string;
  significance: number;
}

interface GraphNode {
  id: string;
  label: string;
  platform: string;
  url: string;
  is_original: boolean;
  authority_score: number;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  weight: number;
}

interface CytoscapeTimelineProps {
  graphData: {
    nodes: GraphNode[];
    edges: GraphEdge[];
  };
  timelineData?: TimelineNode[];
  height?: number;
}

const PLATFORM_COLORS: Record<string, string> = {
  weibo: "#E6162D", zhihu: "#0084FF", wechat: "#07C160",
  twitter: "#1DA1F2", reddit: "#FF4500", news: "#10B981",
  general: "#6B7280", unknown: "#9CA3AF",
  xiaohongshu: "#FF2442", douyin: "#000000",
  kuaishou: "#FF5000", bilibili: "#FB7299", youtube: "#FF0000",
};

export function CytoscapeTimeline({
  graphData,
  timelineData,
  height = 600,
}: CytoscapeTimelineProps) {
  const graphContainerRef = useRef<HTMLDivElement>(null);
  const timelineContainerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [playing, setPlaying] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [totalSteps] = useState(10);
  const playIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Build timeline events from graph + timeline data
  const timelineEvents = timelineData || [];

  // ── Initialize Cytoscape graph ──
  useEffect(() => {
    if (!graphContainerRef.current || !graphData.nodes.length) return;

    const cy = cytoscape({
      container: graphContainerRef.current,
      elements: [
        ...graphData.nodes.map((n) => ({
          group: "nodes" as const,
          data: {
            id: n.id,
            label: n.label.slice(0, 18),
            platform: n.platform,
            is_original: n.is_original,
          },
        })),
        ...graphData.edges.map((e) => ({
          group: "edges" as const,
          data: { id: e.id, source: e.source, target: e.target, type: e.type, weight: e.weight },
        })),
      ],
      style: [
        {
          selector: "node",
          style: {
            "background-color": "#6B7280",
            label: "data(label)",
            "font-size": "10px",
            width: 20, height: 20,
            "text-valign": "bottom",
            "text-halign": "center",
          },
        },
        ...Object.entries(PLATFORM_COLORS).map(([p, c]) => ({
          selector: `node[platform="${p}"]`,
          style: { "background-color": c },
        })),
        {
          selector: "node[is_original=true]",
          style: { "border-color": "#F59E0B", "border-width": 3 },
        },
        {
          selector: "edge",
          style: {
            width: 1.5, "line-color": "#9CA3AF",
            "target-arrow-color": "#9CA3AF", "target-arrow-shape": "triangle",
            "arrow-scale": 0.7, "curve-style": "bezier",
          },
        },
        { selector: ".hidden-node", style: { opacity: 0.15 } },
        { selector: ".hidden-edge", style: { opacity: 0.1 } },
      ],
      layout: { name: "cose", animate: false },
      wheelSensitivity: 0.2,
      minZoom: 0.2, maxZoom: 3,
    });

    cyRef.current = cy;
    return () => { cy.destroy(); cyRef.current = null; };
  }, [graphData]);

  // ── Step change handler ──
  const showStep = (step: number) => {
    const cy = cyRef.current;
    if (!cy) return;

    const revealFraction = (step + 1) / totalSteps;
    const totalNodes = graphData.nodes.length;

    cy.nodes().forEach((node, i) => {
      const shouldShow = i < Math.floor(totalNodes * revealFraction);
      if (shouldShow) {
        node.removeClass("hidden-node");
        // Trigger a subtle flash
        node.style("border-color", "#3B82F6");
        setTimeout(() => node.style("border-color", node.data("is_original") ? "#F59E0B" : ""), 600);
      } else {
        node.addClass("hidden-node");
      }
    });

    cy.edges().forEach((edge) => {
      const src = edge.data("source") as string;
      const tgt = edge.data("target") as string;
      const srcIdx = graphData.nodes.findIndex((n) => n.id === src);
      const tgtIdx = graphData.nodes.findIndex((n) => n.id === tgt);
      const showThreshold = Math.floor(totalNodes * revealFraction);
      if (srcIdx < showThreshold && tgtIdx < showThreshold) {
        edge.removeClass("hidden-edge");
      } else {
        edge.addClass("hidden-edge");
      }
    });
  };

  // ── Play/pause animation ──
  useEffect(() => {
    if (playing) {
      playIntervalRef.current = setInterval(() => {
        setCurrentStep((prev) => {
          const next = prev + 1;
          if (next >= totalSteps) {
            setPlaying(false);
            return prev;
          }
          showStep(next);
          return next;
        });
      }, 800);
    } else {
      if (playIntervalRef.current) clearInterval(playIntervalRef.current);
    }
    return () => { if (playIntervalRef.current) clearInterval(playIntervalRef.current); };
  }, [playing, totalSteps]);

  // Show step 0 on mount
  useEffect(() => { showStep(currentStep); }, []);

  return (
    <div className="rounded-lg border bg-card overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-2 border-b bg-muted/20">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Clock size={14} />
          传播时序动画
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => { setCurrentStep(0); showStep(0); }}
            className="p-1 rounded hover:bg-muted"
            title="重置"
          >
            <SkipBack size={14} />
          </button>
          <button
            onClick={() => setPlaying(!playing)}
            className={`p-1 rounded ${playing ? "bg-blue-100 text-blue-600" : "hover:bg-muted"}`}
            title={playing ? "暂停" : "播放"}
          >
            {playing ? <Pause size={14} /> : <Play size={14} />}
          </button>
          <button
            onClick={() => { const ns = totalSteps - 1; setCurrentStep(ns); showStep(ns); }}
            className="p-1 rounded hover:bg-muted"
            title="跳到结束"
          >
            <SkipForward size={14} />
          </button>
        </div>
      </div>

      {/* Timeline scrubber */}
      <div className="px-3 py-1.5 border-b bg-muted/10">
        <input
          type="range"
          min={0}
          max={totalSteps - 1}
          value={currentStep}
          onChange={(e) => { const v = parseInt(e.target.value); setCurrentStep(v); showStep(v); }}
          className="w-full h-1.5 accent-blue-500 cursor-pointer"
        />
        <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
          <span>步骤 {currentStep + 1}/{totalSteps}</span>
          <span>{Math.round(((currentStep + 1) / totalSteps) * 100)}%</span>
        </div>
      </div>

      {/* Timeline events */}
      {timelineEvents.length > 0 && (
        <div
          ref={timelineContainerRef}
          className="flex overflow-x-auto gap-2 px-3 py-1.5 border-b bg-muted/5 max-h-10"
        >
          {timelineEvents.map((evt, i) => (
            <button
              key={i}
              onClick={() => { setCurrentStep(i); showStep(i); }}
              className={`shrink-0 text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap transition-colors ${
                i <= currentStep
                  ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              {evt.label?.slice(0, 20)}
            </button>
          ))}
        </div>
      )}

      {/* Cytoscape graph */}
      <div
        ref={graphContainerRef}
        style={{ width: "100%", height: `${height}px` }}
        className="bg-gray-50 dark:bg-gray-950"
      />

      {/* Step info bar */}
      <div className="px-3 py-1 border-t bg-muted/10 text-[10px] text-muted-foreground flex items-center justify-between">
        <span>节点: {graphData.nodes.length} · 边: {graphData.edges.length}</span>
        <span className={playing ? "text-blue-500 animate-pulse" : ""}>
          {playing ? "▶ 动画播放中..." : "⏸ 已暂停"}
        </span>
      </div>
    </div>
  );
}

export default CytoscapeTimeline;
