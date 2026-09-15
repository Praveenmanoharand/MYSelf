import { describe, expect, it } from "vitest";
import { calculateQuote } from "./quotation";

describe("calculateQuote", () => {
  it("calculates subtotal, tax, discount, and milestones deterministically", () => {
    const quote = calculateQuote({ currency: "USD", items: [{ id: "design", description: "Design", quantity: 2, unitPrice: 100 }], taxRate: 10, discount: 20, milestones: [{ label: "Start", percentage: 50 }] });
    expect(quote.subtotal).toBe(200);
    expect(quote.tax).toBe(18);
    expect(quote.total).toBe(198);
    expect(quote.milestoneAmounts[0].amount).toBe(99);
  });

  it("rejects invalid line items", () => {
    expect(() => calculateQuote({ currency: "USD", items: [{ id: "bad", description: "Bad", quantity: 0, unitPrice: 10 }] })).toThrow();
  });
});
