/**
 * GroupByToggle component tests.
 *
 * Covered:
 * 1. Renders "Group by:" label with Level and Type buttons.
 * 2. The active mode button has aria-pressed=true.
 * 3. Clicking the inactive button calls onChange with the new mode.
 * 4. Clicking the already-active button still calls onChange.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { GroupByToggle } from "../../components/GroupByToggle";

describe("GroupByToggle", () => {
  it("renders Group by label with Level and Type buttons", () => {
    render(<GroupByToggle value="level" onChange={() => {}} />);
    expect(screen.getByText(/group by:/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Level" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Type" })).toBeInTheDocument();
  });

  it("Level button has aria-pressed=true when value=level", () => {
    render(<GroupByToggle value="level" onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Level" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(screen.getByRole("button", { name: "Type" })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
  });

  it("Type button has aria-pressed=true when value=type", () => {
    render(<GroupByToggle value="type" onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Type" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(screen.getByRole("button", { name: "Level" })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
  });

  it("calls onChange with 'type' when Type button is clicked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<GroupByToggle value="level" onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: "Type" }));
    expect(onChange).toHaveBeenCalledWith("type");
  });

  it("calls onChange with 'level' when Level button is clicked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<GroupByToggle value="type" onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: "Level" }));
    expect(onChange).toHaveBeenCalledWith("level");
  });
});
