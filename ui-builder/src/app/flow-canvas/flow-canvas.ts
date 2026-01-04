import { CommonModule } from '@angular/common';
import { Component, NgZone, ViewChild } from '@angular/core';
import { FConnectionContent, FCreateConnectionEvent, FCreateNodeEvent, FDropToGroupEvent, FFlowComponent, FFlowModule, FMoveNodesEvent } from '@foblex/flow';
import { LlmConfig } from '../models/llm-config';
import { LlmConfigPanelComponent } from '../llm-config-panel/llm-config-panel';
import { ParallelGroupConfig } from '../models/parallel-group-config';
import { ParallelGroupPanelComponent } from '../parallel-group-panel/parallel-group-panel';
import { LoopConfig } from '../models/loop-config';
import { LoopPanelComponent } from '../loop-panel/loop-panel';
import { FanoutRouterConfig } from '../models/fanout-router-config';
import { FanoutRouteOption, FanoutRouterPanelComponent } from '../fanout-router-panel/fanout-router-panel';

interface AgentType {
  type: string;
  label: string;
}


interface FlowNode {
  id: string;
  label: string;
  column: number;
  position: { x: number; y: number };
  type: string;
  hasInput: boolean;
  hasOutput: boolean;
  inputId?: string;
  outputId?: string;
  parentId?: string | null;
}

interface FlowGroup {
  id: string;
  label: string;
  type: 'parallel';
  position: { x: number; y: number };
  size: { width: number; height: number };
  hasInput: boolean;
  hasOutput: boolean;
  inputId?: string;
  outputId?: string;
  config: ParallelGroupConfig;
}

interface FlowConnection {
  id: string;
  source: string;
  target: string;
  type: 'segment' | 'bezier' | 'straight' | 'adaptive_curve';
}

type RouteEntity =
  | { kind: 'node'; node: FlowNode }
  | { kind: 'group'; group: FlowGroup };

@Component({
  selector: 'app-flow-canvas',
  standalone: true,
  imports: [
    CommonModule,
    FFlowModule,
    FConnectionContent,
    LlmConfigPanelComponent,
    ParallelGroupPanelComponent,
    LoopPanelComponent,
    FanoutRouterPanelComponent
  ],
  templateUrl: './flow-canvas.html',
  styleUrl: './flow-canvas.css'
})
export class FlowCanvasComponent {
  @ViewChild(FFlowComponent) private flow?: FFlowComponent;

  readonly agentTypes: AgentType[] = [
    { type: 'start', label: 'Start' },
    { type: 'exit', label: 'Exit' },
    { type: 'llm', label: 'LLM' },
    { type: 'tool', label: 'Tool' },
    { type: 'router', label: 'Router' },
    { type: 'workflow', label: 'Workflow' },
    { type: 'external', label: 'External' },
    { type: 'a2a', label: 'A2A' },
    { type: 'fan_out_router', label: 'Fan-out Router' },
    { type: 'interrupt', label: 'Interrupt' }
  ];

  readonly groupTypes: AgentType[] = [
    { type: 'sequential', label: 'Sequential' },
    { type: 'parallel', label: 'Parallel' },
    { type: 'loop', label: 'Loop' }
  ];

  readonly iconPaths: Record<string, string> = {
    start: 'M7 5l12 7-12 7z',
    exit: 'M6 6h12v12H6z',
    llm: 'M12 2l2.2 5.2L20 9l-5.8 1.8L12 16l-2.2-5.2L4 9l5.8-1.8L12 2z',
    tool: 'M14.7 6.3a4 4 0 0 1-5 5L5 16l3 3 4.7-4.7a4 4 0 0 1 5-5z',
    router: 'M4 6h6m4 0h6M7 6v6m10-6v6M7 12h10M12 12v6M7 18h10',
    workflow:
      'M6 6h4v4H6zM14 6h4v4h-4zM10 8h4M10 16h4M6 14h4v4H6zM14 14h4v4h-4z',
    external: 'M14 4h6v6M20 4l-9 9M10 7H6v11h11v-4',
    a2a: 'M10 13a3 3 0 0 1 0-4l2-2a3 3 0 0 1 4 4l-1 1M14 11a3 3 0 0 1 0 4l-2 2a3 3 0 0 1-4-4l1-1',
    fan_out_router: 'M12 5v5m0 0l-5 5m5-5l5 5M4 20h16',
    fan_in_router: 'M4 4h16m-8 0v10m0 0l-4-4m4 4l4-4M4 20h16',
    interrupt: 'M13 2L5 14h6l-1 8 8-12h-6z',
    sequential: 'M7 6h10M7 12h10M7 18h10',
    parallel: 'M7 6v12M12 6v12M17 6v12',
    loop: 'M7 7h8a4 4 0 0 1 0 8H9m0 0l-3-3m3 3l-3 3'
  };

