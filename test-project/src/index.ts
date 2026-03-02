import express from "express";
import userController from "./controllers/userController";
import orderController from "./controllers/orderController";
import { AppError, ValidationError } from "./utils/errors";

const app = express();
const PORT = process.env.PORT || 3001;

app.use(express.json());

// Routes
app.use("/api/users", userController);
app.use("/api/orders", orderController);

// Health check
app.get("/health", (_req, res) => {
  res.json({ status: "ok", timestamp: new Date().toISOString() });
});

// Global error handler
app.use((err: Error, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  if (err instanceof ValidationError) {
    res.status(err.statusCode).json({
      error: err.message,
      errors: err.errors,
    });
    return;
  }

  if (err instanceof AppError) {
    res.status(err.statusCode).json({
      error: err.message,
    });
    return;
  }

  console.error("Unhandled error:", err);
  res.status(500).json({
    error: "Internal server error",
  });
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

export default app;
