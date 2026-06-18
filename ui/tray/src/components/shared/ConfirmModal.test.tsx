import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ConfirmModal from "./ConfirmModal";

describe("ConfirmModal", () => {
  it("renders tool name and action", () => {
    render(
      <ConfirmModal
        toolName="write_file"
        toolPath="/tmp/test.txt"
        toolAction="Write content to file"
        onApprove={() => {}}
        onDeny={() => {}}
      />,
    );
    expect(screen.getByText("write_file")).toBeInTheDocument();
    expect(screen.getByText("/tmp/test.txt")).toBeInTheDocument();
    expect(screen.getByText("Write content to file")).toBeInTheDocument();
  });

  it("renders default warning text", () => {
    render(
      <ConfirmModal
        toolName="delete_file"
        onApprove={() => {}}
        onDeny={() => {}}
      />,
    );
    expect(
      screen.getByText(
        "This action will modify your filesystem. It cannot be automatically undone.",
      ),
    ).toBeInTheDocument();
  });

  it("renders custom warning text", () => {
    render(
      <ConfirmModal
        toolName="execute_python"
        warningText="Custom warning"
        onApprove={() => {}}
        onDeny={() => {}}
      />,
    );
    expect(screen.getByText("Custom warning")).toBeInTheDocument();
  });

  it("renders tool size when provided", () => {
    render(
      <ConfirmModal
        toolName="write_file"
        toolSize="2.4 KB"
        onApprove={() => {}}
        onDeny={() => {}}
      />,
    );
    expect(screen.getByText("(2.4 KB)")).toBeInTheDocument();
  });

  it("does not show path section when absent", () => {
    render(
      <ConfirmModal
        toolName="write_file"
        onApprove={() => {}}
        onDeny={() => {}}
      />,
    );
    expect(screen.queryByText("Path")).not.toBeInTheDocument();
  });

  it("calls onApprove when Approve button clicked", async () => {
    const onApprove = vi.fn();
    const user = userEvent.setup();
    render(
      <ConfirmModal
        toolName="write_file"
        onApprove={onApprove}
        onDeny={() => {}}
      />,
    );
    await user.click(screen.getByRole("button", { name: /approve/i }));
    expect(onApprove).toHaveBeenCalledTimes(1);
  });

  it("calls onDeny when Deny button clicked", async () => {
    const onDeny = vi.fn();
    const user = userEvent.setup();
    render(
      <ConfirmModal
        toolName="write_file"
        onApprove={() => {}}
        onDeny={onDeny}
      />,
    );
    await user.click(screen.getByRole("button", { name: /deny/i }));
    expect(onDeny).toHaveBeenCalledTimes(1);
  });

  it("has correct aria attributes", () => {
    render(
      <ConfirmModal
        toolName="write_file"
        onApprove={() => {}}
        onDeny={() => {}}
      />,
    );
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
    expect(screen.getByText("Tool requires your approval")).toHaveAttribute(
      "id",
      "confirm-modal-title",
    );
  });
});