  nodes: FlowNode[] = [];
  connections: FlowConnection[] = [];
  groups: FlowGroup[] = [];
  activeLlmConfig: LlmConfig | null = null;
  activeParallelConfig: ParallelGroupConfig | null = null;
  activeLoopConfig: LoopConfig | null = null;
  activeFanoutConfig: FanoutRouterConfig | null = null;
  activeConnectionId: string | null = null;
  private llmConfigs: Record<string, LlmConfig> = {};
  private loopConfigs: Record<string, LoopConfig> = {};
  private fanoutConfigs: Record<string, FanoutRouterConfig> = {};
  private fanInNodes: Record<string, string> = {};
  private fanInParents: Record<string, string> = {};

  private nodeCounter = 0;
  private groupCounter = 0;
  private currentColumnIndex = 0;
  canvasScale = 1;
  gridSize = 32;
  private readonly baseGridSize = 32;
  private readonly minScale = 0.4;
  private readonly maxScale = 1.6;
  private readonly zoomStep = 0.1;
  private readonly groupMinSize = { width: 320, height: 220 };
  private readonly groupMaxSize = { width: 920, height: 720 };

  constructor(private zone: NgZone) {}

  onCreateNode(event: FCreateNodeEvent) {
    const data = event.data as AgentType | string | undefined;
    if (!data) {
      return;
    }

    this.zone.run(() => {
      const type = typeof data === 'string' ? data : data.type;
      if (type === 'parallel') {
        const id = `group-${this.groupCounter++}`;
        const dropPosition = this.getDropPoint(event);
        const config: ParallelGroupConfig = {
          nodeId: id,
          name: 'Parallel',
          description: ''
        };
        this.groups = [
          ...this.groups,
          {
            id,
            label: 'Parallel Group',
            type: 'parallel',
            position: dropPosition,
            size: { width: 440, height: 260 },
            hasInput: true,
            hasOutput: true,
            inputId: `in-${id}`,
            outputId: `out-${id}`,
            config
          }
        ];
        this.activeLlmConfig = null;
        this.activeParallelConfig = config;
        return;
      }

      const label =
        typeof data === 'string'
          ? this.getLabelForType(data)
          : data.label ?? data.type;
      const ports = this.getNodePorts(type);
      const id = `node-${this.nodeCounter++}`;
      const dropPosition = this.getDropPoint(event);
      const group = event.fTargetNode ? this.getGroupById(event.fTargetNode) : null;
      const position = group
        ? this.toGroupPosition(dropPosition, group.position)
        : dropPosition;
      const node: FlowNode = {
        id,
        label,
        column: this.currentColumnIndex,
        position,
        type,
        hasInput: ports.input,
        hasOutput: ports.output,
        inputId: ports.input ? `in-${id}` : undefined,
        outputId: ports.output ? `out-${id}` : undefined,
        parentId: group?.id ?? null
      };

      this.nodes = [...this.nodes, node];
      if (type === 'llm') {
        this.openLlmConfig(node.id);
      }
      if (type === 'loop') {
        this.openLoopConfig(node.id);
      }
      if (type === 'fan_out_router') {
        this.openFanoutConfig(node.id);
      }
    });
  }

  onCreateConnection(event: FCreateConnectionEvent) {
    const inputId = event.fInputId;
    const outputId = event.fOutputId;
    if (!inputId || !outputId) {
      return;
    }
    if (this.getNodeIdFromConnectorId(inputId, 'in-') === this.getNodeIdFromConnectorId(outputId, 'out-')) {
      return;
    }

    const exists = this.connections.some(
      (connection) => connection.source === outputId && connection.target === inputId
    );
    if (exists) {
      return;
    }

    this.zone.run(() => {
      this.connections = [
        ...this.connections,
        {
          id: `conn-${outputId}-${inputId}`,
          source: outputId,
          target: inputId,
          type: 'segment'
        }
      ];
      const sourceNodeId = this.getNodeIdFromConnectorId(outputId, 'out-');
      const sourceNode = this.nodes.find((node) => node.id === sourceNodeId);
      if (sourceNode?.type === 'fan_out_router') {
        this.syncFanoutRoutes(sourceNode.id);
      }
      this.flow?.redraw();
    });
  }

  onMoveNodes(event: FMoveNodesEvent) {
    this.zone.run(() => {
      this.nodes = this.nodes.map((node) => {
        const moved = event.fNodes.find((item) => item.id === node.id);
        if (!moved) {
          return node;
        }
        return {
          ...node,
          position: { x: moved.position.x, y: moved.position.y }
        };
      });
      this.groups = this.groups.map((group) => {
        const moved = event.fNodes.find((item) => item.id === group.id);
        if (!moved) {
          return group;
        }
        return {
          ...group,
          position: { x: moved.position.x, y: moved.position.y }
        };
      });
    });
  }

