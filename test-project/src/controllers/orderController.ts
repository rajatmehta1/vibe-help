import { Router, Request, Response, NextFunction } from "express";
import * as orderService from "../services/orderService";
import { verifyAuthMiddleware } from "../middleware/auth";
import type { OrderStatus } from "../types";

const router = Router();

router.use(verifyAuthMiddleware);

router.post("/", async (req: Request, res: Response, next: NextFunction) => {
  try {
    const order = await orderService.createOrder({
      userId: req.user!.userId,
      items: req.body.items,
    });
    res.status(201).json(order);
  } catch (error) {
    next(error);
  }
});

router.get("/", async (req: Request, res: Response, next: NextFunction) => {
  try {
    const page = parseInt(req.query.page as string) || 1;
    const limit = parseInt(req.query.limit as string) || 20;
    const result = await orderService.fetchOrdersByUserId(req.user!.userId, {
      page,
      limit,
    });
    res.json(result);
  } catch (error) {
    next(error);
  }
});

router.get("/by-status/:status", async (req: Request, res: Response, next: NextFunction) => {
  try {
    const page = parseInt(req.query.page as string) || 1;
    const limit = parseInt(req.query.limit as string) || 20;
    const status = req.params.status as OrderStatus;
    const result = await orderService.fetchOrdersByStatus(status, { page, limit });
    res.json(result);
  } catch (error) {
    next(error);
  }
});

router.get("/summary", async (req: Request, res: Response, next: NextFunction) => {
  try {
    const summary = await orderService.fetchOrderSummary(req.user!.userId);
    res.json(summary);
  } catch (error) {
    next(error);
  }
});

router.get("/:id", async (req: Request, res: Response, next: NextFunction) => {
  try {
    const order = await orderService.fetchOrderById(req.params.id);
    res.json(order);
  } catch (error) {
    next(error);
  }
});

router.patch("/:id/status", async (req: Request, res: Response, next: NextFunction) => {
  try {
    const order = await orderService.updateOrderStatus(req.params.id, req.body.status);
    res.json(order);
  } catch (error) {
    next(error);
  }
});

router.delete("/:id", async (req: Request, res: Response, next: NextFunction) => {
  try {
    await orderService.deleteOrder(req.params.id);
    res.status(204).send();
  } catch (error) {
    next(error);
  }
});

export default router;
