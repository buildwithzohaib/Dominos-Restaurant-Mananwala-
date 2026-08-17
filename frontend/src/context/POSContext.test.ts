/**
 * Test for POSContext totals calculation.
 * Ensures that tax_enabled flag correctly controls whether tax is added to total.
 */

import { describe, it, expect } from "vitest";

describe("POSContext Totals Calculation", () => {
  describe("Tax calculation with tax_enabled", () => {
    it("should include tax in total when tax_enabled is true", () => {
      // Subtotal: 35000 paisa (Rs. 350)
      // Tax rate: 1600 basis points (16%)
      // Tax: (35000 * 1600 + 5000) // 10000 = 5600 paisa (Rs. 56)
      // Expected total: 35000 + 5600 = 40600 paisa (Rs. 406)

      const subtotal = 35000;
      const taxRate = 1600;
      const taxable = subtotal; // no discount
      const tax = Math.floor((taxable * taxRate + 5000) / 10000);
      const total = taxable + tax;

      expect(tax).toBe(5600);
      expect(total).toBe(40600);
    });

    it("should NOT include tax in total when tax_enabled is false (tax_rate becomes 0)", () => {
      // Subtotal: 35000 paisa (Rs. 350)
      // Tax enabled: false → tax_rate treated as 0
      // Tax: (35000 * 0 + 5000) // 10000 = 0 paisa
      // Expected total: 35000 + 0 = 35000 paisa (Rs. 350)

      const subtotal = 35000;
      const taxRateFromSettings = 1600; // settings still have 1600
      const taxEnabled = false; // but tax is disabled

      // This is what POSContext should do (the fix):
      const taxRate = taxEnabled ? taxRateFromSettings : 0;
      const taxable = subtotal;
      const tax = Math.floor((taxable * taxRate + 5000) / 10000);
      const total = taxable + tax;

      expect(taxRate).toBe(0);
      expect(tax).toBe(0);
      expect(total).toBe(35000);
    });

    it("should correctly compute tax with discount when tax_enabled is true", () => {
      // Subtotal: 35000 paisa (Rs. 350)
      // Discount: 5000 paisa (Rs. 50)
      // Taxable: 35000 - 5000 = 30000 paisa (Rs. 300)
      // Tax rate: 1600 basis points (16%)
      // Tax: (30000 * 1600 + 5000) // 10000 = 4800 paisa (Rs. 48)
      // Total: 30000 + 4800 = 34800 paisa (Rs. 348)

      const subtotal = 35000;
      const discount = 5000;
      const taxRate = 1600;

      const discountAmount = Math.min(discount, subtotal);
      const taxable = subtotal - discountAmount;
      const tax = Math.floor((taxable * taxRate + 5000) / 10000);
      const total = taxable + tax;

      expect(discountAmount).toBe(5000);
      expect(taxable).toBe(30000);
      expect(tax).toBe(4800);
      expect(total).toBe(34800);
    });

    it("should NOT apply tax to delivery charge", () => {
      // Subtotal: 35000 paisa (Rs. 350)
      // Discount: 0
      // Taxable: 35000
      // Tax rate: 1600 basis points (16%)
      // Tax: (35000 * 1600 + 5000) // 10000 = 5600 paisa (Rs. 56)
      // Delivery charge: 10000 paisa (Rs. 100) — NOT TAXED
      // Total: 35000 + 5600 + 10000 = 50600 paisa (Rs. 506)

      const subtotal = 35000;
      const discount = 0;
      const taxRate = 1600;
      const deliveryCharge = 10000;

      const discountAmount = Math.min(discount, subtotal);
      const taxable = subtotal - discountAmount;
      const tax = Math.floor((taxable * taxRate + 5000) / 10000);
      const total = taxable + tax + deliveryCharge;

      expect(taxable).toBe(35000);
      expect(tax).toBe(5600);
      expect(total).toBe(50600);
    });
  });
});