  onDropToGroup(event: FDropToGroupEvent) {
    const group = this.getGroupById(event.fTargetNode);
    if (!group) {
      return;
    }

    this.zone.run(() => {
      const dropPoint = this.getDropPointFromGroupEvent(event);
      const firstNode = this.nodes.find((node) => event.fNodes.includes(node.id));
      const firstAbsolute = firstNode ? this.getAbsolutePosition(firstNode) : dropPoint;
      const delta = {
        x: dropPoint.x - firstAbsolute.x,
        y: dropPoint.y - firstAbsolute.y
      };

      this.nodes = this.nodes.map((node) => {
        if (!event.fNodes.includes(node.id)) {
          return node;
        }
        const absolute = this.getAbsolutePosition(node);
        const movedAbsolute = {
          x: absolute.x + delta.x,
          y: absolute.y + delta.y
        };
        return {
          ...node,
          parentId: group.id,
          position: this.toGroupPosition(movedAbsolute, group.position)
        };
      });
      this.flow?.redraw();
    });
  }

  onGroupSizeChange(groupId: string, rect: { width: number; height: number }) {
    const width = this.clamp(rect.width, this.groupMinSize.width, this.groupMaxSize.width);
    const height = this.clamp(rect.height, this.groupMinSize.height, this.groupMaxSize.height);
    this.groups = this.groups.map((group) => {
      if (group.id !== groupId) {
        return group;
      }
      return {
        ...group,
        size: { width, height }
      };
    });
  }

  private getNodePorts(type: string): { input: boolean; output: boolean } {
    if (type === 'start') {
      return { input: false, output: true };
    }
    if (type === 'exit') {
      return { input: true, output: false };
    }
    return { input: true, output: true };
  }

  private getLabelForType(type: string) {
    const label =
      this.agentTypes.find((item) => item.type === type)?.label ??
      this.groupTypes.find((item) => item.type === type)?.label;
    return label ?? type;
  }

  private getGroupById(id: string | undefined) {
    if (!id) {
      return null;
    }
    return this.groups.find((group) => group.id === id) ?? null;
  }

  private getDropPoint(event: FCreateNodeEvent) {
    if (event.fDropPosition && this.flow) {
      const rect = this.flow.getPositionInFlow(event.fDropPosition);
      return { x: rect.x, y: rect.y };
    }
    return { x: event.rect.x, y: event.rect.y };
  }

  private getDropPointFromGroupEvent(event: FDropToGroupEvent) {
    if (event.fDropPosition && this.flow) {
      const rect = this.flow.getPositionInFlow(event.fDropPosition);
      return { x: rect.x, y: rect.y };
    }
    return { x: event.fDropPosition.x, y: event.fDropPosition.y };
  }

  private toGroupPosition(point: { x: number; y: number }, groupPosition: { x: number; y: number }) {
    return {
      x: point.x - groupPosition.x,
      y: point.y - groupPosition.y
    };
  }

  private getAbsolutePosition(node: FlowNode) {
    if (!node.parentId) {
      return node.position;
    }
    const parent = this.getGroupById(node.parentId);
    if (!parent) {
      return node.position;
    }
    return {
      x: parent.position.x + node.position.x,
      y: parent.position.y + node.position.y
    };
  }

  private clamp(value: number, min: number, max: number) {
    return Math.min(Math.max(value, min), max);
  }

  zoomIn() {
    this.updateScale(this.canvasScale + this.zoomStep);
  }

  zoomOut() {
    this.updateScale(this.canvasScale - this.zoomStep);
  }

  resetZoom() {
    this.canvasScale = 1;
    this.gridSize = this.baseGridSize;
  }

  get zoomLabel() {
    return `${Math.round(this.canvasScale * 100)}%`;
  }

  toggleConnectionType(connectionId: string) {
    this.zone.run(() => {
      const types: FlowConnection['type'][] = ['segment', 'bezier', 'adaptive_curve'];
      this.connections = this.connections.map((connection) => {
        if (connection.id !== connectionId) {
          return connection;
        }
        const nextIndex = (types.indexOf(connection.type) + 1) % types.length;
        return {
          ...connection,
          type: types[nextIndex]
        };
      });
      this.flow?.redraw();
    });
  }

