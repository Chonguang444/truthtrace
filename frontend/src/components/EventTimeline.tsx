import { Loader2 } from "lucide-react";
import { formatDate } from "../lib/utils";

interface TimelineNode {
  id: string;
  timestamp: string;
  description: string;
  significance: number;
}

interface EventTimelineProps {
  nodes: TimelineNode[];
  loading?: boolean;
}

export function EventTimeline({ nodes, loading }: EventTimelineProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-32">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!nodes.length) {
    return (
      <div className="text-center py-8 text-muted-foreground text-sm">
        暂未构建时间线数据
      </div>
    );
  }

  return (
    <div className="relative pl-8">
      <div className="timeline-line" />

      <div className="space-y-6">
        {nodes.map((node, i) => (
          <div key={node.id} className="relative">
            {/* Dot */}
            <div
              className={`absolute -left-[1.625rem] top-1 h-3 w-3 rounded-full border-2 border-background ${
                node.significance > 1.5
                  ? "bg-red-500"
                  : node.significance > 1
                  ? "bg-primary"
                  : "bg-muted-foreground/30"
              }`}
            />

            {/* Content */}
            <div className={`p-3 rounded-lg border ${
              node.significance > 1.5
                ? "bg-red-50 border-red-200"
                : "bg-card"
            }`}>
              <div className="flex items-center gap-2 mb-1">
                <time className="text-xs font-medium text-muted-foreground">
                  {formatDate(node.timestamp)}
                </time>
                {node.significance > 1.5 && (
                  <span className="px-1.5 py-0.5 rounded bg-red-100 text-red-700 text-xs font-medium">
                    关键节点
                  </span>
                )}
              </div>
              <p className="text-sm">{node.description}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
