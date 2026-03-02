import { Request, Response, NextFunction } from "express";
import * as crypto from "crypto";
import { UserService } from "./services/user-service";
import { Logger } from "../utils/logger";

// Constants
export const MAX_RETRIES = 3;
const DEFAULT_TIMEOUT = 5000;

// Type alias
export type UserId = string;

/**
 * Represents a generic API response.
 */
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  error?: string;
  timestamp: number;
}

/**
 * Configuration options for the middleware.
 */
export interface MiddlewareConfig {
  enableLogging: boolean;
  timeout: number;
  retries: number;
}

/**
 * Base class for all handlers.
 */
export class BaseHandler {
  protected logger: Logger;

  constructor(protected name: string) {
    this.logger = new Logger(name);
  }

  /**
   * Initialize the handler.
   */
  async initialize(): Promise<void> {
    this.logger.info(`Initializing ${this.name}`);
  }

  protected handleError(error: Error): ApiResponse<null> {
    this.logger.error(error.message);
    return {
      success: false,
      data: null,
      error: error.message,
      timestamp: Date.now(),
    };
  }
}

/**
 * Handles user-related API requests.
 */
export class UserHandler extends BaseHandler {
  private userService: UserService;

  constructor(userService: UserService) {
    super("UserHandler");
    this.userService = userService;
  }

  async getUser(req: Request, res: Response): Promise<void> {
    try {
      const userId = req.params.id;
      const user = await this.userService.findById(userId);
      if (user) {
        res.json({ success: true, data: user, timestamp: Date.now() });
      } else {
        res.status(404).json(this.handleError(new Error("User not found")));
      }
    } catch (error) {
      res.status(500).json(this.handleError(error as Error));
    }
  }

  async createUser(req: Request, res: Response): Promise<void> {
    const { email, name } = req.body;
    if (!email || !name) {
      res.status(400).json(this.handleError(new Error("Missing fields")));
      return;
    }
    const user = await this.userService.create({ email, name });
    res.status(201).json({ success: true, data: user, timestamp: Date.now() });
  }
}

/**
 * Simple utility function.
 */
export function generateId(prefix: string = "id"): string {
  return `${prefix}_${crypto.randomUUID()}`;
}

/**
 * Async function that fetches data with retries.
 */
export async function fetchWithRetry(
  url: string,
  options: RequestInit = {},
  retries: number = MAX_RETRIES
): Promise<Response> {
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const response = await fetch(url, options);
      if (response.ok) {
        return response;
      }
      if (response.status >= 500 && attempt < retries - 1) {
        continue;
      }
      throw new Error(`HTTP ${response.status}`);
    } catch (error) {
      if (attempt === retries - 1) {
        throw error;
      }
    }
  }
  throw new Error("Unreachable");
}

function _internalHelper(data: string[]): string[] {
  return data.filter((item) => item.length > 0).map((item) => item.trim());
}

/**
 * Arrow function exported as const.
 */
export const processItems = async (
  items: Array<{ id: string; value: number }>
): Promise<Array<{ id: string; result: number }>> => {
  return items.map((item) => ({
    id: item.id,
    result: item.value * 2,
  }));
};

export const createMiddleware = (config: MiddlewareConfig) => {
  return (req: Request, _res: Response, next: NextFunction): void => {
    if (config.enableLogging) {
      console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
    }
    next();
  };
};

class InternalCache<T> {
  private store = new Map<string, T>();

  set(key: string, value: T): void {
    this.store.set(key, value);
  }

  get(key: string): T | undefined {
    return this.store.get(key);
  }

  has(key: string): boolean {
    return this.store.has(key);
  }

  clear(): void {
    this.store.clear();
  }
}