  deleteConnection(connectionId: string) {
    const targetConnection = this.connections.find((connection) => connection.id === connectionId);
    this.connections = this.connections.filter((connection) => connection.id !== connectionId);
    if (targetConnection) {
      const sourceNodeId = this.getNodeIdFromConnectorId(targetConnection.source, 'out-');
      const sourceNode = this.nodes.find((node) => node.id === sourceNodeId);
      if (sourceNode?.type === 'fan_out_router') {
        this.syncFanoutRoutes(sourceNode.id);
      }
    }
    if (this.activeConnectionId === connectionId) {
      this.activeConnectionId = null;
    }
    this.flow?.redraw();
  }

  toggleConnectionActions(connectionId: string) {
    this.activeConnectionId = this.activeConnectionId === connectionId ? null : connectionId;
  }

  closeLlmConfig() {
    this.activeLlmConfig = null;
  }

  closeParallelConfig() {
    this.activeParallelConfig = null;
  }

  closeLoopConfig() {
    this.activeLoopConfig = null;
  }

  closeFanoutConfig() {
    this.activeFanoutConfig = null;
  }

  deleteNode(nodeId: string) {
    this.nodes = this.nodes.filter((node) => node.id !== nodeId);
    this.connections = this.connections.filter(
      (connection) =>
        !connection.source.startsWith(`out-${nodeId}`) &&
        !connection.target.startsWith(`in-${nodeId}`)
    );
    if (this.llmConfigs[nodeId]) {
      delete this.llmConfigs[nodeId];
    }
    if (this.loopConfigs[nodeId]) {
      delete this.loopConfigs[nodeId];
    }
    if (this.fanoutConfigs[nodeId]) {
      delete this.fanoutConfigs[nodeId];
    }
    if (this.fanInParents[nodeId]) {
      const fanoutId = this.fanInParents[nodeId];
      delete this.fanInParents[nodeId];
      delete this.fanInNodes[fanoutId];
      const config = this.fanoutConfigs[fanoutId];
      if (config) {
        config.fanInEnabled = false;
        config.fanInNodeId = undefined;
      }
    }
    if (this.fanInNodes[nodeId]) {
      this.removeFanInNode(nodeId);
    }
    this.activeLlmConfig = null;
    if (this.activeLoopConfig?.nodeId === nodeId) {
      this.activeLoopConfig = null;
    }
    if (this.activeFanoutConfig?.nodeId === nodeId) {
      this.activeFanoutConfig = null;
    }
    this.flow?.redraw();
  }

  deleteGroup(groupId: string) {
    this.groups = this.groups.filter((group) => group.id !== groupId);
    this.nodes = this.nodes.filter((node) => node.parentId !== groupId);
    this.connections = this.connections.filter(
      (connection) =>
        !connection.source.startsWith(`out-${groupId}`) &&
        !connection.target.startsWith(`in-${groupId}`)
    );
    if (this.activeParallelConfig?.nodeId === groupId) {
      this.activeParallelConfig = null;
    }
    this.activeParallelConfig = null;
    this.flow?.redraw();
  }

  openParallelConfig(groupId: string) {
    const group = this.groups.find((item) => item.id === groupId);
    if (!group) {
      return;
    }
    this.activeLlmConfig = null;
    this.activeLoopConfig = null;
    this.activeFanoutConfig = null;
    this.activeParallelConfig = group.config;
  }

  getSubagentNames(groupId?: string | null) {
    if (!groupId) {
      return [];
    }
    return this.nodes
      .filter((node) => node.parentId === groupId)
      .map((node) => this.getNodeLabel(node));
  }

  openLlmConfig(nodeId: string) {
    const target = this.nodes.find((node) => node.id === nodeId);
    if (!target || target.type !== 'llm') {
      return;
    }
    if (!this.llmConfigs[nodeId]) {
      this.llmConfigs[nodeId] = {
        nodeId,
        name: '',
        instruction: '',
        description: '',
        outputKey: '',
        instructionVariables: [],
        tools: [],
        callbacks: []
      };
    }
    this.activeParallelConfig = null;
    this.activeLoopConfig = null;
    this.activeFanoutConfig = null;
    this.activeLlmConfig = this.llmConfigs[nodeId];
  }

  openLlmConfigFromNode(node: FlowNode) {
    if (node.type !== 'llm') {
      return;
    }
    this.openLlmConfig(node.id);
  }

  openLoopConfig(nodeId: string) {
    const target = this.nodes.find((node) => node.id === nodeId);
    if (!target || target.type !== 'loop') {
      return;
    }
    if (!this.loopConfigs[nodeId]) {
      this.loopConfigs[nodeId] = {
        nodeId,
        name: 'Loop',
        description: '',
        maxIterations: 5,
        exitConditionType: 'logical',
        conditions: []
      };
    }
    this.activeParallelConfig = null;
    this.activeLlmConfig = null;
    this.activeFanoutConfig = null;
    this.activeLoopConfig = this.loopConfigs[nodeId];
  }

