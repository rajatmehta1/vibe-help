import { AIDetectionResult } from "../types";

interface Signal {
  name: string;
  weight: number;
  test: (text: string, context: string) => boolean;
}

export class AICodeDetector {
  private readonly AI_THRESHOLD = 0.5;
  private readonly signals: Signal[];

  constructor() {
    this.signals = [
      {
        name: "Large block (>10 lines)",
        weight: 0.2,
        test: (text) => text.split("\n").length > 10,
      },
      {
        name: "Explanatory inline comments",
        weight: 0.2,
        test: (text) => this._hasExplanatoryComments(text),
      },
      {
        name: "Perfect formatting consistency",
        weight: 0.1,
        test: (text) => this._hasPerfectFormatting(text),
      },
      {
        name: "AI patterns (TODO placeholders, template code)",
        weight: 0.15,
        test: (text) => this._hasAIPatterns(text),
      },
      {
        name: "Tutorial quality (every step explained)",
        weight: 0.15,
        test: (text) => this._hasTutorialQuality(text),
      },
      {
        name: "Boilerplate template match",
        weight: 0.1,
        test: (text) => this._isBoilerplateTemplate(text),
      },
      {
        name: "Rapid/bulk insertion",
        weight: 0.1,
        test: (_text, context) =>
          context === "paste" || context === "rapid_sequence",
      },
    ];
  }

  scoreInsertion(
    insertedText: string,
    fileContext: string,
  ): AIDetectionResult {
    let confidence = 0;
    const matchedSignals: string[] = [];

    for (const signal of this.signals) {
      if (signal.test(insertedText, fileContext)) {
        confidence += signal.weight;
        matchedSignals.push(signal.name);
      }
    }

    confidence = Math.min(1.0, Math.max(0.0, confidence));

    return {
      confidence,
      signals: matchedSignals,
      isLikelyAI: confidence >= this.AI_THRESHOLD,
    };
  }

  private _hasExplanatoryComments(text: string): boolean {
    const lines = text.split("\n");
    const codeLines = lines.filter((l) => l.trim().length > 0);
    if (codeLines.length < 3) {
      return false;
    }

    const commentPatterns = [
      /^\s*\/\/\s+\w/,
      /^\s*#\s+\w/,
      /^\s*\/\*\*?\s+\w/,
      /^\s*\*\s+\w/,
    ];

    let commentCount = 0;
    for (const line of codeLines) {
      if (commentPatterns.some((p) => p.test(line))) {
        commentCount++;
      }
    }

    return commentCount / codeLines.length > 0.3;
  }

  private _hasPerfectFormatting(text: string): boolean {
    const lines = text.split("\n");
    if (lines.length < 5) {
      return false;
    }

    const indents = lines
      .filter((l) => l.trim().length > 0)
      .map((l) => {
        const match = l.match(/^(\s*)/);
        return match ? match[1].length : 0;
      });

    const nonZeroIndents = indents.filter((i) => i > 0);
    if (nonZeroIndents.length === 0) {
      return false;
    }

    const minIndent = Math.min(...nonZeroIndents);
    if (minIndent === 0) {
      return false;
    }

    const allConsistent = nonZeroIndents.every(
      (i) => i % minIndent === 0,
    );
    const noTrailing = lines.every(
      (l) => l === l.trimEnd() || l.trim().length === 0,
    );

    return allConsistent && noTrailing;
  }

  private _hasAIPatterns(text: string): boolean {
    const patterns = [
      /TODO:?\s*(implement|add|replace|update|fix)\s/i,
      /\/\/\s*\.\.\./,
      /your[_-]?(api[_-]?key|token|secret)/i,
      /example\.(com|org)/i,
      /placeholder/i,
      /FIXME:?\s*(implement|add)/i,
      /pass\s*#\s*TODO/,
      /throw\s+new\s+Error\s*\(\s*["']Not implemented/i,
      /raise\s+NotImplementedError/,
    ];
    return patterns.filter((p) => p.test(text)).length >= 2;
  }

  private _hasTutorialQuality(text: string): boolean {
    const lines = text.split("\n");
    if (lines.length < 8) {
      return false;
    }

    const stepPatterns = [
      /^\s*\/\/\s*(Step\s+\d|First|Then|Next|Finally|Now)/i,
      /^\s*#\s*(Step\s+\d|First|Then|Next|Finally|Now)/i,
      /^\s*\/\*\*?\s*(Step\s+\d|First|Then|Next|Finally)/i,
    ];
    const stepComments = lines.filter((l) =>
      stepPatterns.some((p) => p.test(l)),
    );
    return stepComments.length >= 2;
  }

  private _isBoilerplateTemplate(text: string): boolean {
    const boilerplateSignatures = [
      /import\s+(?:React|express|fastify|flask)/,
      /export\s+default\s+function\s+App/,
      /const\s+app\s*=\s*express\(\)/,
      /class\s+\w+Controller/,
      /interface\s+\w+Props\s*\{/,
      /describe\s*\(\s*['"`]\w+['"`]\s*,\s*\(\s*\)\s*=>\s*\{/,
      /@(Component|Injectable|Controller|Module)\s*\(/,
    ];
    const matched = boilerplateSignatures.filter((p) => p.test(text));
    return (
      matched.length >= 2 ||
      (matched.length >= 1 && text.split("\n").length > 20)
    );
  }

  dispose(): void {
    // Stateless — nothing to clean up
  }
}
