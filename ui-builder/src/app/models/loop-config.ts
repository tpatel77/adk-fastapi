export type LoopExitConditionType = 'logical' | 'tool';

export type LoopConditionOperator =
  | 'eq'
  | 'ne'
  | 'gte'
  | 'lte'
  | 'contains'
  | 'starts_with'
  | 'ends_with'
  | 'is_null'
  | 'is_not_null'
  | 'in_list'
  | 'not_in_list'
  | 'regex_match'
  | 'regex_search'
  | 'regex_full_match';

export interface LoopCondition {
  id: string;
  variable: string;
  operator: LoopConditionOperator;
  value: string;
  joinWith: 'AND' | 'OR';
}

export interface LoopConfig {
  nodeId: string;
  name: string;
  description: string;
  maxIterations: number | null;
  exitConditionType: LoopExitConditionType;
  conditions: LoopCondition[];
}
