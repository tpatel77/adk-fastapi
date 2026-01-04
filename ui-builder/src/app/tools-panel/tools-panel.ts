import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';

type ToolItem = {
  id: string;
  name: string;
  type: 'Python Function' | 'Python REST API';
  description: string;
  arguments: ToolArgument[];
  outputs: string[];
  version: string;
};

type ToolArgument = {
  name: string;
  type: 'String' | 'Integer' | 'Float' | 'Boolean' | 'Object' | 'Array';
  required: boolean;
  properties?: ToolArgument[];
};

@Component({
  selector: 'app-tools-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './tools-panel.html',
  styleUrl: './tools-panel.css'
})
export class ToolsPanelComponent {
  @Input() tools: ToolItem[] = [];
  @Input() selectedToolId: string | null = null;
  @Output() selectTool = new EventEmitter<string>();
  @Output() createTool = new EventEmitter<{ name: string; type: ToolItem['type'] }>();
  @Output() addArgument = new EventEmitter<string>();
  @Output() updateArgument = new EventEmitter<{
    toolId: string;
    path: number[];
    field: 'name' | 'type' | 'required';
    value: string | boolean;
  }>();
  @Output() removeArgument = new EventEmitter<{ toolId: string; path: number[] }>();
  @Output() defineSchema = new EventEmitter<{ toolId: string; path: number[] }>();
  @Output() addProperty = new EventEmitter<{ toolId: string; path: number[] }>();
  @Output() removeTool = new EventEmitter<string>();

  protected readonly toolTypes = [
    {
      type: 'Python Function' as const,
      description: 'Local Python function that runs within the workflow.',
      tags: ['Arguments', 'Code', 'Python']
    },
    {
      type: 'Python REST API' as const,
      description: 'HTTP REST API Integration tool.',
      tags: ['REST Settings', 'Arguments', 'Python']
    }
  ];
  protected showCreateModal = false;
  protected createStep: 1 | 2 = 1;
  protected selectedToolType: ToolItem['type'] | null = null;
  protected newToolName = '';
  protected toolTab: 'arguments' | 'code' = 'arguments';
  protected readonly argumentTypes = ['String', 'Integer', 'Float', 'Boolean', 'Object', 'Array'] as const;
  protected showDeleteModal = false;
  protected pendingDeleteTool: ToolItem | null = null;

  get selectedTool(): ToolItem | null {
    if (this.tools.length === 0) {
      return null;
    }
    if (!this.selectedToolId) {
      return this.tools[0];
    }
    return this.tools.find((tool) => tool.id === this.selectedToolId) ?? this.tools[0];
  }

  openCreateModal() {
    this.showCreateModal = true;
    this.createStep = 1;
    this.selectedToolType = null;
    this.newToolName = '';
  }

  promptDeleteTool(tool: ToolItem, event: Event) {
    event.stopPropagation();
    this.pendingDeleteTool = tool;
    this.showDeleteModal = true;
  }

  cancelDeleteTool() {
    this.pendingDeleteTool = null;
    this.showDeleteModal = false;
  }

  confirmDeleteTool() {
    if (!this.pendingDeleteTool) {
      return;
    }
    this.removeTool.emit(this.pendingDeleteTool.id);
    this.pendingDeleteTool = null;
    this.showDeleteModal = false;
  }

  closeCreateModal() {
    this.showCreateModal = false;
    this.createStep = 1;
    this.selectedToolType = null;
    this.newToolName = '';
  }

  chooseToolType(type: ToolItem['type']) {
    this.selectedToolType = type;
    this.createStep = 2;
  }

  backToToolType() {
    this.createStep = 1;
  }

  submitCreateTool() {
    if (!this.selectedToolType || !this.newToolName.trim()) {
      return;
    }
    this.createTool.emit({ name: this.newToolName.trim(), type: this.selectedToolType });
    this.closeCreateModal();
  }

  setToolTab(tab: 'arguments' | 'code') {
    this.toolTab = tab;
  }

  addToolArgument() {
    if (!this.selectedTool) {
      return;
    }
    this.addArgument.emit(this.selectedTool.id);
  }

  updateToolArgument(path: number[], field: 'name' | 'type' | 'required', value: string | boolean) {
    if (!this.selectedTool) {
      return;
    }
    this.updateArgument.emit({
      toolId: this.selectedTool.id,
      path,
      field,
      value
    });
  }

  removeToolArgument(path: number[]) {
    if (!this.selectedTool) {
      return;
    }
    this.removeArgument.emit({ toolId: this.selectedTool.id, path });
  }

  defineObjectSchema(path: number[]) {
    if (!this.selectedTool) {
      return;
    }
    this.defineSchema.emit({ toolId: this.selectedTool.id, path });
  }

  addObjectProperty(path: number[]) {
    if (!this.selectedTool) {
      return;
    }
    this.addProperty.emit({ toolId: this.selectedTool.id, path });
  }

  schemaPreview(properties: ToolArgument[] | undefined) {
    if (!properties || properties.length === 0) {
      return '{}';
    }
    const schema = this.buildSchemaObject(properties);
    return JSON.stringify(schema, null, 2);
  }

  private buildSchemaObject(properties: ToolArgument[]) {
    return properties.reduce<Record<string, unknown>>((acc, property) => {
      acc[property.name] = this.schemaValue(property);
      return acc;
    }, {});
  }

  private schemaValue(property: ToolArgument): unknown {
    if (property.type === 'Object') {
      return this.buildSchemaObject(property.properties ?? []);
    }
    if (property.type === 'Array') {
      return ['<array>'];
    }
    return `<${property.type.toLowerCase()}>`;
  }

  extendPath(path: number[], index: number) {
    return [...path, index];
  }
}
