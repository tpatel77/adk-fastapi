import { LoopCondition, LoopConditionOperator } from './loop-config';

export type FanoutRouteCondition = LoopCondition;
export type FanoutConditionOperator = LoopConditionOperator;

export interface FanoutRoutingRule {
  id: string;
  conditions: FanoutRouteCondition[];
  routeAgents: string[];
  routeTargetId?: string;
}

export interface FanoutRouterConfig {
  nodeId: string;
  name: string;
  description: string;
  routingRules: FanoutRoutingRule[];
  fanInEnabled: boolean;
  fanInStrategy: '' | 'dict' | 'list';
  fanInOutputKey: string;
  fanInNodeId?: string;
}
