import * as vscode from "vscode";
import {
  AIDetectionResult,
  ViolationResponse,
  WebviewMessage,
} from "../types";

export class SummaryPanel {
  public static readonly viewType = "forgelineSummary";

  private static _instance: SummaryPanel | undefined;
  private readonly _panel: vscode.WebviewPanel;
  private readonly _outputChannel: vscode.OutputChannel;
  private _lastUri: vscode.Uri | undefined;
  private _disposed = false;

  static get currentInstance(): SummaryPanel | undefined {
    return SummaryPanel._instance;
  }

  static createOrShow(
    extensionUri: vscode.Uri,
    outputChannel: vscode.OutputChannel,
  ): SummaryPanel {
    if (SummaryPanel._instance) {
      SummaryPanel._instance._panel.reveal(vscode.ViewColumn.Beside);
      return SummaryPanel._instance;
    }

    const panel = vscode.window.createWebviewPanel(
      SummaryPanel.viewType,
      "ForgeLine Summary",
      vscode.ViewColumn.Beside,
      { enableScripts: true, retainContextWhenHidden: true },
    );

    SummaryPanel._instance = new SummaryPanel(panel, outputChannel);
    return SummaryPanel._instance;
  }

  private constructor(
    panel: vscode.WebviewPanel,
    outputChannel: vscode.OutputChannel,
  ) {
    this._panel = panel;
    this._outputChannel = outputChannel;

    this._panel.onDidDispose(() => {
      this._disposed = true;
      SummaryPanel._instance = undefined;
    });

    this._panel.webview.onDidReceiveMessage(
      (msg: WebviewMessage) => this._handleMessage(msg),
    );

    this._panel.webview.html = this._buildEmptyHtml();
  }

  update(
    uri: vscode.Uri,
    violations: ViolationResponse[],
    detectionResult?: AIDetectionResult,
  ): void {
    if (this._disposed) {
      return;
    }
    this._lastUri = uri;
    this._panel.webview.html = this._buildHtml(
      uri,
      violations,
      detectionResult,
    );
  }

  private async _handleMessage(msg: WebviewMessage): Promise<void> {
    if (msg.type === "goToLine") {
      if (!this._lastUri) {
        return;
      }
      const doc = await vscode.workspace.openTextDocument(this._lastUri);
      const editor = await vscode.window.showTextDocument(
        doc,
        vscode.ViewColumn.One,
      );
      const pos = new vscode.Position(msg.line - 1, 0);
      editor.selection = new vscode.Selection(pos, pos);
      editor.revealRange(
        new vscode.Range(pos, pos),
        vscode.TextEditorRevealType.InCenter,
      );
    } else if (msg.type === "suppress") {
      if (!this._lastUri) {
        return;
      }
      const doc = await vscode.workspace.openTextDocument(this._lastUri);
      const editor = await vscode.window.showTextDocument(
        doc,
        vscode.ViewColumn.One,
      );
      const line = msg.line - 1;
      const lineText = doc.lineAt(line);
      const indent = lineText.text.match(/^(\s*)/)?.[1] ?? "";
      const prefix = this._getCommentPrefix(doc.languageId);
      const comment = `${indent}${prefix} forgeline-disable-next-line: ${msg.policyId}\n`;

      await editor.edit((eb) => {
        eb.insert(new vscode.Position(line, 0), comment);
      });

      this._outputChannel.appendLine(
        `[Summary] Suppressed rule ${msg.policyId} at line ${msg.line}`,
      );
    }
  }