  openFanoutConfig(nodeId: string) {
    const target = this.nodes.find((node) => node.id === nodeId);
    if (!target || target.type !== 'fan_out_router') {
      return;
    }
    if (!this.fanoutConfigs[nodeId]) {
      this.fanoutConfigs[nodeId] = {
        nodeId,
        name: 'Fan-out Router',
        description: '',
        routingRules: [],
        fanInEnabled: false,
        fanInStrategy: '',
        fanInOutputKey: '',
        fanInNodeId: undefined
      };
    }
    this.activeParallelConfig = null;
    this.activeLlmConfig = null;
    this.activeLoopConfig = null;
    this.activeFanoutConfig = this.fanoutConfigs[nodeId];
    this.ensureFanInNode(this.activeFanoutConfig);
    this.syncFanoutRoutes(nodeId);
  }

  openNodePanel(node: FlowNode) {
    if (node.type === 'llm') {
      this.openLlmConfig(node.id);
      return;
    }
    if (node.type === 'loop') {
      this.openLoopConfig(node.id);
      return;
    }
    if (node.type === 'fan_out_router') {
      this.openFanoutConfig(node.id);
    }
  }

  getNodeLabel(node: FlowNode) {
    if (node.type === 'llm') {
      const config = this.llmConfigs[node.id];
      if (config && config.name.trim().length > 0) {
        return config.name;
      }
      return 'LLM';
    }
    if (node.type === 'loop') {
      const config = this.loopConfigs[node.id];
      if (config && config.name.trim().length > 0) {
        return config.name;
      }
      return 'Loop';
    }
    if (node.type === 'fan_out_router') {
      const config = this.fanoutConfigs[node.id];
      if (config && config.name.trim().length > 0) {
        return config.name;
      }
      return 'Fan-out Router';
    }
    if (node.type === 'fan_in_router') {
      const parentId = this.fanInParents[node.id];
      if (parentId) {
        const config = this.fanoutConfigs[parentId];
        if (config && config.name.trim().length > 0) {
          return `${config.name} Fan-in`;
        }
      }
      return 'Fan-in';
    }
    return node.label;
  }

  getGroupLabel(group: FlowGroup) {
    if (group.config.name && group.config.name.trim().length > 0) {
      return group.config.name;
    }
    return 'Parallel';
  }

  getInputConnectors(node: FlowNode) {
    if (!node.hasInput) {
      return [];
    }
    if (this.usesMultiConnectors(node.type)) {
      return ['top', 'right', 'bottom', 'left'].map((side) => ({
        id: `in-${node.id}-${side}`,
        side
      }));
    }
    return [
      {
        id: node.inputId ?? `in-${node.id}`,
        side: 'top'
      }
    ];
  }

  getOutputConnectors(node: FlowNode) {
    if (!node.hasOutput) {
      return [];
    }
    if (this.usesMultiConnectors(node.type)) {
      return ['top', 'right', 'bottom', 'left'].map((side) => ({
        id: `out-${node.id}-${side}`,
        side
      }));
    }
    return [
      {
        id: node.outputId ?? `out-${node.id}`,
        side: 'bottom'
      }
    ];
  }

  private usesMultiConnectors(type: string) {
    return ['llm', 'tool', 'router', 'fan_out_router', 'fan_in_router', 'workflow', 'loop'].includes(type);
  }

  getLoopSubagents(nodeId: string) {
    return this.getLoopSubagentIds(nodeId).map((id) => this.getRouteEntityLabel(id));
  }

  getAvailableAgentNames(excludeId?: string) {
    return this.nodes
      .filter((node) => node.id !== excludeId)
      .map((node) => this.getNodeLabel(node));
  }

  getFanoutRouteOptions(fanoutId: string): FanoutRouteOption[] {
    const downstreamTargets = new Set(
      this.connections
        .filter((connection) => connection.source.startsWith(`out-${fanoutId}`))
        .map((connection) => this.getNodeIdFromConnectorId(connection.target, 'in-'))
    );

    const options: FanoutRouteOption[] = [];
    downstreamTargets.forEach((targetId) => {
      const node = this.nodes.find((item) => item.id === targetId);
      if (node) {
        if (node.type === 'fan_in_router') {
          return;
        }
        options.push({
          id: node.id,
          label: this.getNodeLabel(node),
          summary: this.buildRouteSummary(node.id)
        });
        return;
      }
      const group = this.groups.find((item) => item.id === targetId);
      if (group) {
        options.push({
          id: group.id,
          label: this.getGroupLabel(group),
          summary: this.getGroupLabel(group)
        });
      }
    });

    return options;
  }

