import * as vscode from "vscode";
import { ApiClient } from "./analysis/apiClient";
import { DiagnosticProvider } from "./analysis/diagnosticProvider";
import {
  ForgeLineQuickFixProvider,
  ViolationDataStore,
} from "./analysis/quickFixProvider";
import { AICodeDetector } from "./detection/aiCodeDetector";
import { ChangeTracker } from "./detection/changeTracker";
import {
  AIDetectionResult,
  ApiError,
  AuthError,
  NetworkError,
  ViolationResponse,
} from "./types";
import { StatusBarManager } from "./ui/statusBar";
import { SummaryPanel } from "./ui/summaryPanel";
import { ForgeLineTreeProvider } from "./ui/treeView";

export function activate(context: vscode.ExtensionContext): void {
  const outputChannel =
    vscode.window.createOutputChannel("ForgeLine");
  context.subscriptions.push(outputChannel);
  outputChannel.appendLine("ForgeLine extension activating...");

  // ---- Initialize components ----

  const apiClient = new ApiClient(outputChannel);
  const diagnosticProvider = new DiagnosticProvider();
  const violationDataStore = new ViolationDataStore();
  const quickFixProvider = new ForgeLineQuickFixProvider(
    violationDataStore,
  );
  const changeTracker = new ChangeTracker();
  const aiDetector = new AICodeDetector();
  const statusBar = new StatusBarManager(apiClient, diagnosticProvider);

  const treeProvider = new ForgeLineTreeProvider();
  const allViolations = new Map<string, ViolationResponse[]>();

  context.subscriptions.push(
    apiClient,
    diagnosticProvider,
    violationDataStore,
    changeTracker,
    statusBar,
  );

  // ---- Register Tree View ----

  const treeView = vscode.window.createTreeView("forgelineViolations", {
    treeDataProvider: treeProvider,
    showCollapseAll: true,
  });
  context.subscriptions.push(treeView);

  // ---- Register QuickFixProvider for all file-scheme documents ----

  context.subscriptions.push(
    vscode.languages.registerCodeActionsProvider(
      { scheme: "file" },
      quickFixProvider,
      {
        providedCodeActionKinds:
          ForgeLineQuickFixProvider.providedCodeActionKinds,
      },
    ),
  );

  // ---- Wire detection pipeline ----
  // ChangeTracker → AICodeDetector → ApiClient.analyze → DiagnosticProvider

  context.subscriptions.push(
    changeTracker.onSignificantInsertion(async (metadata) => {
      const config = vscode.workspace.getConfiguration("forgeline");
      if (!config.get<boolean>("autoScan", true)) {
        return;
      }

      outputChannel.appendLine(
        `[Detection] Significant insertion in ${metadata.filePath}: ` +
          `${metadata.lineEnd - metadata.lineStart} lines, type=${metadata.changeType}`,
      );

      const detection = aiDetector.scoreInsertion(
        metadata.insertedText,
        metadata.changeType,
      );

      if (!detection.isLikelyAI) {
        return;
      }

      outputChannel.appendLine(
        `[Detection] Likely AI-generated (confidence=${detection.confidence.toFixed(2)}): ` +
          `${detection.signals.join(", ")}`,
      );

      try {
        const uri = vscode.Uri.file(metadata.filePath);
        const document = await vscode.workspace.openTextDocument(uri);

        const result = await apiClient.analyze({
          code: metadata.insertedText,
          file_path: metadata.filePath,
          language: document.languageId,
          surrounding_context: document.getText(),
        });

        if (result.violations && result.violations.length > 0) {
          processAndUpdateUI(
            uri,
            result.violations,
            diagnosticProvider,
            violationDataStore,
            allViolations,
            treeProvider,
            detection,
          );
          statusBar.updateViolationCount();
        }
      } catch (err) {
        if (err instanceof ApiError && err.statusCode === 404) {
          outputChannel.appendLine(
            "[Detection] Analysis endpoint not available, showing local detection result",
          );
          showLocalDetectionNotification(
            detection.confidence,
            detection.signals,
          );
        } else if (err instanceof NetworkError) {
          outputChannel.appendLine(
            `[Detection] Network error: ${err.message}`,
          );
        } else if (err instanceof AuthError) {
          outputChannel.appendLine(
            `[Detection] Auth error: ${err.message}`,
          );
        }
      }
    }),
  );

  // ---- Register commands ----

  // scanFile
  context.subscriptions.push(
    vscode.commands.registerCommand("ForgeLine.scanFile", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showWarningMessage(
          "ForgeLine: No active file to scan.",
        );
        return;
      }

      const uri = editor.document.uri;
      outputChannel.appendLine(`[Scan] Scanning file: ${uri.fsPath}`);
      statusBar.showIndexing("Scanning file...");

      try {
        const result = await apiClient.analyze({
          code: editor.document.getText(),
          file_path: uri.fsPath,
          language: editor.document.languageId,
        });

        diagnosticProvider.clearDiagnostics(uri);
        violationDataStore.clearUri(uri);
        allViolations.delete(uri.toString());

        if (result.violations && result.violations.length > 0) {
          processAndUpdateUI(
            uri,
            result.violations,
            diagnosticProvider,
            violationDataStore,
            allViolations,
            treeProvider,
          );
          vscode.window.showInformationMessage(
            `ForgeLine: Found ${result.violations.length} violation(s).`,
          );
        } else {
          treeProvider.refresh(allViolations);
          vscode.window.showInformationMessage(
            "ForgeLine: No violations found.",
          );
        }
      } catch (err) {
        handleCommandError(err, "scan file", outputChannel);
      } finally {
        statusBar.updateViolationCount();
      }
    }),
  );

  // scanWorkspace
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "ForgeLine.scanWorkspace",
      async () => {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
          vscode.window.showWarningMessage(
            "ForgeLine: No workspace folder open.",
          );
          return;
        }

        outputChannel.appendLine("[Scan] Scanning workspace...");
        statusBar.showIndexing("Scanning workspace...");

        try {
          const openDocuments = vscode.workspace.textDocuments.filter(
            (d) => d.uri.scheme === "file",
          );

          // Clear all tracked violations for a fresh workspace scan
          allViolations.clear();

          let totalViolations = 0;
          for (const doc of openDocuments) {
            try {
              const result = await apiClient.analyze({
                code: doc.getText(),
                file_path: doc.uri.fsPath,
                language: doc.languageId,
              });

              diagnosticProvider.clearDiagnostics(doc.uri);
              violationDataStore.clearUri(doc.uri);

              if (result.violations && result.violations.length > 0) {
                processAndUpdateUI(
                  doc.uri,
                  result.violations,
                  diagnosticProvider,
                  violationDataStore,
                  allViolations,
                  treeProvider,
                );
                totalViolations += result.violations.length;
              }
            } catch (innerErr) {
              outputChannel.appendLine(
                `[Scan] Error scanning ${doc.uri.fsPath}: ${innerErr}`,
              );
            }
          }

          vscode.window.showInformationMessage(
            `ForgeLine: Workspace scan complete. ${totalViolations} violation(s) across ${openDocuments.length} file(s).`,
          );
        } catch (err) {
          handleCommandError(err, "scan workspace", outputChannel);
        } finally {
          statusBar.updateViolationCount();
        }
      },
    ),
  );

  // indexWorkspace
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "ForgeLine.indexWorkspace",
      async () => {
        outputChannel.appendLine(
          "[Index] Triggering workspace indexing...",
        );
        statusBar.showIndexing();

        try {
          const job = await apiClient.triggerIndex("full");
          outputChannel.appendLine(
            `[Index] Job created: ${job.id}, status: ${job.status}`,
          );

          vscode.window.showInformationMessage(
            `ForgeLine: Indexing started (Job ${job.id.substring(0, 8)}...)`,
          );

          pollIndexingStatus(apiClient, statusBar, outputChannel);
        } catch (err) {
          handleCommandError(err, "index workspace", outputChannel);
          statusBar.updateViolationCount();
        }
      },
    ),
  );

  // injectContext
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "ForgeLine.injectContext",
      async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
          vscode.window.showWarningMessage(
            "ForgeLine: No active editor.",
          );
          return;
        }

        outputChannel.appendLine(
          "[Context] Fetching project conventions and patterns...",
        );

        try {
          const [patterns, conventions] = await Promise.all([
            apiClient
              .getPatterns()
              .catch(() => ({ patterns: [], count: 0 })),
            apiClient
              .getConventions()
              .catch(() => ({ conventions: [], count: 0 })),
          ]);

          if (patterns.count === 0 && conventions.count === 0) {
            vscode.window.showInformationMessage(
              "ForgeLine: No patterns or conventions found. Try indexing first.",
            );
            return;
          }

          const contextLines: string[] = [
            "// === ForgeLine Codebase Context ===",
            "// Patterns and conventions detected from this codebase:",
            "",
          ];

          for (const p of patterns.patterns.slice(0, 10)) {
            contextLines.push(
              `// Pattern: ${p.name} - ${p.description ?? ""}`,
            );
          }

          if (patterns.count > 0 && conventions.count > 0) {
            contextLines.push("");
          }

          for (const c of conventions.conventions.slice(0, 10)) {
            contextLines.push(
              `// Convention: ${c.name} - ${c.description ?? ""}`,
            );
          }

          contextLines.push(
            "",
            "// === End ForgeLine Context ===",
            "",
          );

          const contextText = contextLines.join("\n");

          await vscode.env.clipboard.writeText(contextText);

          vscode.window.showInformationMessage(
            `ForgeLine: ${patterns.count} patterns and ${conventions.count} conventions copied to clipboard. Paste into your AI tool.`,
          );
        } catch (err) {
          handleCommandError(err, "inject context", outputChannel);
        }
      },
    ),
  );

  // markAsAIGenerated
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "ForgeLine.markAsAIGenerated",
      async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
          vscode.window.showWarningMessage(
            "ForgeLine: No active editor.",
          );
          return;
        }

        const selection = editor.selection;
        if (selection.isEmpty) {
          vscode.window.showWarningMessage(
            "ForgeLine: Select code to mark as AI-generated.",
          );
          return;
        }

        const commentPrefix = getCommentPrefix(
          editor.document.languageId,
        );

        await editor.edit((editBuilder) => {
          editBuilder.insert(
            new vscode.Position(selection.start.line, 0),
            `${commentPrefix} [AI-GENERATED] Begin - marked by ForgeLine\n`,
          );
          editBuilder.insert(
            new vscode.Position(selection.end.line + 1, 0),
            `${commentPrefix} [AI-GENERATED] End - marked by ForgeLine\n`,
          );
        });

        outputChannel.appendLine(
          `[Mark] Marked lines ${selection.start.line + 1}-${selection.end.line + 1} as AI-generated`,
        );

        vscode.window.showInformationMessage(
          "ForgeLine: Selection marked as AI-generated.",
        );

        // Force-analyze regardless of confidence
        try {
          const selectedText = editor.document.getText(selection);
          const result = await apiClient.analyze({
            code: selectedText,
            file_path: editor.document.uri.fsPath,
            language: editor.document.languageId,
          });

          if (result.violations && result.violations.length > 0) {
            processAndUpdateUI(
              editor.document.uri,
              result.violations,
              diagnosticProvider,
              violationDataStore,
              allViolations,
              treeProvider,
            );
            statusBar.updateViolationCount();
          }
        } catch {
          // Silent — marking still succeeded
        }
      },
    ),
  );

  // retryConnection (internal command for status bar click)
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "ForgeLine.retryConnection",
      async () => {
        await statusBar.refreshConnection();
      },
    ),
  );

  // showSummary
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "ForgeLine.showSummary",
      () => {
        const panel = SummaryPanel.createOrShow(
          context.extensionUri,
          outputChannel,
        );
        const editor = vscode.window.activeTextEditor;
        if (editor) {
          const uri = editor.document.uri;
          const violations = allViolations.get(uri.toString()) ?? [];
          panel.update(uri, violations);
        }
      },
    ),
  );

  // scanSelection
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "ForgeLine.scanSelection",
      async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
          vscode.window.showWarningMessage(
            "ForgeLine: No active editor.",
          );
          return;
        }

        const selection = editor.selection;
        if (selection.isEmpty) {
          vscode.window.showWarningMessage(
            "ForgeLine: Select code to scan.",
          );
          return;
        }

        const selectedText = editor.document.getText(selection);
        const uri = editor.document.uri;

        outputChannel.appendLine(
          `[Scan] Scanning selection in ${uri.fsPath} (${selection.end.line - selection.start.line + 1} lines)`,
        );
        statusBar.showIndexing("Scanning selection...");

        try {
          const result = await apiClient.analyze({
            code: selectedText,
            file_path: uri.fsPath,
            language: editor.document.languageId,
            surrounding_context: editor.document.getText(),
          });

          if (result.violations && result.violations.length > 0) {
            processAndUpdateUI(
              uri,
              result.violations,
              diagnosticProvider,
              violationDataStore,
              allViolations,
              treeProvider,
            );
            vscode.window.showInformationMessage(
              `ForgeLine: Found ${result.violations.length} violation(s) in selection.`,
            );
          } else {
            vscode.window.showInformationMessage(
              "ForgeLine: No violations found in selection.",
            );
          }
        } catch (err) {
          handleCommandError(err, "scan selection", outputChannel);
        } finally {
          statusBar.updateViolationCount();
        }
      },
    ),
  );

  // refreshTree
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "ForgeLine.refreshTree",
      async () => {
        outputChannel.appendLine("[Tree] Refreshing violations tree...");
        try {
          const conventions = await apiClient
            .getConventions()
            .catch(() => ({ conventions: [], count: 0 }));
          treeProvider.refresh(allViolations, conventions.conventions);
        } catch {
          treeProvider.refresh(allViolations);
        }
      },
    ),
  );

  // ---- Scan on save ----

  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument(async (document) => {
      const config = vscode.workspace.getConfiguration("forgeline");
      if (!config.get<boolean>("scanOnSave", true)) {
        return;
      }
      if (document.uri.scheme !== "file") {
        return;
      }

      outputChannel.appendLine(
        `[Scan] Auto-scanning on save: ${document.uri.fsPath}`,
      );

      try {
        const result = await apiClient.analyze({
          code: document.getText(),
          file_path: document.uri.fsPath,
          language: document.languageId,
        });

        diagnosticProvider.clearDiagnostics(document.uri);
        violationDataStore.clearUri(document.uri);
        allViolations.delete(document.uri.toString());

        if (result.violations && result.violations.length > 0) {
          processAndUpdateUI(
            document.uri,
            result.violations,
            diagnosticProvider,
            violationDataStore,
            allViolations,
            treeProvider,
          );
        } else {
          treeProvider.refresh(allViolations);
        }
      } catch (err) {
        if (!(err instanceof ApiError && err.statusCode === 404)) {
          outputChannel.appendLine(`[Scan] Auto-scan error: ${err}`);
        }
      } finally {
        statusBar.updateViolationCount();
      }
    }),
  );

  // ---- Clean up violations when documents close ----

  context.subscriptions.push(
    vscode.workspace.onDidCloseTextDocument((document) => {
      if (document.uri.scheme !== "file") {
        return;
      }
      const key = document.uri.toString();
      if (allViolations.has(key)) {
        allViolations.delete(key);
        diagnosticProvider.clearDiagnostics(document.uri);
        violationDataStore.clearUri(document.uri);
        treeProvider.refresh(allViolations);
        statusBar.updateViolationCount();
      }
    }),
  );

  outputChannel.appendLine("ForgeLine extension activated successfully.");
}

