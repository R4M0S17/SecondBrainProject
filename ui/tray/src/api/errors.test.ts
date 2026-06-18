import { describe, it, expect } from "vitest";
import { ApiError } from "./errors";

describe("ApiError", () => {
  it("creates error with status and detail", () => {
    const err = new ApiError(404, "Not found");
    expect(err.status).toBe(404);
    expect(err.detail).toBe("Not found");
    expect(err.message).toBe("API 404: Not found");
    expect(err).toBeInstanceOf(Error);
  });

  it("creates error with 500 status", () => {
    const err = new ApiError(500, "Internal server error");
    expect(err.status).toBe(500);
    expect(err.message).toBe("API 500: Internal server error");
  });

  it("handles empty detail", () => {
    const err = new ApiError(403, "");
    expect(err.message).toBe("API 403: ");
  });
});