  onFanInChange(config: FanoutRouterConfig) {
    if (config.fanInEnabled) {
      this.ensureFanInNode(config);
      this.syncFanoutRoutes(config.nodeId);
      return;
    }
    this.removeFanInNode(config.nodeId);
  }

  private ensureFanInNode(config: FanoutRouterConfig) {
    if (!config.fanInEnabled) {
      return;
    }
    if (config.fanInNodeId && this.nodes.some((node) => node.id === config.fanInNodeId)) {
      this.fanInNodes[config.nodeId] = config.fanInNodeId;
      this.fanInParents[config.fanInNodeId] = config.nodeId;
      return;
    }
    const fanoutNode = this.nodes.find((node) => node.id === config.nodeId);
    if (!fanoutNode) {
      return;
    }
    const fanInId = `fan-in-${config.nodeId}`;
    const offset = { x: 0, y: 180 };
    const newNode: FlowNode = {
      id: fanInId,
      label: 'Fan-in',
      column: fanoutNode.column,
      position: {
        x: fanoutNode.position.x + offset.x,
        y: fanoutNode.position.y + offset.y
      },
      type: 'fan_in_router',
      hasInput: true,
      hasOutput: true,
      inputId: `in-${fanInId}`,
      outputId: `out-${fanInId}`,
      parentId: fanoutNode.parentId ?? null
    };
    this.nodes = [...this.nodes, newNode];
    config.fanInNodeId = fanInId;
    this.fanInNodes[config.nodeId] = fanInId;
    this.fanInParents[fanInId] = config.nodeId;
    this.flow?.redraw();
  }

  private removeFanInNode(fanoutId: string) {
    const fanInId = this.fanInNodes[fanoutId];
    if (!fanInId) {
      return;
    }
    this.nodes = this.nodes.filter((node) => node.id !== fanInId);
    this.connections = this.connections.filter(
      (connection) =>
        !connection.source.startsWith(`out-${fanInId}`) &&
        !connection.target.startsWith(`in-${fanInId}`)
    );
    delete this.fanInNodes[fanoutId];
    delete this.fanInParents[fanInId];
    const config = this.fanoutConfigs[fanoutId];
    if (config) {
      config.fanInEnabled = false;
      config.fanInNodeId = undefined;
    }
    this.flow?.redraw();
  }

  private syncFanoutRoutes(fanoutId: string) {
    const config = this.fanoutConfigs[fanoutId];
    if (!config) {
      return;
    }
    const targetIds = Array.from(
      new Set(
        this.connections
          .filter((connection) => connection.source.startsWith(`out-${fanoutId}`))
          .map((connection) => this.getNodeIdFromConnectorId(connection.target, 'in-'))
      )
    );

    const existing = new Map(
      config.routingRules
        .filter((rule) => rule.routeTargetId)
        .map((rule) => [rule.routeTargetId as string, rule])
    );
    config.routingRules = targetIds.map((targetId) => {
      const existingRule = existing.get(targetId);
      if (existingRule) {
        return existingRule;
      }
      return {
        id: `rule-${fanoutId}-${targetId}`,
        routeTargetId: targetId,
        conditions: [],
        routeAgents: []
      };
    });

    config.routingRules.forEach((rule) => {
      if (!rule.routeTargetId) {
        return;
      }
      rule.routeAgents = [rule.routeTargetId];
    });

    if (config.fanInEnabled) {
      this.ensureFanInConnections(config, targetIds);
    }
  }

  private ensureFanInConnections(config: FanoutRouterConfig, targetIds: string[]) {
    const fanInId = config.fanInNodeId ?? this.fanInNodes[config.nodeId];
    if (!fanInId) {
      return;
    }
    const fanInInput = this.getDefaultInputIdForEntity(fanInId);
    if (!fanInInput) {
      return;
    }
    const desiredSources = new Set<string>();
    targetIds.forEach((targetId) => {
      const lastId = this.getLastRouteEntityId(targetId);
      const outputId = this.getDefaultOutputIdForEntity(lastId ?? targetId);
      if (outputId) {
        desiredSources.add(outputId);
      }
    });

    if (desiredSources.size === 0) {
      return;
    }

    this.connections = this.connections.filter((connection) => {
      if (connection.target !== fanInInput) {
        return true;
      }
      return desiredSources.has(connection.source);
    });

    desiredSources.forEach((sourceId) => {
      const exists = this.connections.some(
        (connection) => connection.source === sourceId && connection.target === fanInInput
      );
      if (exists) {
        return;
      }
      this.connections = [
        ...this.connections,
        {
          id: `conn-${sourceId}-${fanInInput}`,
          source: sourceId,
          target: fanInInput,
          type: 'segment'
        }
      ];
    });
  }

