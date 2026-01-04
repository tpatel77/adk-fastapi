import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { FanoutRoutingRule, FanoutRouterConfig } from '../models/fanout-router-config';
import { LoopCondition, LoopConditionOperator } from '../models/loop-config';

const DEFAULT_OPERATOR: LoopConditionOperator = 'eq';

export interface FanoutRouteOption {
  id: string;
  label: string;
  summary: string;
}

@Component({
  selector: 'app-fanout-router-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './fanout-router-panel.html',
  styleUrls: ['./fanout-router-panel.css']
})
export class FanoutRouterPanelComponent {
  @Input() config: FanoutRouterConfig | null = null;
  @Input() availableAgents: FanoutRouteOption[] = [];
  @Output() close = new EventEmitter<void>();
  @Output() deleteRouter = new EventEmitter<string>();
  @Output() fanInChange = new EventEmitter<FanoutRouterConfig>();

  readonly operators: Array<{ value: LoopConditionOperator; label: string }> = [
    { value: 'eq', label: 'Equal (eq)' },
    { value: 'ne', label: 'Not Equal (ne)' },
    { value: 'gte', label: 'Greater Than (gte)' },
    { value: 'lte', label: 'Less Than (lte)' },
    { value: 'contains', label: 'Contains' },
    { value: 'starts_with', label: 'Starts With' },
    { value: 'ends_with', label: 'Ends With' },
    { value: 'is_null', label: 'Is Null' },
    { value: 'is_not_null', label: 'Is Not Null' },
    { value: 'in_list', label: 'In List' },
    { value: 'not_in_list', label: 'Not In List' },
    { value: 'regex_match', label: 'Regex Match' },
    { value: 'regex_search', label: 'Regex Search' },
    { value: 'regex_full_match', label: 'Regex Full Match' }
  ];

  addCondition(rule: FanoutRoutingRule) {
    const id = `cond-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const condition: LoopCondition = {
      id,
      variable: '',
      operator: DEFAULT_OPERATOR,
      value: '',
      joinWith: 'AND'
    };
    rule.conditions = [...rule.conditions, condition];
  }

  removeCondition(rule: FanoutRoutingRule, conditionId: string) {
    rule.conditions = rule.conditions.filter((condition) => condition.id !== conditionId);
  }

  toggleAgent(rule: FanoutRoutingRule, agentId: string) {
    if (rule.routeAgents.includes(agentId)) {
      rule.routeAgents = rule.routeAgents.filter((name) => name !== agentId);
      return;
    }
    rule.routeAgents = [...rule.routeAgents, agentId];
  }

  getRouteSummary(rule: FanoutRoutingRule) {
    if (rule.routeAgents.length === 0) {
      return 'No routes connected';
    }
    const optionsById = new Map(this.availableAgents.map((option) => [option.id, option]));
    const optionsByLabel = new Map(this.availableAgents.map((option) => [option.label, option]));
    const summaries = rule.routeAgents.map((agent) => {
      const option = optionsById.get(agent) ?? optionsByLabel.get(agent);
      return option?.summary ?? agent;
    });
    if (summaries.length === 1) {
      return summaries[0];
    }
    return `Routes: ${summaries.join(' | ')}`;
  }

  getRouteSummaryForRule(rule: FanoutRoutingRule) {
    const optionsById = new Map(this.availableAgents.map((option) => [option.id, option]));
    const fallback = rule.routeTargetId ?? 'Route';
    const option = rule.routeTargetId ? optionsById.get(rule.routeTargetId) : null;
    return option?.summary ?? fallback;
  }

  getRouteTitle(rule: FanoutRoutingRule) {
    const optionsById = new Map(this.availableAgents.map((option) => [option.id, option]));
    const fallback = rule.routeTargetId ?? 'Route';
    const option = rule.routeTargetId ? optionsById.get(rule.routeTargetId) : null;
    return option?.label ?? fallback;
  }

  requestDelete() {
    if (!this.config) {
      return;
    }
    this.deleteRouter.emit(this.config.nodeId);
  }
}
