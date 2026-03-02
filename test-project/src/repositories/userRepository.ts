import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";
import type { User, CreateUserInput, UpdateUserInput, PaginatedResult, PaginationParams } from "../types";
import { NotFoundError } from "../utils/errors";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL || "postgresql://localhost:5432/testdb",
});

export async function fetchUserById(id: string): Promise<User> {
  const result = await pool.query(
    "SELECT * FROM users WHERE id = $1",
    [id]
  );
  if (result.rows.length === 0) {
    throw new NotFoundError("User", id);
  }
  return mapRowToUser(result.rows[0]);
}

export async function fetchUserByEmail(email: string): Promise<User | null> {
  const result = await pool.query(
    "SELECT * FROM users WHERE email = $1",
    [email]
  );
  if (result.rows.length === 0) {
    return null;
  }
  return mapRowToUser(result.rows[0]);
}

export async function fetchAllUsers(params: PaginationParams): Promise<PaginatedResult<User>> {
  const offset = (params.page - 1) * params.limit;

  const [dataResult, countResult] = await Promise.all([
    pool.query(
      "SELECT * FROM users ORDER BY created_at DESC LIMIT $1 OFFSET $2",
      [params.limit, offset]
    ),
    pool.query("SELECT COUNT(*) as total FROM users"),
  ]);

  const total = parseInt(countResult.rows[0].total, 10);

  return {
    data: dataResult.rows.map(mapRowToUser),
    total,
    page: params.page,
    limit: params.limit,
    totalPages: Math.ceil(total / params.limit),
  };
}

export async function createUser(input: CreateUserInput & { passwordHash: string }): Promise<User> {
  const id = uuidv4();
  const now = new Date();

  const result = await pool.query(
    `INSERT INTO users (id, email, full_name, password_hash, is_active, created_at, updated_at)
     VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING *`,
    [id, input.email, input.fullName, input.passwordHash, true, now, now]
  );

  return mapRowToUser(result.rows[0]);
}

export async function updateUser(id: string, input: UpdateUserInput): Promise<User> {
  const existing = await fetchUserById(id);

  const email = input.email ?? existing.email;
  const fullName = input.fullName ?? existing.fullName;
  const isActive = input.isActive ?? existing.isActive;
  const now = new Date();

  const result = await pool.query(
    `UPDATE users SET email = $1, full_name = $2, is_active = $3, updated_at = $4
     WHERE id = $5 RETURNING *`,
    [email, fullName, isActive, now, id]
  );

  return mapRowToUser(result.rows[0]);
}

export async function deleteUser(id: string): Promise<void> {
  const result = await pool.query("DELETE FROM users WHERE id = $1", [id]);
  if (result.rowCount === 0) {
    throw new NotFoundError("User", id);
  }
}

function mapRowToUser(row: Record<string, unknown>): User {
  return {
    id: row.id as string,
    email: row.email as string,
    fullName: row.full_name as string,
    passwordHash: row.password_hash as string,
    isActive: row.is_active as boolean,
    createdAt: new Date(row.created_at as string),
    updatedAt: new Date(row.updated_at as string),
  };
}
