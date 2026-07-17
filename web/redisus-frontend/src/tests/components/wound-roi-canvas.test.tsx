import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WoundRoiCanvas } from "../../components/roi/WoundRoiCanvas";

describe("WoundRoiCanvas", () => {
  it("usa a roda para zoom sem propagar a rolagem para a página", () => {
    const pageWheelHandler = vi.fn();
    document.addEventListener("wheel", pageWheelHandler);

    render(
      <WoundRoiCanvas
        imageSrc="data:image/png;base64,"
        onConfirm={vi.fn()}
        onSelectionCleared={vi.fn()}
      />,
    );

    const viewport = screen.getByTestId("wound-roi-viewport");
    const wheelEvent = new WheelEvent("wheel", {
      bubbles: true,
      cancelable: true,
      clientX: 200,
      clientY: 200,
      deltaY: -100,
    });

    act(() => viewport.dispatchEvent(wheelEvent));

    expect(wheelEvent.defaultPrevented).toBe(true);
    expect(pageWheelHandler).not.toHaveBeenCalled();
    expect(screen.getByText("125%")).toBeInTheDocument();

    document.removeEventListener("wheel", pageWheelHandler);
  });

  it("mantém as outras ferramentas selecionáveis depois de ativar a mão", () => {
    render(
      <WoundRoiCanvas
        imageSrc="data:image/png;base64,"
        onConfirm={vi.fn()}
        onSelectionCleared={vi.fn()}
      />,
    );

    const viewport = screen.getByTestId("wound-roi-viewport");
    const handTool = screen.getByRole("button", { name: "Mover canvas" });
    const freehandTool = screen.getByRole("button", { name: "Desenho livre" });

    fireEvent.click(handTool);
    expect(handTool).toHaveAttribute("aria-pressed", "true");

    fireEvent.pointerDown(freehandTool, { button: 0, pointerId: 1 });
    expect(viewport).not.toHaveClass("cursor-grabbing");

    fireEvent.click(freehandTool);
    expect(handTool).toHaveAttribute("aria-pressed", "false");
    expect(freehandTool).toHaveAttribute("aria-pressed", "true");
  });
});
