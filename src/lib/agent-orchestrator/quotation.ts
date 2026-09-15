export type QuoteItem = { id: string; description: string; quantity: number; unitPrice: number };
export type PaymentMilestone = { label: string; percentage: number };
export type QuoteInput = { items: QuoteItem[]; currency: string; taxRate?: number; discount?: number; milestones?: PaymentMilestone[] };
export type Quote = QuoteInput & { subtotal: number; tax: number; total: number; milestoneAmounts: Array<PaymentMilestone & { amount: number }> };

const money = (value: number) => Math.round((value + Number.EPSILON) * 100) / 100;

export function calculateQuote(input: QuoteInput): Quote {
  if (!input.items.length) throw new Error("A quotation requires at least one item.");
  if (input.items.some((item) => item.quantity <= 0 || item.unitPrice < 0)) throw new Error("Quantities must be positive and unit prices cannot be negative.");
  const taxRate = input.taxRate ?? 0;
  const discount = input.discount ?? 0;
  if (taxRate < 0 || taxRate > 100 || discount < 0) throw new Error("Invalid tax rate or discount.");
  if (input.milestones?.some((milestone) => milestone.percentage < 0) || (input.milestones ?? []).reduce((sum, milestone) => sum + milestone.percentage, 0) > 100) throw new Error("Payment milestones must total no more than 100%.");
  const subtotal = money(input.items.reduce((sum, item) => sum + item.quantity * item.unitPrice, 0));
  const taxable = Math.max(0, subtotal - discount);
  const tax = money(taxable * taxRate / 100);
  const total = money(taxable + tax);
  return { ...input, taxRate, discount, subtotal, tax, total, milestoneAmounts: (input.milestones ?? []).map((milestone) => ({ ...milestone, amount: money(total * milestone.percentage / 100) })) };
}
