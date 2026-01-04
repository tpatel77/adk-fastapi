import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LlmConfig } from '../models/llm-config';
import promptsData from '../../../data/prompts.json';

type PromptRecord = {
  promptId: string;
  intent: string;
  model: string;
  provider: string;
  status: string;
  user: string;
  createdAt: string;
};

type PromptDataset = {
  data: PromptRecord[];
};

@Component({
  selector: 'app-llm-config-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './llm-config-panel.html',
  styleUrls: ['./llm-config-panel.css']
})
export class LlmConfigPanelComponent {
  @Input() config: LlmConfig | null = null;
  @Output() close = new EventEmitter<void>();
  @Output() deleteAgent = new EventEmitter<string>();
  protected showPromptPicker = false;
  protected showToolPicker = false;
  protected showCallbackPicker = false;
  protected readonly availablePrompts = (promptsData as PromptDataset).data;
  protected selectedPrompt:
    | { name: string; id: string; model: string; provider: string; status: string; createdBy: string; createdAt: string }
    | null = null;
  protected readonly availableTools = [
    'echo_tool',
    'add_numbers',
    'multiply_numbers',
    'lookup_country',
    'query_vector_store'
  ];
  protected readonly availableCallbacks = [
    'log_agent_start',
    'log_tool_start',
    'log_tool_finish',
    'log_model_finish',
    'log_agent_finish'
  ];
  protected readonly callbackTypes = [
    'on_agent_start',
    'on_agent_finish',
    'on_tool_start',
    'on_tool_finish',
    'on_model_start',
    'on_model_finish'
  ];

  setToolsFromText(value: string) {
    if (!this.config) {
      return;
    }
    this.config.tools = value
      .split('\n')
      .map((tool) => tool.trim())
      .filter(Boolean);
  }

  setCallbacksFromText(value: string) {
    if (!this.config) {
      return;
    }
    this.config.callbacks = value
      .split('\n')
      .map((entry) => entry.trim())
      .filter(Boolean);
  }

  addInstructionVariable() {
    if (!this.config) {
      return;
    }
    this.config.instructionVariables = [
      ...this.config.instructionVariables,
      { key: '', value: '' }
    ];
  }

  removeInstructionVariable(index: number) {
    if (!this.config) {
      return;
    }
    this.config.instructionVariables = this.config.instructionVariables.filter((_, idx) => idx !== index);
  }

  searchExistingPrompt() {
    this.showPromptPicker = true;
  }

  closePromptPicker() {
    this.showPromptPicker = false;
  }

  pickPrompt(prompt: PromptRecord) {
    if (this.config) {
      this.config.instruction = prompt.promptId;
    }
    this.selectedPrompt = {
      name: prompt.intent,
      id: prompt.promptId,
      model: prompt.model,
      provider: prompt.provider,
      status: prompt.status,
      createdBy: prompt.user,
      createdAt: prompt.createdAt
    };
    this.showPromptPicker = false;
  }

  clearPrompt() {
    if (this.config) {
      this.config.instruction = '';
    }
    this.selectedPrompt = null;
  }

  addExistingTool() {
    this.showToolPicker = true;
  }

  createNewTool() {
    // Placeholder for wiring tool creation.
  }

  addExistingCallback() {
    this.showCallbackPicker = true;
  }

  useExistingCallback() {
    // Placeholder for wiring callback selection.
  }

  closeToolPicker() {
    this.showToolPicker = false;
  }

  closeCallbackPicker() {
    this.showCallbackPicker = false;
  }

  addTool(tool: string) {
    if (!this.config) {
      return;
    }
    if (!this.config.tools.includes(tool)) {
      this.config.tools = [...this.config.tools, tool];
    }
    this.showToolPicker = false;
  }

  addCallback(callback: string) {
    if (!this.config) {
      return;
    }
    if (!this.config.callbacks.includes(callback)) {
      this.config.callbacks = [...this.config.callbacks, callback];
    }
    this.showCallbackPicker = false;
  }

  addCallbackType(callbackType: string) {
    if (!this.config || !callbackType) {
      return;
    }
    if (!this.config.callbacks.includes(callbackType)) {
      this.config.callbacks = [...this.config.callbacks, callbackType];
    }
  }

  requestDelete() {
    if (!this.config) {
      return;
    }
    this.deleteAgent.emit(this.config.nodeId);
  }
}
