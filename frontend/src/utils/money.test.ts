import { describe, it, expect } from "vitest";
import {
  formatMoney,
  formatSouthAsianGrouping,
  rupeesToPaisa,
  paisaToRupees,
} from "./money";

describe("formatMoney", () => {
  it("formats 125000 as Rs. 1,250", () => {
    expect(formatMoney(125000)).toBe("Rs. 1,250");
  });

  it("formats 12345600 as Rs. 1,23,456", () => {
    expect(formatMoney(12345600)).toBe("Rs. 1,23,456");
  });

  it("formats 100000000 as Rs. 10,00,000", () => {
    expect(formatMoney(100000000)).toBe("Rs. 10,00,000");
  });

  it("formats 45050 as Rs. 450.50", () => {
    expect(formatMoney(45050)).toBe("Rs. 450.50");
  });

  it("formats 45005 as Rs. 450.05 (zero-padded paisa)", () => {
    expect(formatMoney(45005)).toBe("Rs. 450.05");
  });

  it("formats 99 as Rs. 0.99", () => {
    expect(formatMoney(99)).toBe("Rs. 0.99");
  });

  it("formats 0 as Rs. 0", () => {
    expect(formatMoney(0)).toBe("Rs. 0");
  });

  it("formats -5650 as Rs. -56.50", () => {
    expect(formatMoney(-5650)).toBe("Rs. -56.50");
  });

  it("formats -5600 as Rs. -56", () => {
    expect(formatMoney(-5600)).toBe("Rs. -56");
  });

  it("formats null as Rs. 0", () => {
    expect(formatMoney(null)).toBe("Rs. 0");
  });

  it("formats undefined as Rs. 0", () => {
    expect(formatMoney(undefined)).toBe("Rs. 0");
  });
});

describe("formatSouthAsianGrouping", () => {
  it("formats 999 as 999", () => {
    expect(formatSouthAsianGrouping(999)).toBe("999");
  });

  it("formats 1250 as 1,250", () => {
    expect(formatSouthAsianGrouping(1250)).toBe("1,250");
  });

  it("formats 123456 as 1,23,456", () => {
    expect(formatSouthAsianGrouping(123456)).toBe("1,23,456");
  });

  it("formats 10000000 as 1,00,00,000", () => {
    expect(formatSouthAsianGrouping(10000000)).toBe("1,00,00,000");
  });
});

describe("rupeesToPaisa", () => {
  it("converts 450 to 45000", () => {
    expect(rupeesToPaisa(450)).toBe(45000);
  });

  it("converts 450.50 to 45050", () => {
    expect(rupeesToPaisa(450.50)).toBe(45050);
  });

  it("converts 0.99 to 99", () => {
    expect(rupeesToPaisa(0.99)).toBe(99);
  });

  it("converts 0 to 0", () => {
    expect(rupeesToPaisa(0)).toBe(0);
  });
});

describe("paisaToRupees", () => {
  it("converts 45050 to 450.5", () => {
    expect(paisaToRupees(45050)).toBe(450.5);
  });
});
