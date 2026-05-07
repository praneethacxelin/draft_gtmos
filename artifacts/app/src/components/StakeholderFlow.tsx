import { useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  MarkerType,
  type Node,
  type Edge,
} from "reactflow";
import "reactflow/dist/style.css";
import type {
  StakeholderEdge,
  StakeholderNode,
} from "@/hooks/useStrategies";

const TIER_STYLE: Record<
  StakeholderNode["tier"],
  { bg: string; border: string; text: string }
> = {
  champion: { bg: "rgba(34,197,94,0.12)", border: "#22c55e", text: "#bbf7d0" },
  blocker: { bg: "rgba(239,68,68,0.12)", border: "#ef4444", text: "#fecaca" },
  economic_buyer: { bg: "rgba(59,130,246,0.12)", border: "#3b82f6", text: "#bfdbfe" },
  influencer: { bg: "rgba(148,163,184,0.10)", border: "#64748b", text: "#e2e8f0" },
};

export function StakeholderFlow({
  nodes,
  edges,
}: {
  nodes: StakeholderNode[];
  edges: StakeholderEdge[];
}) {
  const flowNodes: Node[] = useMemo(() => {
    const cols = Math.min(3, Math.max(nodes.length, 1));
    return nodes.map((n, i) => {
      const style = TIER_STYLE[n.tier] ?? TIER_STYLE.influencer;
      return {
        id: n.id,
        position: {
          x: (i % cols) * 220,
          y: Math.floor(i / cols) * 130,
        },
        data: {
          label: (
            <div style={{ color: style.text, fontFamily: "inherit" }}>
              <div style={{ fontSize: 10, opacity: 0.7, textTransform: "uppercase", letterSpacing: "0.1em" }}>
                {n.tier.replace("_", " ")}
              </div>
              <div style={{ fontWeight: 600, fontSize: 13, marginTop: 2 }}>
                {n.label}
              </div>
              <div style={{ fontSize: 11, opacity: 0.7 }}>{n.role ?? ""}</div>
              <div style={{
                marginTop: 6, height: 3, borderRadius: 2,
                background: "rgba(255,255,255,0.08)",
              }}>
                <div style={{
                  height: "100%", width: `${n.influence ?? 0}%`,
                  background: style.border, borderRadius: 2,
                }} />
              </div>
            </div>
          ),
        },
        style: {
          background: style.bg,
          border: `1px solid ${style.border}`,
          borderRadius: 8,
          padding: 10,
          width: 200,
        },
      };
    });
  }, [nodes]);

  const flowEdges: Edge[] = useMemo(
    () =>
      edges.map((e, i) => ({
        id: `e${i}-${e.from}-${e.to}`,
        source: e.from,
        target: e.to,
        label: e.label,
        animated: true,
        markerEnd: { type: MarkerType.ArrowClosed, color: "#94a3b8" },
        style: { stroke: "#475569" },
        labelStyle: { fill: "#cbd5e1", fontSize: 10 },
        labelBgStyle: { fill: "#0f172a" },
      })),
    [edges],
  );

  return (
    <div style={{ height: 320 }} className="rounded border border-border bg-background/40">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        fitView
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1e293b" gap={16} />
        <Controls showInteractive={false} className="!bg-card !border-border" />
      </ReactFlow>
    </div>
  );
}
