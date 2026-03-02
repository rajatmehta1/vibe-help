import { Request, Response, NextFunction } from "express";
import jwt from "jsonwebtoken";
import type { AuthPayload } from "../types";
import { UnauthorizedError } from "../utils/errors";

const JWT_SECRET = process.env.JWT_SECRET || "dev-secret-key";

declare global {
  namespace Express {
    interface Request {
      user?: AuthPayload;
    }
  }
}

export function fetchAuthToken(req: Request): string | null {
  const header = req.headers.authorization;
  if (!header || !header.startsWith("Bearer ")) {
    return null;
  }
  return header.slice(7);
}

export function createAuthToken(payload: AuthPayload): string {
  return jwt.sign(payload, JWT_SECRET, { expiresIn: "24h" });
}

export function verifyAuthMiddleware(
  req: Request,
  _res: Response,
  next: NextFunction
): void {
  try {
    const token = fetchAuthToken(req);
    if (!token) {
      throw new UnauthorizedError("No authentication token provided");
    }

    const decoded = jwt.verify(token, JWT_SECRET) as AuthPayload;
    req.user = decoded;
    next();
  } catch (error) {
    if (error instanceof UnauthorizedError) {
      next(error);
    } else {
      next(new UnauthorizedError("Invalid or expired token"));
    }
  }
}

export function requireUser(
  req: Request,
  _res: Response,
  next: NextFunction
): void {
  if (!req.user) {
    next(new UnauthorizedError("User context not available"));
    return;
  }
  next();
}
