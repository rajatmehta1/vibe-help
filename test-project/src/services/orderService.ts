import type {
  Order,
  OrderStatus,
  CreateOrderInput,
  PaginatedResult,
  PaginationParams,
} from "../types";
import * as orderRepository from "../repositories/orderRepository";
import * as userRepository from "../repositories/userRepository";
import { ValidationError, NotFoundError } from "../utils/errors";

const VALID_TRANSITIONS: Record<OrderStatus, OrderStatus[]> = {
  pending: ["confirmed", "cancelled"],
  confirmed: ["shipped", "cancelled"],
  shipped: ["delivered"],
  delivered: [],
  cancelled: [],
};

export async function fetchOrderById(id: string): Promise<Order> {
  return orderRepository.fetchOrderById(id);
}

export async function fetchOrdersByUserId(
  userId: string,
  params: PaginationParams
): Promise<PaginatedResult<Order>> {
  await userRepository.fetchUserById(userId);
  return orderRepository.fetchOrdersByUserId(userId, params);
}

export async function fetchOrdersByStatus(
  status: OrderStatus,
  params: PaginationParams
): Promise<PaginatedResult<Order>> {
  return orderRepository.fetchOrdersByStatus(status, params);
}

export async function createOrder(input: CreateOrderInput): Promise<Order> {
  const errors: Record<string, string[]> = {};

  if (!input.userId) {
    errors.userId = ["User ID is required"];
  }
  if (!input.items || input.items.length === 0) {
    errors.items = ["At least one order item is required"];
  }

  for (const [index, item] of input.items.entries()) {
    if (item.quantity <= 0) {
      errors[`items[${index}].quantity`] = ["Quantity must be positive"];
    }
    if (item.unitPrice < 0) {
      errors[`items[${index}].unitPrice`] = ["Price cannot be negative"];
    }
  }

  if (Object.keys(errors).length > 0) {
    throw new ValidationError(errors);
  }

  await userRepository.fetchUserById(input.userId);

  return orderRepository.createOrder(input.userId, input.items);
}

export async function updateOrderStatus(id: string, newStatus: OrderStatus): Promise<Order> {
  const order = await orderRepository.fetchOrderById(id);

  const allowedTransitions = VALID_TRANSITIONS[order.status];
  if (!allowedTransitions.includes(newStatus)) {
    throw new ValidationError({
      status: [`Cannot transition from '${order.status}' to '${newStatus}'`],
    });
  }

  return orderRepository.updateOrderStatus(id, newStatus);
}

export async function deleteOrder(id: string): Promise<void> {
  const order = await orderRepository.fetchOrderById(id);
  if (order.status !== "pending" && order.status !== "cancelled") {
    throw new ValidationError({
      status: ["Only pending or cancelled orders can be deleted"],
    });
  }
  return orderRepository.deleteOrder(id);
}

export async function fetchOrderSummary(
  userId: string
): Promise<{ totalOrders: number; totalSpent: number; statusBreakdown: Record<string, number> }> {
  const allOrders = await orderRepository.fetchOrdersByUserId(userId, {
    page: 1,
    limit: 1000,
  });

  const statusBreakdown: Record<string, number> = {};
  let totalSpent = 0;

  for (const order of allOrders.data) {
    statusBreakdown[order.status] = (statusBreakdown[order.status] || 0) + 1;
    if (order.status !== "cancelled") {
      totalSpent += order.totalAmount;
    }
  }

  return {
    totalOrders: allOrders.total,
    totalSpent,
    statusBreakdown,
  };
}