  private getLastRouteEntityId(startId: string) {
    const visited = new Set<string>();
    let currentId: string | null = startId;
    let lastId: string | null = null;
    let safety = 0;
    const loopSubagentParents = this.buildLoopSubagentMap();

    while (currentId && safety < 50) {
      safety += 1;
      if (visited.has(currentId)) {
        break;
      }
      visited.add(currentId);
      const entity = this.getRouteEntity(currentId);
      if (!entity) {
        break;
      }
      if (loopSubagentParents.has(currentId)) {
        lastId = loopSubagentParents.get(currentId) ?? lastId;
        currentId = this.getNextConnectedNodeIdForRoute(currentId);
        continue;
      }
      lastId = currentId;
      if (entity.kind === 'group') {
        const nextId = this.getNextConnectedNodeIdForRoute(currentId);
        if (!nextId) {
          break;
        }
        currentId = nextId;
        continue;
      }
      const node = entity.node;
      if (node.type === 'loop') {
        const subagents = this.getLoopSubagentIds(node.id);
        if (subagents.length > 0) {
          const nextId = this.getNextConnectedNodeIdForRoute(node.id);
          if (!nextId) {
            break;
          }
          currentId = nextId;
          continue;
        }
        currentId = this.getNextConnectedNodeIdForRoute(node.id);
        continue;
      }
      if (node.type === 'fan_out_router') {
        const config = this.fanoutConfigs[node.id];
        if (!config?.fanInEnabled) {
          break;
        }
        const fanInId = config.fanInNodeId ?? this.fanInNodes[node.id];
        if (!fanInId) {
          break;
        }
        currentId = this.getNextConnectedNodeIdForRoute(fanInId);
        continue;
      }
      if (node.type === 'fan_in_router') {
        currentId = this.getNextConnectedNodeIdForRoute(node.id);
        continue;
      }
      const nextId = this.getNextConnectedNodeIdForRoute(node.id);
      if (!nextId) {
        break;
      }
      currentId = nextId;
    }

    return lastId;
  }

  private getDefaultOutputIdForEntity(entityId: string) {
    const node = this.nodes.find((item) => item.id === entityId);
    if (node) {
      const connectors = this.getOutputConnectors(node);
      const bottom = connectors.find((connector) => connector.side === 'bottom');
      return bottom?.id ?? connectors[0]?.id ?? node.outputId ?? `out-${node.id}`;
    }
    const group = this.groups.find((item) => item.id === entityId);
    if (group) {
      return group.outputId ?? `out-${group.id}`;
    }
    return null;
  }

  private getDefaultInputIdForEntity(entityId: string) {
    const node = this.nodes.find((item) => item.id === entityId);
    if (node) {
      const connectors = this.getInputConnectors(node);
      const top = connectors.find((connector) => connector.side === 'top');
      return top?.id ?? connectors[0]?.id ?? node.inputId ?? `in-${node.id}`;
    }
    const group = this.groups.find((item) => item.id === entityId);
    if (group) {
      return group.inputId ?? `in-${group.id}`;
    }
    return null;
  }

  private getNodeIdFromConnectorId(connectorId: string, prefix: string) {
    if (!connectorId.startsWith(prefix)) {
      return connectorId;
    }
    const raw = connectorId.slice(prefix.length);
    const sideSuffixes = ['-top', '-right', '-bottom', '-left'];
    const suffix = sideSuffixes.find((item) => raw.endsWith(item));
    if (!suffix) {
      return raw;
    }
    return raw.slice(0, -suffix.length);
  }

  private updateScale(next: number) {
    this.canvasScale = Math.min(this.maxScale, Math.max(this.minScale, Number(next.toFixed(2))));
    this.gridSize = this.baseGridSize * this.canvasScale;
  }

