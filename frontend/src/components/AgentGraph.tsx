import {
  Background,
  BackgroundVariant,
  Handle,
  Position,
  ReactFlow,
  MarkerType,
  type NodeProps,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMemo } from "react";
import {
  Box,
  Check,
  FileCode2,
  FlaskConical,
  GitBranch,
  Lightbulb,
  LockKeyhole,
  ScanSearch,
  ShieldCheck,
  WandSparkles,
} from "lucide-react";
import type { Run } from "../lib/types";
const definitions = [
  { id: "clone", label: "Clone", icon: GitBranch, x: 15, y: 30 },
  { id: "baseline", label: "Baseline", icon: FlaskConical, x: 205, y: 30 },
  { id: "locate", label: "Locate", icon: ScanSearch, x: 395, y: 30 },
  { id: "diagnose", label: "Diagnose", icon: Lightbulb, x: 395, y: 170 },
  { id: "patch", label: "Patch", icon: WandSparkles, x: 205, y: 170 },
  { id: "validate_patch", label: "Validate", icon: FileCode2, x: 15, y: 170 },
  { id: "test", label: "Test", icon: Box, x: 15, y: 310 },
  { id: "review", label: "Review", icon: ShieldCheck, x: 205, y: 310 },
  { id: "approval", label: "Approval", icon: LockKeyhole, x: 395, y: 310 },
];
type GraphNode = Node<{ label: string; step: string; state: string }, "agent">;
function AgentNode({ data }: NodeProps<GraphNode>) {
  const Icon = definitions.find((x) => x.id === data.step)?.icon ?? Box;
  return (
    <div className={`graph-node graph-node-${data.state}`}>
      <Handle type="target" position={Position.Left} />
      <div>
        <span className="graph-icon">
          {data.state === "done" ? <Check size={18} /> : <Icon size={18} />}
        </span>
        <strong>{data.label}</strong>
      </div>
      <small>
        {data.state === "done"
          ? "Completed"
          : data.state === "active"
            ? "In progress"
            : "Waiting"}
      </small>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
const nodeTypes = { agent: AgentNode };
export default function AgentGraph({ run }: { run: Run }) {
  const active = [...run.events]
    .reverse()
    .find((e) => e.type === "start")?.node;
  const done = new Set(
    run.events.filter((e) => e.type === "end").map((e) => e.node),
  );
  const nodes = useMemo(
    () =>
      definitions.map((d) => ({
        id: d.id,
        type: "agent",
        position: { x: d.x, y: d.y },
        data: {
          label: d.label,
          step: d.id,
          state: done.has(d.id) ? "done" : active === d.id ? "active" : "idle",
        },
      })),
    [active, run.events.length],
  );
  const edges = definitions.slice(0, -1).map((d, i) => ({
    id: `${d.id}-${definitions[i + 1].id}`,
    source: d.id,
    target: definitions[i + 1].id,
    type: "smoothstep",
    animated: done.has(d.id) && active === definitions[i + 1].id,
    style: {
      stroke: done.has(d.id) ? "#7762ce" : "#303444",
      strokeWidth: 1.4,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: done.has(d.id) ? "#7762ce" : "#303444",
      width: 14,
      height: 14,
    },
  }));
  edges.push({
    id: "retry",
    source: "test",
    target: "patch",
    type: "smoothstep",
    animated: active === "recover",
    style: { stroke: "#565063", strokeWidth: 1.1, strokeDasharray: "4 5" },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      color: "#565063",
      width: 14,
      height: 14,
    },
  } as (typeof edges)[number]);
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.16 }}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      panOnDrag={false}
      zoomOnScroll={false}
      zoomOnPinch={false}
      zoomOnDoubleClick={false}
      preventScrolling={false}
      proOptions={{ hideAttribution: true }}
      minZoom={0.3}
    >
      <Background
        color="#353646"
        gap={20}
        size={1}
        variant={BackgroundVariant.Dots}
      />
    </ReactFlow>
  );
}
