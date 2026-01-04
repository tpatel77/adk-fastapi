import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ParallelGroupConfig } from '../models/parallel-group-config';

@Component({
  selector: 'app-parallel-group-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './parallel-group-panel.html',
  styleUrls: ['./parallel-group-panel.css']
})
export class ParallelGroupPanelComponent {
  @Input() config: ParallelGroupConfig | null = null;
  @Input() subagents: string[] = [];
  @Output() close = new EventEmitter<void>();
  @Output() deleteGroup = new EventEmitter<string>();

  requestDelete() {
    if (!this.config) {
      return;
    }
    this.deleteGroup.emit(this.config.nodeId);
  }
}
