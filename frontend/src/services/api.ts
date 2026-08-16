import type {Category,DashboardOverview,InventoryUpdateInput,Order,OrderCancelInput,OrderType,PaymentMethod,Product,ProductCreateInput,ProductUpdateInput,RestaurantTable,Settings,SettingsUpdate,StockAdjustmentInput,StockMovement,StockPurchaseInput} from "../types";
const API_URL=import.meta.env.VITE_API_URL||"http://127.0.0.1:8000";
async function request<T>(path:string,options?:RequestInit):Promise<T>{
 const r=await fetch(`${API_URL}${path}`,{headers:{"Content-Type":"application/json",...(options?.headers||{})},...options});
 if(!r.ok){let m="Request failed.";try{const b=await r.json();m=b.detail||m;}catch{}throw new Error(m);}
 return r.json();
}
export const api={
 getCatalogCategories:()=>request<Category[]>("/api/catalog/categories"),
 getCategories:()=>request<Category[]>("/api/categories"),
 getCatalogProducts:()=>request<Product[]>("/api/catalog/products"),
 getProducts:(search?:string,includeDisabled?:boolean)=>{
  const q=new URLSearchParams();
  if(search&&search.trim())q.set("search",search.trim());
  if(includeDisabled)q.set("include_disabled","true");
  const qs=q.toString();
  return request<Product[]>(`/api/products${qs?`?${qs}`:""}`);
 },
 getTables:()=>request<RestaurantTable[]>("/api/tables"),
 getOrders:(params?:{search?:string;status?:string})=>{
  const q=new URLSearchParams();
  if(params?.search&&params.search.trim())q.set("search",params.search.trim());
  if(params?.status)q.set("status",params.status);
  const qs=q.toString();
  return request<Order[]>(`/api/orders${qs?`?${qs}`:""}`);
 },
 createOrder:(p:{order_type:OrderType;table_id:number|null;items:{product_id:number;quantity:number}[];discount:number;tax_rate:number;payment_method:PaymentMethod;amount_received:number})=>request<Order>("/api/orders",{method:"POST",body:JSON.stringify(p)}),
 // Order cancellation (Phase 7) — never deletes the order, just flips status to
 // CANCELLED with a required reason; inventory restoration is a Phase 8 concern.
 cancelOrder:(id:number,payload:OrderCancelInput)=>request<Order>(`/api/orders/${id}/cancel`,{method:"POST",body:JSON.stringify(payload)}),
 // Inventory (Phase 3) — same Product row as the catalog endpoints above, just
 // exposed through inventory-focused routes (search, add-stock, edit).
 getInventory:(search?:string)=>request<Product[]>(`/api/inventory${search&&search.trim()?`?search=${encodeURIComponent(search.trim())}`:""}`),
 getInventoryItem:(id:number)=>request<Product>(`/api/inventory/${id}`),
 updateInventoryItem:(id:number,payload:InventoryUpdateInput)=>request<Product>(`/api/inventory/${id}`,{method:"PUT",body:JSON.stringify(payload)}),
 // Stock operations (Phase 4) — Add Stock (purchase) and Stock Adjustment both
 // return the updated Product, and both write a StockMovement row server-side.
 addStock:(id:number,payload:StockPurchaseInput)=>request<Product>(`/api/inventory/${id}/stock`,{method:"POST",body:JSON.stringify(payload)}),
 adjustStock:(id:number,payload:StockAdjustmentInput)=>request<Product>(`/api/inventory/${id}/adjust`,{method:"POST",body:JSON.stringify(payload)}),
 getStockMovements:(params?:{search?:string;movement_type?:string;date?:string})=>{
  const q=new URLSearchParams();
  if(params?.search&&params.search.trim())q.set("search",params.search.trim());
  if(params?.movement_type)q.set("movement_type",params.movement_type);
  if(params?.date)q.set("date",params.date);
  const qs=q.toString();
  return request<StockMovement[]>(`/api/stock-movements${qs?`?${qs}`:""}`);
 },
 // Settings (Task 1.1) — restaurant configuration
 getSettings:()=>request<Settings>("/api/settings"),
 updateSettings:(p:SettingsUpdate)=>request<Settings>("/api/settings",{method:"PATCH",body:JSON.stringify(p)}),
 // Dashboard (Phase 9) — today's business metrics
 getDashboardOverview:()=>request<DashboardOverview>("/api/dashboard/overview"),
 // Product Management (Phase 10)
 getProduct:(id:number)=>request<Product>(`/api/products/${id}`),
 createProduct:(p:ProductCreateInput)=>request<Product>("/api/products",{method:"POST",body:JSON.stringify(p)}),
 updateProduct:(id:number,p:ProductUpdateInput)=>request<Product>(`/api/products/${id}`,{method:"PUT",body:JSON.stringify(p)}),
 disableProduct:(id:number)=>request<Product>(`/api/products/${id}/disable`,{method:"PATCH",body:JSON.stringify({})}),
 enableProduct:(id:number)=>request<Product>(`/api/products/${id}/enable`,{method:"PATCH",body:JSON.stringify({})})
};
