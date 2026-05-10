/**
 * GroupByToggle component tests.
 *
 * Covered:
 * 1. Renders "Group by:" label with Level and Type radio buttons.
 * 2. The wrapper has role="radiogroup".
 * 3. Each button has role="radio".
 * 4. The active mode button has aria-checked=true; inactive has aria-checked=false.
 * 5. Clicking the inactive button calls onChange with the new mode.
 * 6. Clicking the already-active button still calls onChange.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { GroupByToggle } from "../../components/GroupByToggle";

describe("GroupByToggle", () => {
  it("renders Group by label with Level and Type radio buttons", () => {
    render(<GroupByToggle value="level" onChange={() => {}} />);
    expect(screen.getByText(/group by:/i)).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Level" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Type" })).toBeInTheDocument();
  });

  it("wrapper has role=radiogroup", () => {
    render(<GroupByToggle value="level" onChange={() => {}} />);
    expect(
      screen.getByRole("radiogroup", { name: /group by/i })
    ).toBeInTheDocument();
  });

  it("Level radio has aria-checked=true when value=level", () => {
    render(<GroupByToggle value="level" onChange={() => {}} />);
    expect(screen.getByRole("radio", { name: "Level" })).toHaveAttribute(
      "aria-checked",
      "true"
    );
    expect(screen.getByRole("radio", { name: "Type" })).toHaveAttribute(
      "aria-checked",
      "false"
    );
  });

  it("Type radio has aria-checked=true when value=type", () => {
    render(<GroupByToggle value="type" onChange={() => {}} />);
    expect(screen.getByRole("radio", { name: "Type" })).toHaveAttribute(
      "aria-checked",
      "true"
    );
    expect(screen.getByRole("radio", { name: "Level" })).toHaveAttribute(
      "aria-checked",
      "false"
    );
  });

  it("calls onChange with 'type' when Type radio is clicked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<GroupByToggle value="level" onChange={onChange} />);
    await user.click(screen.getByRole("radio", { name: "Type" }));
    expect(onChange).toHaveBeenCalledWith("type");
  });

  it("calls onChange with 'level' when Level radio is clicked", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<GroupByToggle value="type" onChange={onChange} />);
    await user.click(screen.getByRole("radio", { name: "Level" }));
    expect(onChange).toHaveBeenCalledWith("level");
  });
});
