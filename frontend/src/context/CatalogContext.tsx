import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { api } from "../services/api";
import type { Category, Product, RestaurantTable } from "../types";

interface CatalogContextType {
  // For POS grid — active products in active categories only
  catalogProducts: Product[];
  catalogCategories: Category[];

  // For management screens — all products and all categories
  allProducts: Product[];
  allCategories: Category[];

  // For table selection in DINE_IN orders
  tables: RestaurantTable[];

  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

const CatalogContext = createContext<CatalogContextType | undefined>(undefined);

export function CatalogProvider({ children }: { children: React.ReactNode }) {
  const [catalogProducts, setCatalogProducts] = useState<Product[]>([]);
  const [catalogCategories, setCatalogCategories] = useState<Category[]>([]);
  const [allProducts, setAllProducts] = useState<Product[]>([]);
  const [allCategories, setAllCategories] = useState<Category[]>([]);
  const [tables, setTables] = useState<RestaurantTable[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [
        catalogProds,
        catalogCats,
        allProds,
        allCats,
        tablesData,
      ] = await Promise.all([
        api.getCatalogProducts(),
        api.getCatalogCategories(),
        api.getProducts(undefined, true),
        api.getCategories(),
        api.getTables(),
      ]);

      setCatalogProducts(catalogProds);
      setCatalogCategories(catalogCats);
      setAllProducts(allProds);
      setAllCategories(allCats);
      setTables(tablesData);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not refresh catalog");
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial load on mount
  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <CatalogContext.Provider
      value={{
        catalogProducts,
        catalogCategories,
        allProducts,
        allCategories,
        tables,
        isLoading,
        error,
        refresh,
      }}
    >
      {children}
    </CatalogContext.Provider>
  );
}

export function useCatalog() {
  const context = useContext(CatalogContext);
  if (!context) {
    throw new Error("useCatalog must be used within CatalogProvider");
  }
  return context;
}