  private buildRouteSummary(startId: string) {
    const parts: string[] = [];
    const visited = new Set<string>();
    let currentId: string | null = startId;
    let safety = 0;
    const loopSubagentParents = this.buildLoopSubagentMap();
    const loopSubagents = new Set(loopSubagentParents.keys());
    const addedLoops = new Set<string>();

    while (currentId && safety < 50) {
      safety += 1;
      if (visited.has(currentId)) {
        break;
      }
      visited.add(currentId);
      const entity = this.getRouteEntity(currentId);
      if (!entity) {
        break;
      }
      if (loopSubagents.has(currentId)) {
        const loopId = loopSubagentParents.get(currentId);
        if (loopId && !addedLoops.has(loopId)) {
          const loopNode = this.nodes.find((item) => item.id === loopId);
          if (loopNode) {
            parts.push(this.getNodeLabel(loopNode));
            addedLoops.add(loopId);
          }
        }
        currentId = this.getNextConnectedNodeIdForRoute(currentId);
        continue;
      }
      if (entity.kind === 'group') {
        parts.push(this.getGroupLabel(entity.group));
        const nextId = this.getNextConnectedNodeIdForRoute(currentId);
        if (!nextId) {
          break;
        }
        currentId = nextId;
        continue;
      }

      const node = entity.node;
      if (node.type === 'loop') {
        const subagents = this.getLoopSubagentIds(node.id);
        if (subagents.length > 0) {
          if (!addedLoops.has(node.id)) {
            parts.push(this.getNodeLabel(node));
            addedLoops.add(node.id);
          }
          currentId = this.getNextConnectedNodeIdForRoute(node.id);
          continue;
        }
        currentId = this.getNextConnectedNodeIdForRoute(node.id);
        continue;
      }
      if (node.type === 'fan_out_router') {
        parts.push(this.getNodeLabel(node));
        const config = this.fanoutConfigs[node.id];
        if (!config?.fanInEnabled) {
          break;
        }
        const fanInId = config.fanInNodeId ?? this.fanInNodes[node.id];
        if (!fanInId) {
          break;
        }
        currentId = this.getNextConnectedNodeIdForRoute(fanInId);
        continue;
      }
      if (node.type === 'fan_in_router') {
        currentId = this.getNextConnectedNodeIdForRoute(node.id);
        continue;
      }

      parts.push(this.getNodeLabel(node));
      currentId = this.getNextConnectedNodeIdForRoute(node.id);
    }

    return parts.join(', ') || this.getRouteEntityLabel(startId);
  }

  private buildLoopSubagentMap() {
    const mapping = new Map<string, string>();
    this.nodes
      .filter((node) => node.type === 'loop')
      .forEach((node) => {
        const subagents = this.getLoopSubagentIds(node.id);
        if (subagents.length === 0) {
          return;
        }
        subagents.forEach((id) => mapping.set(id, node.id));
      });
    return mapping;
  }

  private getLoopSubagentIds(nodeId: string) {
    const loopbackOutputId = `out-${nodeId}-left`;
    const loopbackConnection = this.connections.find(
      (connection) => connection.source === loopbackOutputId
    );
    if (!loopbackConnection) {
      return [];
    }

    const startNodeId = this.getNodeIdFromConnectorId(loopbackConnection.target, 'in-');
    const visited = new Set<string>();
    const subagents: string[] = [];
    let currentId: string | null = startNodeId;

    while (currentId && !visited.has(currentId)) {
      visited.add(currentId);
      if (currentId === nodeId) {
        break;
      }
      const entity = this.getRouteEntity(currentId);
      if (!entity) {
        break;
      }
      if (entity.kind === 'node' && entity.node.type === 'fan_in_router') {
        currentId = this.getNextConnectedNodeId(currentId);
        continue;
      }
      subagents.push(currentId);
      if (entity.kind === 'node' && entity.node.type === 'fan_out_router') {
        const config = this.fanoutConfigs[entity.node.id];
        const fanInId = config?.fanInEnabled
          ? config.fanInNodeId ?? this.fanInNodes[entity.node.id]
          : undefined;
        if (fanInId) {
          currentId = this.getNextConnectedNodeId(fanInId);
          continue;
        }
      }
      currentId = this.getNextConnectedNodeId(currentId);
    }

    return subagents;
  }

  private getRouteEntity(id: string): RouteEntity | null {
    const node = this.nodes.find((item) => item.id === id);
    if (node) {
      return { kind: 'node', node };
    }
    const group = this.groups.find((item) => item.id === id);
    if (group) {
      return { kind: 'group', group };
    }
    return null;
  }

  private getRouteEntityLabel(id: string) {
    const entity = this.getRouteEntity(id);
    if (!entity) {
      return id;
    }
    if (entity.kind === 'group') {
      return this.getGroupLabel(entity.group);
    }
    return this.getNodeLabel(entity.node);
  }

  private getNextConnectedNodeId(nodeId: string) {
    const connection = this.connections.find((item) => item.source.startsWith(`out-${nodeId}`));
    if (!connection) {
      return null;
    }
    return this.getNodeIdFromConnectorId(connection.target, 'in-');
  }

  private getNextConnectedNodeIdForRoute(nodeId: string) {
    const node = this.nodes.find((item) => item.id === nodeId);
    if (node?.type === 'loop') {
      const nonLoopback = this.connections.find(
        (item) =>
          item.source.startsWith(`out-${nodeId}`) &&
          !item.source.startsWith(`out-${nodeId}-left`)
      );
      if (nonLoopback) {
        return this.getNodeIdFromConnectorId(nonLoopback.target, 'in-');
      }
    }
    return this.getNextConnectedNodeId(nodeId);
  }
}
