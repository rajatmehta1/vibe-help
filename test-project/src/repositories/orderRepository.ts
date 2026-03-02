import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";
import type { Order, OrderItem, OrderStatus, PaginatedResult, PaginationParams } from "../types";
import { NotFoundError } from "../utils/errors";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL || "postgresql://localhost:5432/testdb",
});

export async function fetchOrderById(id: string): Promise<Order> {
  const orderResult = await pool.query(
    "SELECT * FROM orders WHERE id = $1",
    [id]
  );
  if (orderResult.rows.length === 0) {
    throw new NotFoundError("Order", id);
  }

  const itemsResult = await pool.query(
    "SELECT * FROM order_items WHERE order_id = $1",
    [id]
  );

  return mapRowToOrder(orderResult.rows[0], itemsResult.rows);
}

export async function fetchOrdersByUserId(
  userId: string,
  params: PaginationParams
): Promise<PaginatedResult<Order>> {
  const offset = (params.page - 1) * params.limit;

  const [dataResult, countResult] = await Promise.all([
    pool.query(
      "SELECT * FROM orders WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
      [userId, params.limit, offset]
    ),
    pool.query("SELECT COUNT(*) as total FROM orders WHERE user_id = $1", [userId]),
  ]);

  const total = parseInt(countResult.rows[0].total, 10);
  const orders = await Promise.all(
    dataResult.rows.map(async (row) => {
      const items = await pool.query(
        "SELECT * FROM order_items WHERE order_id = $1",
        [row.id]
      );
      return mapRowToOrder(row, items.rows);
    })
  );

  return {
    data: orders,
    total,
    page: params.page,
    limit: params.limit,
    totalPages: Math.ceil(total / params.limit),
  };
}

export async function fetchOrdersByStatus(
  status: OrderStatus,
  params: PaginationParams
): Promise<PaginatedResult<Order>> {
  const offset = (params.page - 1) * params.limit;

  const [dataResult, countResult] = await Promise.all([
    pool.query(
      "SELECT * FROM orders WHERE status = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
      [status, params.limit, offset]
    ),
    pool.query("SELECT COUNT(*) as total FROM orders WHERE status = $1", [status]),
  ]);

  const total = parseInt(countResult.rows[0].total, 10);
  const orders = await Promise.all(
    dataResult.rows.map(async (row) => {
      const items = await pool.query(
        "SELECT * FROM order_items WHERE order_id = $1",
        [row.id]
      );
      return mapRowToOrder(row, items.rows);
    })
  );

  return {
    data: orders,
    total,
    page: params.page,
    limit: params.limit,
    totalPages: Math.ceil(total / params.limit),
  };
}

export async function createOrder(
  userId: string,
  items: { productId: string; productName: string; quantity: number; unitPrice: number }[]
): Promise<Order> {
  const orderId = uuidv4();
  const now = new Date();
  const totalAmount = items.reduce((sum, item) => sum + item.quantity * item.unitPrice, 0);

  await pool.query(
    `INSERT INTO orders (id, user_id, status, total_amount, created_at, updated_at)
     VALUES ($1, $2, $3, $4, $5, $6)`,
    [orderId, userId, "pending", totalAmount, now, now]
  );

  const orderItems: OrderItem[] = [];
  for (const item of items) {
    const itemId = uuidv4();
    await pool.query(
      `INSERT INTO order_items (id, order_id, product_id, product_name, quantity, unit_price)
       VALUES ($1, $2, $3, $4, $5, $6)`,
      [itemId, orderId, item.productId, item.productName, item.quantity, item.unitPrice]
    );
    orderItems.push({
      id: itemId,
      orderId,
      productId: item.productId,
      productName: item.productName,
      quantity: item.quantity,
      unitPrice: item.unitPrice,
    });
  }

  return {
    id: orderId,
    userId,
    status: "pending",
    totalAmount,
    items: orderItems,
    createdAt: now,
    updatedAt: now,
  };
}

export async function updateOrderStatus(id: string, status: OrderStatus): Promise<Order> {
  const result = await pool.query(
    "UPDATE orders SET status = $1, updated_at = $2 WHERE id = $3 RETURNING *",
    [status, new Date(), id]
  );

  if (result.rows.length === 0) {
    throw new NotFoundError("Order", id);
  }

  const itemsResult = await pool.query(
    "SELECT * FROM order_items WHERE order_id = $1",
    [id]
  );

  return mapRowToOrder(result.rows[0], itemsResult.rows);
}

export async function deleteOrder(id: string): Promise<void> {
  await pool.query("DELETE FROM order_items WHERE order_id = $1", [id]);
  const result = await pool.query("DELETE FROM orders WHERE id = $1", [id]);
  if (result.rowCount === 0) {
    throw new NotFoundError("Order", id);
  }
}

function mapRowToOrder(row: Record<string, unknown>, itemRows: Record<string, unknown>[]): Order {
  return {
    id: row.id as string,
    userId: row.user_id as string,
    status: row.status as OrderStatus,
    totalAmount: parseFloat(row.total_amount as string),
    items: itemRows.map(mapRowToOrderItem),
    createdAt: new Date(row.created_at as string),
    updatedAt: new Date(row.updated_at as string),
  };
}

function mapRowToOrderItem(row: Record<string, unknown>): OrderItem {
  return {
    id: row.id as string,
    orderId: row.order_id as string,
    productId: row.product_id as string,
    productName: row.product_name as string,
    quantity: row.quantity as number,
    unitPrice: parseFloat(row.unit_price as string),
  };
}