  private _buildEmptyHtml(): string {
    const nonce = this._getNonce();
    return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy"
    content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';">
  <style>${this._getStyles()}</style>
</head>
<body>
  <div class="empty">
    <p>No scan results yet.</p>
    <p>Run <strong>ForgeLine: Scan File</strong> or <strong>Scan Selection</strong> to see results here.</p>
  </div>
</body>
</html>`;
  }

  private _buildHtml(
    uri: vscode.Uri,
    violations: ViolationResponse[],
    detectionResult?: AIDetectionResult,
  ): string {
    const nonce = this._getNonce();
    const filename = vscode.workspace.asRelativePath(uri);
    const timestamp = new Date().toLocaleTimeString();

    const errorCount = violations.filter(
      (v) => v.severity === "error",
    ).length;
    const warnCount = violations.filter(
      (v) => v.severity === "warning",
    ).length;
    const infoCount = violations.filter(
      (v) => v.severity === "info",
    ).length;

    let detectionHtml = "";
    if (detectionResult) {
      detectionHtml = `
        <div class="section detection">
          <h3>AI Detection</h3>
          <div class="detection-info">
            <span class="confidence">Confidence: ${(detectionResult.confidence * 100).toFixed(0)}%</span>
            <span class="likely ${detectionResult.isLikelyAI ? "yes" : "no"}">
              ${detectionResult.isLikelyAI ? "Likely AI-generated" : "Likely human-written"}
            </span>
          </div>
          ${detectionResult.signals.length > 0 ? `<div class="signals">Signals: ${detectionResult.signals.join(", ")}</div>` : ""}
        </div>`;
    }

    const violationCards = violations
      .map(
        (v) => `
      <div class="card severity-${v.severity}">
        <div class="card-header">
          <span class="badge badge-${v.severity}">${v.severity.toUpperCase()}</span>
          <span class="policy-id">${this._escapeHtml(v.policy_id)}</span>
          <span class="location">Line ${v.line_start}</span>
        </div>
        <div class="card-body">
          <p class="message">${this._escapeHtml(v.message)}</p>
          ${v.suggestion ? `<p class="suggestion">${this._escapeHtml(v.suggestion)}</p>` : ""}
          ${v.code_snippet ? `<pre class="snippet">${this._escapeHtml(v.code_snippet)}</pre>` : ""}
        </div>
        <div class="card-actions">
          <a href="#" class="action-link" onclick="goToLine(${v.line_start})">Go to line ${v.line_start}</a>
          <a href="#" class="action-link" onclick="suppress('${this._escapeHtml(v.policy_id)}', ${v.line_start})">Suppress</a>
        </div>
      </div>`,
      )
      .join("\n");

    return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy"
    content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';">
  <style>${this._getStyles()}</style>
</head>
<body>
  <div class="header">
    <h2>${this._escapeHtml(filename)}</h2>
    <span class="timestamp">${timestamp}</span>
    <div class="badge-row">
      ${errorCount > 0 ? `<span class="badge badge-error">${errorCount} error${errorCount !== 1 ? "s" : ""}</span>` : ""}
      ${warnCount > 0 ? `<span class="badge badge-warning">${warnCount} warning${warnCount !== 1 ? "s" : ""}</span>` : ""}
      ${infoCount > 0 ? `<span class="badge badge-info">${infoCount} info</span>` : ""}
      ${violations.length === 0 ? '<span class="badge badge-ok">No violations</span>' : ""}
    </div>
  </div>

  ${detectionHtml}

  <div class="section">
    ${violations.length > 0 ? `<h3>Violations (${violations.length})</h3>` : ""}
    ${violationCards}
  </div>

  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    function goToLine(line) {
      vscode.postMessage({ type: 'goToLine', line: line });
    }
    function suppress(policyId, line) {
      vscode.postMessage({ type: 'suppress', policyId: policyId, line: line });
    }
  </script>
</body>
</html>`;
  }

