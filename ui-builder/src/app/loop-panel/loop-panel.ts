import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LoopCondition, LoopConditionOperator, LoopConfig, LoopExitConditionType } from '../models/loop-config';

const DEFAULT_OPERATOR: LoopConditionOperator = 'eq';

@Component({
  selector: 'app-loop-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './loop-panel.html',
  styleUrls: ['./loop-panel.css']
})
export class LoopPanelComponent {
  @Input() config: LoopConfig | null = null;
  @Input() subagents: string[] = [];
  @Output() close = new EventEmitter<void>();
  @Output() deleteLoop = new EventEmitter<string>();

  readonly exitConditionTypes: Array<{ value: LoopExitConditionType; label: string }> = [
    { value: 'logical', label: 'Logical Condition' },
    { value: 'tool', label: 'Tool Based' }
  ];

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

  addCondition() {
    if (!this.config) {
      return;
    }
    const id = `cond-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const condition: LoopCondition = {
      id,
      variable: '',
      operator: DEFAULT_OPERATOR,
      value: '',
      joinWith: 'AND'
    };
    this.config.conditions = [...this.config.conditions, condition];
  }

  removeCondition(conditionId: string) {
    if (!this.config) {
      return;
    }
    this.config.conditions = this.config.conditions.filter((condition) => condition.id !== conditionId);
  }

  updateExitCondition(type: LoopExitConditionType) {
    if (!this.config) {
      return;
    }
    this.config.exitConditionType = type;
  }

  requestDelete() {
    if (!this.config) {
      return;
    }
    this.deleteLoop.emit(this.config.nodeId);
  }
}
