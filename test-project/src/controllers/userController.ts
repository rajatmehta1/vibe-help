import { Router, Request, Response, NextFunction } from "express";
import * as userService from "../services/userService";
import { createAuthToken } from "../middleware/auth";
import { verifyAuthMiddleware } from "../middleware/auth";
import { AppError, ValidationError } from "../utils/errors";

const router = Router();

router.post("/register", async (req: Request, res: Response, next: NextFunction) => {
  try {
    const user = await userService.createUser(req.body);
    const token = createAuthToken({ userId: user.id, email: user.email });

    res.status(201).json({
      user: {
        id: user.id,
        email: user.email,
        fullName: user.fullName,
      },
      token,
    });
  } catch (error) {
    next(error);
  }
});

router.post("/login", async (req: Request, res: Response, next: NextFunction) => {
  try {
    const { email, password } = req.body;
    const user = await userService.verifyUserPassword(email, password);
    const token = createAuthToken({ userId: user.id, email: user.email });

    res.json({
      user: {
        id: user.id,
        email: user.email,
        fullName: user.fullName,
      },
      token,
    });
  } catch (error) {
    next(error);
  }
});

router.get("/me", verifyAuthMiddleware, async (req: Request, res: Response, next: NextFunction) => {
  try {
    const user = await userService.fetchUserById(req.user!.userId);
    res.json({
      id: user.id,
      email: user.email,
      fullName: user.fullName,
      isActive: user.isActive,
    });
  } catch (error) {
    next(error);
  }
});

router.get("/", verifyAuthMiddleware, async (req: Request, res: Response, next: NextFunction) => {
  try {
    const page = parseInt(req.query.page as string) || 1;
    const limit = parseInt(req.query.limit as string) || 20;
    const result = await userService.fetchAllUsers({ page, limit });
    res.json(result);
  } catch (error) {
    next(error);
  }
});

router.get("/:id", verifyAuthMiddleware, async (req: Request, res: Response, next: NextFunction) => {
  try {
    const user = await userService.fetchUserById(req.params.id);
    res.json({
      id: user.id,
      email: user.email,
      fullName: user.fullName,
      isActive: user.isActive,
      createdAt: user.createdAt,
    });
  } catch (error) {
    next(error);
  }
});

router.put("/:id", verifyAuthMiddleware, async (req: Request, res: Response, next: NextFunction) => {
  try {
    const user = await userService.updateUser(req.params.id, req.body);
    res.json({
      id: user.id,
      email: user.email,
      fullName: user.fullName,
      isActive: user.isActive,
    });
  } catch (error) {
    next(error);
  }
});

router.delete("/:id", verifyAuthMiddleware, async (req: Request, res: Response, next: NextFunction) => {
  try {
    await userService.deleteUser(req.params.id);
    res.status(204).send();
  } catch (error) {
    next(error);
  }
});

export default router;
