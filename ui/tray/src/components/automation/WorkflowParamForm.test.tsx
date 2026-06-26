import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import WorkflowParamForm from "./WorkflowParamForm";

describe("WorkflowParamForm", () => {
  it("renders parameter inputs", () => {
    const onChange = vi.fn();
    render(
      <WorkflowParamForm
        parameters={[
          { name: "folder", type: "path", description: "Destination folder", default: "~/Desktop" },
        ]}
        values={{ folder: "~/Desktop" }}
        onChange={onChange}
      />,
    );
    expect(screen.getByDisplayValue("~/Desktop")).toBeInTheDocument();
    fireEvent.change(screen.getByDisplayValue("~/Desktop"), { target: { value: "~/Docs" } });
    expect(onChange).toHaveBeenCalledWith("folder", "~/Docs");
  });
});
