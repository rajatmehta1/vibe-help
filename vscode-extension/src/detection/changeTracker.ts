import * as vscode from "vscode";
import { ChangeMetadata, ChangeType } from "../types";

export class ChangeTracker implements vscode.Disposable {
  private readonly _onSignificantInsertion =
    new vscode.EventEmitter<ChangeMetadata>();
  public readonly onSignificantInsertion =
    this._onSignificantInsertion.event;

  private _disposables: vscode.Disposable[] = [];
  private _recentChanges: Map<
    string,
    { timestamp: number; totalLines: number; lastMetadata: ChangeMetadata }
  > = new Map();
  private _debounceTimers: Map<string, NodeJS.Timeout> = new Map();

  // Thresholds
  private readonly PASTE_LINE_THRESHOLD = 3;
  private readonly SIGNIFICANT_LINE_THRESHOLD = 5;
  private readonly RAPID_SEQUENCE_WINDOW_MS = 300;

  constructor() {
    const subscription = vscode.workspace.onDidChangeTextDocument(
      this._onDocumentChange,
      this,
    );
    this._disposables.push(subscription);
  }

  private _onDocumentChange(event: vscode.TextDocumentChangeEvent): void {
    if (event.document.uri.scheme !== "file") {
      return;
    }

    for (const change of event.contentChanges) {
      if (change.text.length === 0) {
        continue;
      }

      const insertedLines = change.text.split("\n").length - 1;
      if (insertedLines === 0 && change.text.length < 50) {
        continue;
      }

      const filePath = event.document.uri.fsPath;
      const now = Date.now();
      let changeType: ChangeType = "manual";

      // Paste detection: >3 lines in single change
      if (insertedLines >= this.PASTE_LINE_THRESHOLD) {
        changeType = "paste";
      }

      // Rapid sequence: accumulate within debounce window
      const recent = this._recentChanges.get(filePath);
      if (
        recent &&
        now - recent.timestamp < this.RAPID_SEQUENCE_WINDOW_MS
      ) {
        const accumulated = recent.totalLines + insertedLines;
        if (
          accumulated >= this.SIGNIFICANT_LINE_THRESHOLD &&
          changeType === "manual"
        ) {
          changeType = "rapid_sequence";
        }

        const metadata: ChangeMetadata = {
          filePath,
          insertedText:
            recent.lastMetadata.insertedText + change.text,
          lineStart: Math.min(
            recent.lastMetadata.lineStart,
            change.range.start.line,
          ),
          lineEnd: change.range.start.line + insertedLines,
          timestamp: now,
          changeType,
          characterCount:
            recent.lastMetadata.characterCount + change.text.length,
        };

        this._recentChanges.set(filePath, {
          timestamp: now,
          totalLines: accumulated,
          lastMetadata: metadata,
        });
        this._scheduleEmit(filePath, metadata, accumulated);
      } else {
        const metadata: ChangeMetadata = {
          filePath,
          insertedText: change.text,
          lineStart: change.range.start.line,
          lineEnd: change.range.start.line + insertedLines,
          timestamp: now,
          changeType,
          characterCount: change.text.length,
        };

        this._recentChanges.set(filePath, {
          timestamp: now,
          totalLines: insertedLines,
          lastMetadata: metadata,
        });
        this._scheduleEmit(filePath, metadata, insertedLines);
      }
    }
  }

  private _scheduleEmit(
    filePath: string,
    metadata: ChangeMetadata,
    lineCount: number,
  ): void {
    const existing = this._debounceTimers.get(filePath);
    if (existing) {
      clearTimeout(existing);
    }

    // Large paste — emit immediately
    if (
      metadata.changeType === "paste" &&
      lineCount >= this.SIGNIFICANT_LINE_THRESHOLD
    ) {
      this._emit(metadata);
      this._recentChanges.delete(filePath);
      return;
    }

    // Debounce to accumulate rapid sequence
    const timer = setTimeout(() => {
      this._debounceTimers.delete(filePath);
      const recent = this._recentChanges.get(filePath);
      if (
        recent &&
        recent.totalLines >= this.SIGNIFICANT_LINE_THRESHOLD
      ) {
        this._emit(recent.lastMetadata);
      }
      this._recentChanges.delete(filePath);
    }, this.RAPID_SEQUENCE_WINDOW_MS);

    this._debounceTimers.set(filePath, timer);
  }

  private _emit(metadata: ChangeMetadata): void {
    this._onSignificantInsertion.fire(metadata);
  }

  dispose(): void {
    for (const timer of this._debounceTimers.values()) {
      clearTimeout(timer);
    }
    this._debounceTimers.clear();
    this._recentChanges.clear();
    this._onSignificantInsertion.dispose();
    for (const d of this._disposables) {
      d.dispose();
    }
  }
}
