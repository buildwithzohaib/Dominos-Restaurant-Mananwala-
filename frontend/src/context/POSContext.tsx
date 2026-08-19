import {createContext,useCallback,useContext,useMemo,useReducer,type ReactNode} from "react";
import type {CartItem,Customer,OrderType,PaymentMethod,Product,RestaurantTable} from "../types";
import { SettingsContext } from "./SettingsContext";
interface State{cart:CartItem[];orderType:OrderType;selectedTable:RestaurantTable|null;discount:number;paymentMethod:PaymentMethod;selectedCustomer:Customer|null;deliveryAddress:string;deliveryChargeText:string;serverId?:number}
type Action={type:"ADD";product:Product}|{type:"SET_QTY";productId:number;quantity:number}|{type:"REMOVE";productId:number}|{type:"CLEAR"}|{type:"ORDER_TYPE";value:OrderType}|{type:"TABLE";value:RestaurantTable|null}|{type:"DISCOUNT";value:number}|{type:"PAYMENT";value:PaymentMethod}|{type:"SYNC_PRODUCTS";products:Product[]}|{type:"CUSTOMER";value:Customer|null}|{type:"DELIVERY_ADDRESS";value:string}|{type:"DELIVERY_CHARGE";value:string};
const initialState:State={cart:[],orderType:"TAKEAWAY",selectedTable:null,discount:0,paymentMethod:"CASH",selectedCustomer:null,deliveryAddress:"",deliveryChargeText:""};
function reducer(s:State,a:Action):State{
 switch(a.type){
 // Soft, UI-side stock cap — mirrors the backend's authoritative check (order_service)
 // so a customer can't queue up more than is on hand. The backend still re-validates
 // at order time, since this cart snapshot's stock can go stale between fetches.
 case"ADD":{const e=s.cart.find(i=>i.product.id===a.product.id);if(e)return e.quantity>=a.product.stock?s:{...s,cart:s.cart.map(i=>i.product.id===a.product.id?{...i,quantity:i.quantity+1}:i)};return a.product.stock<=0?s:{...s,cart:[...s.cart,{product:a.product,quantity:1}]};}
 case"SET_QTY":return{...s,cart:a.quantity<=0?s.cart.filter(i=>i.product.id!==a.productId):s.cart.map(i=>i.product.id===a.productId?{...i,quantity:Math.min(a.quantity,i.product.stock)}:i)};
 case"REMOVE":return{...s,cart:s.cart.filter(i=>i.product.id!==a.productId)};
 case"CLEAR":return{...initialState,orderType:s.orderType,selectedTable:s.orderType==="DINE_IN"?s.selectedTable:null};
 case"ORDER_TYPE":{const newOrderType=a.value;const newState={...s,orderType:newOrderType,selectedTable:newOrderType==="DINE_IN"?s.selectedTable:null};if(newOrderType!=="DELIVERY"){newState.deliveryChargeText=""}return newState;};
 case"CUSTOMER":return{...s,selectedCustomer:a.value};
 case"DELIVERY_ADDRESS":return{...s,deliveryAddress:a.value};
 case"DELIVERY_CHARGE":return{...s,deliveryChargeText:a.value};
 case"TABLE":return{...s,selectedTable:a.value};
 case"DISCOUNT":return{...s,discount:Math.max(0,a.value)};
 case"PAYMENT":return{...s,paymentMethod:a.value};
 // Phase 6: a cart line built from an earlier product snapshot can go stale if
 // another sale/adjustment lands while it's sitting in this cart. Whenever fresh
 // product data arrives (after any order, or an inventory edit), re-point each
 // cart line at the latest product and clamp its quantity to the current stock —
 // dropping the line entirely if it's now out of stock, so a product that just
 // sold out elsewhere can't still be checked out from a stale cart.
 case"SYNC_PRODUCTS":{const byId=new Map(a.products.map(p=>[p.id,p]));return{...s,cart:s.cart.map(i=>{const fresh=byId.get(i.product.id);return fresh?{product:fresh,quantity:Math.min(i.quantity,fresh.stock)}:i;}).filter(i=>i.quantity>0)};}
 }
}
interface POSContextValue {
  state: State;
  subtotal: number;
  discount: number;
  tax: number;
  deliveryCharge: number;
  total: number;
  addProduct: (product: Product) => void;
  setQty: (productId: number, quantity: number) => void;
  removeProduct: (productId: number) => void;
  clear: () => void;
  setOrderType: (value: OrderType) => void;
  setTable: (value: RestaurantTable | null) => void;
  setDiscount: (value: number) => void;
  setPaymentMethod: (value: PaymentMethod) => void;
  syncProducts: (products: Product[]) => void;
  setCustomer: (value: Customer | null) => void;
  setDeliveryAddress: (value: string) => void;
  setDeliveryCharge: (value: string) => void;
}

const C = createContext<POSContextValue | null>(null);
export function POSProvider({children}:{children:ReactNode}){
 const settingsContext=useContext(SettingsContext);
 const settings=settingsContext?.settings;
 const[state,dispatch]=useReducer(reducer,initialState);
 const subtotal=useMemo(()=>state.cart.reduce((x,i)=>x+i.product.price*i.quantity,0),[state.cart]);
 const discountAmount=Math.min(state.discount,subtotal);
 const taxable=subtotal-discountAmount;
 const taxRate=settings?.tax_enabled?(settings?.tax_rate??0):0;
 const tax=Math.floor((taxable*taxRate+5000)/10000);
 const deliveryChargeAmount=state.orderType==="DELIVERY"?Math.max(0,Math.floor(parseFloat(state.deliveryChargeText)||0)*100):0;
 const total=taxable+tax+deliveryChargeAmount;
 const discount=discountAmount;
 const value={state,subtotal,discount,tax,deliveryCharge:deliveryChargeAmount,total,
 addProduct:useCallback((product:Product)=>dispatch({type:"ADD",product}),[]),
 setQty:useCallback((productId:number,quantity:number)=>dispatch({type:"SET_QTY",productId,quantity}),[]),
 removeProduct:useCallback((productId:number)=>dispatch({type:"REMOVE",productId}),[]),
 clear:useCallback(()=>dispatch({type:"CLEAR"}),[]),
 setOrderType:useCallback((value:OrderType)=>{if(value==="DELIVERY"&&state.orderType!=="DELIVERY"){const defaultCharge=(settings?.delivery_charge??0)/100;dispatch({type:"DELIVERY_CHARGE",value:String(defaultCharge)});}dispatch({type:"ORDER_TYPE",value});},[state.orderType,settings?.delivery_charge]),
 setTable:useCallback((value:RestaurantTable|null)=>dispatch({type:"TABLE",value}),[]),
 setDiscount:useCallback((value:number)=>dispatch({type:"DISCOUNT",value}),[]),
 setPaymentMethod:useCallback((value:PaymentMethod)=>dispatch({type:"PAYMENT",value}),[]),
 syncProducts:useCallback((products:Product[])=>dispatch({type:"SYNC_PRODUCTS",products}),[]),
 setCustomer:useCallback((value:Customer|null)=>dispatch({type:"CUSTOMER",value}),[]),
 setDeliveryAddress:useCallback((value:string)=>dispatch({type:"DELIVERY_ADDRESS",value}),[]),
 setDeliveryCharge:useCallback((value:string)=>dispatch({type:"DELIVERY_CHARGE",value}),[])};
 return <C.Provider value={value}>{children}</C.Provider>;
}
export function usePOS() {
  const v = useContext(C);
  if (!v) throw new Error("usePOS must be inside POSProvider");
  return v;
}