// ---- Helper functions ----

function processAndUpdateUI(
  uri: vscode.Uri,
  violations: ViolationResponse[],
  diagnosticProvider: DiagnosticProvider,
  violationDataStore: ViolationDataStore,
  allViolations: Map<string, ViolationResponse[]>,
  treeProvider: ForgeLineTreeProvider,
  detectionResult?: AIDetectionResult,
): void {
  const config = vscode.workspace.getConfiguration("forgeline");
  const threshold = config.get<string>("severityThreshold", "warning");
  const filtered = filterBySeverity(violations, threshold);

  diagnosticProvider.showViolations(uri, filtered);
  for (const v of filtered) {
    violationDataStore.store(uri, v);
  }

  // Update shared violation store and tree
  const existing = allViolations.get(uri.toString()) ?? [];
  allViolations.set(uri.toString(), [...existing, ...filtered]);
  treeProvider.refresh(allViolations);

  // Update summary panel if visible
  const panel = SummaryPanel.currentInstance;
  if (panel) {
    const all = allViolations.get(uri.toString()) ?? [];
    panel.update(uri, all, detectionResult);
  }
}

function filterBySeverity(
  violations: ViolationResponse[],
  threshold: string,
): ViolationResponse[] {
  const severityOrder: Record<string, number> = {
    error: 0,
    warning: 1,
    info: 2,
  };
  const thresholdLevel = severityOrder[threshold] ?? 1;
  return violations.filter((v) => {
    const level = severityOrder[v.severity] ?? 2;
    return level <= thresholdLevel;
  });
}

