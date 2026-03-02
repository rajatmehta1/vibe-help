import * as vscode from "vscode";
import { ApiClient } from "../analysis/apiClient";
import { DiagnosticProvider } from "../analysis/diagnosticProvider";

type StatusState = "connected" | "disconnected" | "violations" | "indexing";

export class StatusBarManager implements vscode.Disposable {
  private readonly _statusBarItem: vscode.StatusBarItem;
  private _healthTimer: ReturnType<typeof setInterval> | undefined;
  private _currentState: StatusState = "disconnected";

  constructor(
    private readonly _apiClient: ApiClient,
    private readonly _diagnosticProvider: DiagnosticProvider,
  ) {
    this._statusBarItem = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Left,
      100,
    );
    this._statusBarItem.show();
    this._setState("disconnected");
    this._startHealthPolling();
  }

  private _setState(state: StatusState, detail?: string): void {
    this._currentState = state;

    switch (state) {
      case "connected":
        this._statusBarItem.text = "$(shield) ForgeLine: $(check)";
        this._statusBarItem.tooltip = "ForgeLine: Connected to server";
        this._statusBarItem.command = undefined;
        this._statusBarItem.backgroundColor = undefined;
        break;

      case "disconnected":
        this._statusBarItem.text =
          "$(shield) ForgeLine: $(close) Disconnected";
        this._statusBarItem.tooltip =
          "ForgeLine: Cannot reach server. Click to retry.";
        this._statusBarItem.command = "ForgeLine.retryConnection";
        this._statusBarItem.backgroundColor = new vscode.ThemeColor(
          "statusBarItem.warningBackground",
        );
        break;

      case "violations": {
        const count = detail ?? "?";
        this._statusBarItem.text = `$(shield) ForgeLine: $(warning) ${count}`;
        this._statusBarItem.tooltip = `ForgeLine: ${count} violation(s) found. Click to open Problems panel.`;
        this._statusBarItem.command = "workbench.actions.view.problems";
        this._statusBarItem.backgroundColor = undefined;
        break;
      }

      case "indexing":
        this._statusBarItem.text =
          "$(shield) ForgeLine: $(sync~spin) Indexing...";
        this._statusBarItem.tooltip = detail
          ? `ForgeLine: Indexing in progress - ${detail}`
          : "ForgeLine: Indexing workspace...";
        this._statusBarItem.command = undefined;
        this._statusBarItem.backgroundColor = undefined;
        break;
    }
  }

  private _startHealthPolling(): void {
    this._checkHealth();
    this._healthTimer = setInterval(() => {
      this._checkHealth();
    }, 30_000);
  }

  private async _checkHealth(): Promise<void> {
    try {
      await this._apiClient.healthCheck();
      const count = this._diagnosticProvider.getDiagnosticCount();
      if (count > 0) {
        this._setState("violations", String(count));
      } else {
        this._setState("connected");
      }
    } catch {
      this._setState("disconnected");
    }
  }

  showIndexing(detail?: string): void {
    this._setState("indexing", detail);
  }

  updateViolationCount(): void {
    if (this._currentState === "indexing") {
      return;
    }
    const count = this._diagnosticProvider.getDiagnosticCount();
    if (count > 0) {
      this._setState("violations", String(count));
    } else if (this._currentState !== "disconnected") {
      this._setState("connected");
    }
  }

  async refreshConnection(): Promise<void> {
    await this._checkHealth();
  }

  dispose(): void {
    if (this._healthTimer) {
      clearInterval(this._healthTimer);
    }
    this._statusBarItem.dispose();
  }
}
