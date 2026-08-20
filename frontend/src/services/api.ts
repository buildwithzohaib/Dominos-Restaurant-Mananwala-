import type {Category,Customer,CustomerCreateInput,CustomerSearchResult,CustomerUpdateInput,DashboardOverview,InventoryUpdateInput,Order,OrderCancelInput,OrderType,PaymentMethod,Product,ProductCreateInput,ProductUpdateInput,RestaurantTable,Settings,SettingsUpdate,StockAdjustmentInput,StockMovement,StockPurchaseInput,StockReconciliationIn} from "../types";

export const API_URL=import.meta.env.VITE_API_URL||"http://127.0.0.1:8000";

/**
 * APIError extends Error to preserve structured error details from the backend.
 * When the server returns detail as an object (e.g., {message: "...", inactive_table_id: 7}),
 * the message property contains the user-facing string, and the full object is available
 * via the detail property. This preserves backward compatibility: existing code checking
 * e instanceof Error and reading e.message continues to work unchanged.
 */
export class APIError extends Error {
 detail: any;
 constructor(message: string, detail?: any) {
  super(message);
  this.detail = detail;
  this.name = "APIError";
  Object.setPrototypeOf(this, APIError.prototype);
 }
}

async function request<T>(path:string,options?:RequestInit):Promise<T>{
 const r=await fetch(`${API_URL}${path}`,{headers:{"Content-Type":"application/json",...(options?.headers||{})},...options});
 if(!r.ok){
  let message="Request failed.";
  let detail:any=undefined;
  try{
   const b=await r.json();
   detail=b.detail;
   if(typeof detail==="string"){
    message=detail;
   }else if(detail&&typeof detail==="object"&&detail.message){
    message=detail.message;
   }
  }catch{}
  throw new APIError(message,detail);
 }
 return r.json();
}