  private _getStyles(): string {
    return `
      body {
        font-family: var(--vscode-font-family);
        font-size: var(--vscode-font-size);
        color: var(--vscode-foreground);
        background: var(--vscode-editor-background);
        padding: 12px;
        margin: 0;
      }
      .empty {
        text-align: center;
        padding: 40px 20px;
        color: var(--vscode-descriptionForeground);
      }
      .header {
        border-bottom: 1px solid var(--vscode-panel-border);
        padding-bottom: 10px;
        margin-bottom: 16px;
      }
      .header h2 {
        margin: 0 0 4px;
        font-size: 1.2em;
      }
      .timestamp {
        color: var(--vscode-descriptionForeground);
        font-size: 0.85em;
      }
      .badge-row {
        margin-top: 8px;
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
      }
      .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 3px;
        font-size: 0.8em;
        font-weight: 600;
      }
      .badge-error {
        background: var(--vscode-editorError-foreground);
        color: var(--vscode-editor-background);
      }
      .badge-warning {
        background: var(--vscode-editorWarning-foreground);
        color: var(--vscode-editor-background);
      }
      .badge-info {
        background: var(--vscode-editorInfo-foreground);
        color: var(--vscode-editor-background);
      }
      .badge-ok {
        background: var(--vscode-badge-background);
        color: var(--vscode-badge-foreground);
      }
      .section {
        margin-bottom: 16px;
      }
      .section h3 {
        margin: 0 0 8px;
        font-size: 1em;
      }
      .detection {
        background: var(--vscode-textBlockQuote-background);
        border-left: 3px solid var(--vscode-textLink-foreground);
        padding: 10px 12px;
        border-radius: 3px;
        margin-bottom: 16px;
      }
      .detection-info {
        display: flex;
        gap: 12px;
        align-items: center;
      }
      .confidence {
        font-weight: 600;
      }
      .likely.yes {
        color: var(--vscode-editorWarning-foreground);
      }
      .likely.no {
        color: var(--vscode-descriptionForeground);
      }
      .signals {
        margin-top: 6px;
        font-size: 0.85em;
        color: var(--vscode-descriptionForeground);
      }
      .card {
        border: 1px solid var(--vscode-panel-border);
        border-radius: 4px;
        margin-bottom: 10px;
        overflow: hidden;
      }
      .card.severity-error {
        border-left: 3px solid var(--vscode-editorError-foreground);
      }
      .card.severity-warning {
        border-left: 3px solid var(--vscode-editorWarning-foreground);
      }
      .card.severity-info {
        border-left: 3px solid var(--vscode-editorInfo-foreground);
      }
      .card-header {
        padding: 8px 12px;
        display: flex;
        gap: 8px;
        align-items: center;
        background: var(--vscode-textBlockQuote-background);
      }
      .policy-id {
        font-family: var(--vscode-editor-font-family);
        font-size: 0.85em;
      }
      .location {
        margin-left: auto;
        font-size: 0.85em;
        color: var(--vscode-descriptionForeground);
      }
      .card-body {
        padding: 8px 12px;
      }
      .message {
        margin: 0 0 6px;
      }
      .suggestion {
        margin: 0;
        font-style: italic;
        color: var(--vscode-descriptionForeground);
      }
      .snippet {
        background: var(--vscode-textCodeBlock-background);
        padding: 8px;
        border-radius: 3px;
        overflow-x: auto;
        font-family: var(--vscode-editor-font-family);
        font-size: 0.9em;
        margin: 6px 0 0;
      }
      .card-actions {
        padding: 6px 12px;
        display: flex;
        gap: 12px;
        border-top: 1px solid var(--vscode-panel-border);
      }
      .action-link {
        color: var(--vscode-textLink-foreground);
        text-decoration: none;
        font-size: 0.85em;
        cursor: pointer;
      }
      .action-link:hover {
        text-decoration: underline;
      }
    `;
  }

  private _getNonce(): string {
    const chars =
      "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    let nonce = "";
    for (let i = 0; i < 32; i++) {
      nonce += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return nonce;
  }

  private _escapeHtml(text: string): string {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  private _getCommentPrefix(languageId: string): string {
    switch (languageId) {
      case "python":
      case "ruby":
      case "shellscript":
      case "yaml":
        return "#";
      default:
        return "//";
    }
  }
}