function handleCommandError(
  err: unknown,
  context: string,
  outputChannel: vscode.OutputChannel,
): void {
  if (err instanceof AuthError) {
    vscode.window.showErrorMessage(
      "ForgeLine: Authentication failed. Check your API key in settings.",
    );
  } else if (err instanceof NetworkError) {
    vscode.window.showErrorMessage(
      "ForgeLine: Cannot reach server. Check forgeline.serverUrl setting.",
    );
  } else if (err instanceof ApiError) {
    if (err.statusCode === 404) {
      vscode.window.showWarningMessage(
        `ForgeLine: The ${context} endpoint is not available yet on the server.`,
      );
    } else {
      vscode.window.showErrorMessage(
        `ForgeLine: Server error (${err.statusCode}): ${err.detail ?? err.message}`,
      );
    }
  } else {
    vscode.window.showErrorMessage(
      `ForgeLine: Unexpected error during ${context}.`,
    );
  }
  outputChannel.appendLine(`[Error] ${context}: ${err}`);
}

async function pollIndexingStatus(
  apiClient: ApiClient,
  statusBar: StatusBarManager,
  outputChannel: vscode.OutputChannel,
): Promise<void> {
  const pollInterval = 5_000;
  const maxPolls = 120; // 10 minutes

  for (let i = 0; i < maxPolls; i++) {
    await new Promise((r) => setTimeout(r, pollInterval));

    try {
      const status = await apiClient.getIndexStatus();
      const progress =
        status.total_files > 0
          ? `${status.processed_files}/${status.total_files}`
          : "...";

      statusBar.showIndexing(`${progress} files processed`);
      outputChannel.appendLine(
        `[Index] Progress: ${progress}, status: ${status.status}`,
      );

      if (status.status === "completed") {
        statusBar.updateViolationCount();
        vscode.window.showInformationMessage(
          `ForgeLine: Indexing complete. ${status.processed_files} files processed.`,
        );
        return;
      }

      if (status.status === "failed") {
        statusBar.updateViolationCount();
        vscode.window.showErrorMessage(
          `ForgeLine: Indexing failed: ${status.error_message ?? "Unknown error"}`,
        );
        return;
      }
    } catch (err) {
      outputChannel.appendLine(`[Index] Poll error: ${err}`);
    }
  }

  statusBar.updateViolationCount();
  outputChannel.appendLine("[Index] Polling timed out after 10 minutes");
}

function showLocalDetectionNotification(
  confidence: number,
  signals: string[],
): void {
  vscode.window.showWarningMessage(
    `ForgeLine: Potentially AI-generated code detected (confidence: ${(confidence * 100).toFixed(0)}%). Signals: ${signals.join(", ")}`,
  );
}

function getCommentPrefix(languageId: string): string {
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

export function deactivate(): void {
  // All cleanup handled by subscriptions disposal
}
