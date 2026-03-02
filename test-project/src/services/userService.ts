import bcrypt from "bcryptjs";
import type { User, CreateUserInput, UpdateUserInput, PaginatedResult, PaginationParams } from "../types";
import * as userRepository from "../repositories/userRepository";
import { ValidationError, NotFoundError } from "../utils/errors";

const SALT_ROUNDS = 12;

export async function fetchUserById(id: string): Promise<User> {
  return userRepository.fetchUserById(id);
}

export async function fetchUserByEmail(email: string): Promise<User | null> {
  return userRepository.fetchUserByEmail(email);
}

export async function fetchAllUsers(params: PaginationParams): Promise<PaginatedResult<User>> {
  return userRepository.fetchAllUsers(params);
}

export async function createUser(input: CreateUserInput): Promise<User> {
  const errors: Record<string, string[]> = {};

  if (!input.email || !input.email.includes("@")) {
    errors.email = ["A valid email address is required"];
  }
  if (!input.fullName || input.fullName.trim().length < 2) {
    errors.fullName = ["Full name must be at least 2 characters"];
  }
  if (!input.password || input.password.length < 8) {
    errors.password = ["Password must be at least 8 characters"];
  }

  if (Object.keys(errors).length > 0) {
    throw new ValidationError(errors);
  }

  const existing = await userRepository.fetchUserByEmail(input.email);
  if (existing) {
    throw new ValidationError({ email: ["Email already in use"] });
  }

  const passwordHash = await bcrypt.hash(input.password, SALT_ROUNDS);

  return userRepository.createUser({
    email: input.email,
    fullName: input.fullName,
    password: input.password,
    passwordHash,
  });
}

export async function updateUser(id: string, input: UpdateUserInput): Promise<User> {
  const user = await userRepository.fetchUserById(id);
  if (!user) {
    throw new NotFoundError("User", id);
  }

  if (input.email !== undefined) {
    if (!input.email.includes("@")) {
      throw new ValidationError({ email: ["A valid email address is required"] });
    }
    const existing = await userRepository.fetchUserByEmail(input.email);
    if (existing && existing.id !== id) {
      throw new ValidationError({ email: ["Email already in use"] });
    }
  }

  return userRepository.updateUser(id, input);
}

export async function deleteUser(id: string): Promise<void> {
  return userRepository.deleteUser(id);
}

export async function verifyUserPassword(email: string, password: string): Promise<User> {
  const user = await userRepository.fetchUserByEmail(email);
  if (!user) {
    throw new NotFoundError("User");
  }

  const isValid = await bcrypt.compare(password, user.passwordHash);
  if (!isValid) {
    throw new ValidationError({ password: ["Invalid credentials"] });
  }

  return user;
}