async function uploadFile<T>(path:string,file:File):Promise<T>{
 const fd=new FormData();fd.append("file",file);
 const r=await fetch(`${API_URL}${path}`,{method:"POST",body:fd});
 if(!r.ok){
  let message="Upload failed.";
  let detail:any=undefined;
  try{
   const b=await r.json();
   detail=b.detail;
   if(typeof detail==="string"){
    message=detail;
   }else if(detail&&typeof detail==="object"&&detail.message){
    message=detail.message;
   }
  }catch{}
  throw new APIError(message,detail);
 }
 return r.json();
}
export const api={
 getCatalogCategories:()=>request<Category[]>("/api/catalog/categories"),
 getCategories:()=>request<Category[]>("/api/categories"),
 createCategory:(name:string)=>request<Category>("/api/categories",{method:"POST",body:JSON.stringify({name})}),
 updateCategory:(id:number,name:string)=>request<Category>(`/api/categories/${id}`,{method:"PUT",body:JSON.stringify({name})}),
 activateCategory:(id:number)=>request<Category>(`/api/categories/${id}/activate`,{method:"PATCH",body:JSON.stringify({})}),
 deactivateCategory:(id:number)=>request<Category>(`/api/categories/${id}/deactivate`,{method:"PATCH",body:JSON.stringify({})}),
 getCatalogProducts:()=>request<Product[]>("/api/catalog/products"),
 getProducts:(search?:string,includeDisabled?:boolean)=>{
  const q=new URLSearchParams();
  if(search&&search.trim())q.set("search",search.trim());
  if(includeDisabled)q.set("include_disabled","true");
  const qs=q.toString();
  return request<Product[]>(`/api/products${qs?`?${qs}`:""}`);
 },
 getTables:(includeInactive?:boolean)=>{
  const q=new URLSearchParams();
  if(includeInactive)q.set("include_inactive","true");
  const qs=q.toString();
  return request<RestaurantTable[]>(`/api/tables${qs?`?${qs}`:""}`);
 },
 createTable:(name:string)=>request<RestaurantTable>("/api/tables",{method:"POST",body:JSON.stringify({name})}),
 renameTable:(id:number,name:string)=>request<RestaurantTable>(`/api/tables/${id}`,{method:"PUT",body:JSON.stringify({name})}),
 deactivateTable:(id:number)=>request<RestaurantTable>(`/api/tables/${id}/deactivate`,{method:"PATCH",body:JSON.stringify({})}),
 activateTable:(id:number)=>request<RestaurantTable>(`/api/tables/${id}/activate`,{method:"PATCH",body:JSON.stringify({})}),
 getOrders:(params?:{search?:string;status?:string})=>{
  const q=new URLSearchParams();
  if(params?.search&&params.search.trim())q.set("search",params.search.trim());
  if(params?.status)q.set("status",params.status);
  const qs=q.toString();
  return request<Order[]>(`/api/orders${qs?`?${qs}`:""}`);
 },
 createOrder:(p:{order_type:OrderType;table_id:number|null;customer_id?:number|null;delivery_address?:string|null;delivery_charge?:number|null;items:{product_id:number;quantity:number}[];discount:number;payment_method:PaymentMethod;amount_received:number})=>request<Order>("/api/orders",{method:"POST",body:JSON.stringify(p)}),
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
 reconcileStock:(payload:StockReconciliationIn)=>request<StockMovement[]>("/api/inventory/reconcile",{method:"POST",body:JSON.stringify(payload)}),
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
 enableProduct:(id:number)=>request<Product>(`/api/products/${id}/enable`,{method:"PATCH",body:JSON.stringify({})}),
 uploadProductImage:(id:number,file:File)=>uploadFile<Product>(`/api/products/${id}/image`,file),
 deleteProductImage:(id:number)=>request<Product>(`/api/products/${id}/image`,{method:"DELETE",body:JSON.stringify({})}),
 // Customers (Phase 3.2–3.5)
 searchCustomers:(query?:string,includeInactive:boolean=false)=>{
  const q=new URLSearchParams();
  if(query&&query.trim())q.set("search",query.trim());
  if(includeInactive)q.set("include_inactive","true");
  const qs=q.toString();
  return request<CustomerSearchResult[]>(`/api/customers${qs?`?${qs}`:""}`);
 },
 getCustomer:(id:number)=>request<Customer>(`/api/customers/${id}`),
 createCustomer:(p:CustomerCreateInput)=>request<Customer>("/api/customers",{method:"POST",body:JSON.stringify(p)}),
 updateCustomer:(id:number,p:CustomerUpdateInput)=>request<Customer>(`/api/customers/${id}`,{method:"PUT",body:JSON.stringify(p)}),
 deactivateCustomer:(id:number)=>request<Customer>(`/api/customers/${id}/deactivate`,{method:"PATCH",body:JSON.stringify({})}),
 activateCustomer:(id:number)=>request<Customer>(`/api/customers/${id}/activate`,{method:"PATCH",body:JSON.stringify({})}),
 // DINE_IN running tab (Phase 4.D2)
 openOrder:(p:{table_id:number;customer_id?:number|null})=>request<Order>("/api/orders/open",{method:"POST",body:JSON.stringify(p)}),
 addItemsToOrder:(id:number,p:{items:{product_id:number;quantity:number}[]})=>request<Order>(`/api/orders/${id}/items`,{method:"POST",body:JSON.stringify(p)}),
 updatePendingItem:(id:number,item_id:number,p:{quantity:number;reason?:string})=>request<Order>(`/api/orders/${id}/items/${item_id}`,{method:"PATCH",body:JSON.stringify(p)}),
 sendBatchToKitchen:(id:number)=>request<Order>(`/api/orders/${id}/send`,{method:"POST",body:JSON.stringify({})}),
 payOrderDineIn:(id:number,p:{payment_method:PaymentMethod;discount:number;amount_received:number})=>request<Order>(`/api/orders/${id}/pay`,{method:"POST",body:JSON.stringify(p)})
};
