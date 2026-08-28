from collections import defaultdict
from datetime import datetime
import logging

from fastapi import HTTPException
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.models import Order, OrderItem, Product, RestaurantTable, StockMovement, Customer, Settings, ProductSize, DealComponent, OrderItemComponent
from app.schemas.schemas import AddItemsIn, OrderCancelIn, OrderCreate, OpenOrderCreate, PayOrderIn, UpdatePendingItemIn

logger = logging.getLogger(__name__)

CANCEL_REASON_LABELS = {
    "CUSTOMER_CHANGED_ORDER": "Customer changed order",
    "WRONG_ORDER": "Wrong order",
    "PAYMENT_ISSUE": "Payment issue",
    "DUPLICATE_ORDER": "Duplicate order",
    "OTHER": "Other",
}


def _validate_and_resolve_item_price(db: Session, product: Product, size_id: int | None) -> tuple[int, str | None]:
    """
    Validate size_id for a product and return the price and size_name.

    If product has sizes, size_id must be provided and must exist.
    If product has no sizes, size_id must be None.

    Returns: (price_in_paisa, size_name_or_none)
    Raises: HTTPException for validation errors
    """
    has_sizes = product.sizes and len(product.sizes) > 0

    if has_sizes:
        if size_id is None:
            raise HTTPException(400, f'"{product.name_display}" requires a size selection.')
        size = db.query(ProductSize).filter(
            ProductSize.id == size_id,
            ProductSize.product_id == product.id
        ).first()
        if not size:
            raise HTTPException(400, f'Selected size does not exist or does not belong to "{product.name_display}".')
        return size.price, size.name
    else:
        if size_id is not None:
            raise HTTPException(400, f'"{product.name_display}" does not have sizes.')
        return product.price, None


def _validate_deal_components(db: Session, deal: Product, line_quantity: int) -> list[tuple[DealComponent, int]]:
    """
    Validate that a deal and all its components exist and have sufficient stock.

    Args:
        db: database session
        deal: Product with product_type='DEAL'
        line_quantity: quantity of this deal being ordered (e.g., 3 deals)

    Returns:
        List of (DealComponent, available_qty) tuples

    Raises:
        HTTPException if any component is missing or out of stock
    """
    if deal.product_type != "DEAL":
        raise HTTPException(400, f'"{deal.name_display}" is not a deal.')

    components = db.query(DealComponent).filter(DealComponent.product_id == deal.id).all()
    if not components:
        raise HTTPException(400, f'Deal "{deal.name_display}" has no components.')

    result = []
    for component in components:
        comp_product = db.get(Product, component.component_product_id)
        if not comp_product:
            raise HTTPException(400, f'Component product {component.component_product_id} not found.')

        needed = component.quantity * line_quantity
        if comp_product.stock < needed:
            raise HTTPException(
                400,
                f'Only {comp_product.stock} of "{comp_product.name_display}" available '
                f'(need {needed} for this deal).'
            )
        result.append((component, comp_product.stock))

    return result


def _decrement_deal_components(db: Session, deal: Product, components_data: list[tuple[DealComponent, int]], line_quantity: int, order_number: str, product_map: dict[int, int] | None = None) -> list[OrderItemComponent]:
    """
    Atomically decrement stock for all deal components and create StockMovements.

    If ANY component fails the atomic check, the entire transaction rolls back
    and an HTTPException is raised. Otherwise, returns a list of OrderItemComponent
    snapshots ready to be added to the order item.

    Args:
        db: database session
        deal: Product with product_type='DEAL'
        components_data: list of (DealComponent, original_stock) tuples from validation
        line_quantity: quantity of this deal being ordered
        order_number: the order's order_number for StockMovement reference
        product_map: optional dict mapping original_product_id -> replacement_product_id (for swaps)
                     if present, stock is decremented for the replacement, not the original

    Returns:
        List of OrderItemComponent dicts (not yet persisted) to add to the order

    Raises:
        HTTPException if any component fails the atomic stock check
    """
    item_components = []

    for component, _ in components_data:
        # Determine which product's stock to decrement: original or replacement (if swapped)
        if product_map and component.component_product_id in product_map:
            decrement_product_id = product_map[component.component_product_id]
        else:
            decrement_product_id = component.component_product_id

        decrement_product = db.get(Product, decrement_product_id)
        needed = component.quantity * line_quantity

        # Atomic conditional decrement on the PRODUCT BEING SERVED (replacement if swapped)
        result = db.execute(
            update(Product)
            .where(Product.id == decrement_product_id, Product.stock >= needed)
            .values(stock=Product.stock - needed, updated_at=datetime.utcnow())
        )
        if result.rowcount == 0:
            db.rollback()
            raise HTTPException(
                400,
                f'Only {decrement_product.stock} of "{decrement_product.name_display}" available '
                f'(need {needed} for this deal).'
            )

        # Refresh to get the new stock value
        db.refresh(decrement_product)
        stock_after = decrement_product.stock
        stock_before = stock_after + needed

        # Create StockMovement for the product ACTUALLY SERVED (StockMovement.item_id = replacement if swapped)
        db.add(StockMovement(
            item_type="PRODUCT",
            item_id=decrement_product.id,
            item_name=decrement_product.name_display,
            movement_type="SALE",
            quantity_change=-needed,
            reason="Sale",
            supplier=None,
            purchase_price=None,
            stock_before=stock_before,
            stock_after=stock_after,
            reference=order_number,
        ))

        # Prepare OrderItemComponent snapshot with the ACTUAL PRODUCT SERVED
        size_name = None
        if component.size_id:
            size = db.query(ProductSize).filter(ProductSize.id == component.size_id).first()
            size_name = size.name if size else None

        item_components.append({
            "deal_component_id": component.id,
            "product_id": decrement_product.id,  # REPLACEMENT PRODUCT if swapped, original otherwise
            "product_name": decrement_product.name_display,
            "quantity": component.quantity * line_quantity,
            "size_id": component.size_id,
        })

    return item_components

def create_order(db: Session, payload: OrderCreate, performed_by_user_id: int | None = None) -> Order:
    # Validate table
    if payload.order_type == "DINE_IN" and payload.table_id is None:
        raise HTTPException(400, "A table is required for dine-in orders.")
    if payload.order_type != "DINE_IN" and payload.table_id is not None:
        raise HTTPException(400, "Only dine-in orders can have a table.")
    if payload.table_id is not None:
        table = db.get(RestaurantTable, payload.table_id)
        if not table or not table.active:
            raise HTTPException(400, "Selected table is not available.")

    # Validate customer if provided
    if payload.customer_id is not None:
        customer = db.get(Customer, payload.customer_id)
        if not customer:
            raise HTTPException(404, "Customer not found.")
        if not customer.is_active:
            raise HTTPException(400, f'"{customer.name_display}" is inactive.')

    # Validate sizes and resolve prices for each item; separate regular products from deals
    # item_details tuple: (product_id, quantity, size_id, price, size_name, is_deal, deal_modifications, price_override)
    item_details: list[tuple[int, int, int | None, int, str | None, bool, dict | None, int | None]] = []
    requested: dict[int, int] = defaultdict(int)  # product_id -> total quantity (regular products only)
    deal_requests: list[tuple[Product, int, dict | None]] = []  # (deal Product, quantity, deal_modifications or None)
    products: dict[int, Product] = {}  # product_id -> Product (regular products only)
    deals: dict[int, Product] = {}  # product_id -> Product (deals only)
    subtotal = 0

    for item in payload.items:
        product = db.query(Product).options(joinedload(Product.category), joinedload(Product.sizes), joinedload(Product.components)).filter(Product.id == item.product_id).first()
        if not product:
            raise HTTPException(400, "Product not found.")
        if not product.available:
            raise HTTPException(400, f'"{product.name_display}" is disabled.')
        if not product.category.active:
            raise HTTPException(400, f'"{product.name_display}" is in a disabled category.')

        is_deal = product.product_type == "DEAL"

        if is_deal:
            # Check if this deal has modifications
            if item.deal_modifications:
                # Modified deal: validate and use charged price
                charged_price = item.deal_modifications.price
                standard_price = product.price
                price_override = standard_price if charged_price != standard_price else None

                # Validate each component in deal_modifications
                for comp_mod in item.deal_modifications.components:
                    # If this component is swapped, validate that the original is actually in the deal
                    if comp_mod.product_id_original:
                        orig_comp = next((c for c in product.components if c.component_product_id == comp_mod.product_id_original), None)
                        if not orig_comp:
                            raise HTTPException(400, f'Component {comp_mod.product_id_original} is not part of "{product.name_display}".')

                    # Validate the component being served (replacement product if swapped, original otherwise)
                    comp_product = db.get(Product, comp_mod.product_id)
                    if not comp_product:
                        raise HTTPException(400, f'Component product {comp_mod.product_id} not found.')
                    if comp_product.product_type == "DEAL":
                        raise HTTPException(400, f'Component "{comp_product.name_display}" is a deal. Deals cannot contain other deals.')
                    if not comp_product.available:
                        raise HTTPException(400, f'Component "{comp_product.name_display}" is disabled.')
                    if not comp_product.category.active:
                        raise HTTPException(400, f'Component "{comp_product.name_display}" is in a disabled category.')

                    # Validate size if provided
                    if comp_mod.size_id:
                        size = db.query(ProductSize).filter(
                            ProductSize.id == comp_mod.size_id,
                            ProductSize.product_id == comp_mod.product_id
                        ).first()
                        if not size:
                            raise HTTPException(400, f'Selected size does not exist or does not belong to "{comp_product.name_display}".')

                # Validate that not all components are removed
                active_comps = [c for c in item.deal_modifications.components if not c.was_removed]
                if not active_comps:
                    raise HTTPException(400, "Deal cannot have all components removed.")

                price = charged_price
                size_name = None
                item_details.append((item.product_id, item.quantity, None, price, size_name, True, item.deal_modifications, price_override))
                deal_requests.append((product, item.quantity, item.deal_modifications))
                deals[item.product_id] = product
                subtotal += price * item.quantity
            else:
                # Unmodified deal: existing logic
                price = product.price
                size_name = None
                item_details.append((item.product_id, item.quantity, None, price, size_name, True, None, None))
                deal_requests.append((product, item.quantity, None))
                deals[item.product_id] = product
                subtotal += price * item.quantity
        else:
            # Regular product: validate size and get price
            price, size_name = _validate_and_resolve_item_price(db, product, item.size_id)
            item_details.append((item.product_id, item.quantity, item.size_id, price, size_name, False, None, None))
            requested[item.product_id] += item.quantity
            products[item.product_id] = product
            subtotal += price * item.quantity

    # Stock validation for regular products (deals are validated separately below)
    for product_id, total_quantity in requested.items():
        product = products[product_id]
        if product.stock <= 0:
            raise HTTPException(400, f'"{product.name_display}" is out of stock.')
        if product.stock < total_quantity:
            raise HTTPException(400, f'Only {product.stock} of "{product.name_display}" available.')

    # Stock validation for deals (and fetch component info for later decrement)
    deal_components_data: dict[int, list[tuple[DealComponent, int]]] = {}  # deal_id -> components_data
    deal_modifications_map: dict[int, dict | None] = {}  # deal_id -> deal_modifications or None
    for deal, quantity, deal_mods in deal_requests:
        components_data = _validate_deal_components(db, deal, quantity)
        deal_components_data[deal.id] = components_data
        deal_modifications_map[deal.id] = deal_mods

    # Get tax_rate and delivery_charge from settings (Rule 7: snapshot at order time)
    settings = db.query(Settings).filter(Settings.id == 1).first()
    tax_rate = settings.tax_rate if settings and settings.tax_enabled else 0

    # Delivery charge: use provided value if sent, else fall back to settings default.
    # Only apply if order_type is DELIVERY; otherwise force 0.
    if payload.order_type == "DELIVERY":
        delivery_charge = payload.delivery_charge if payload.delivery_charge is not None else (settings.delivery_charge if settings else 0)
    else:
        delivery_charge = 0

    discount = min(payload.discount, subtotal)
    taxable = subtotal - discount
    # Half-up rounding: (taxable * rate + 5000) // 10000
    # Delivery charge is NOT taxed (per Rule 7: tax applies only to goods/services taxed at POS)
    tax = (taxable * tax_rate + 5000) // 10000
    total = taxable + tax + delivery_charge
    received = payload.amount_received

    if payload.payment_method == "CASH" and received < total:
        raise HTTPException(400, f"Cash received must be at least {total}.")
    change = received - total if payload.payment_method == "CASH" else 0

    # Nothing has been written yet: every validation above (bad product, insufficient
    # cash, closed table) fails before this point, so a failed/rejected order never
    # touches stock.
    #
    # order_number is derived from COUNT(*)+1, which is only a hint of the next
    # number, not a reservation: two concurrent requests can both read the same
    # count before either commits and both try to insert the same order_number.
    # SQLite's unique index then rejects the second INSERT with an IntegrityError
    # instead of silently allowing a duplicate, so this is a retry loop rather
    # than an extra correctness check — if two requests collide, the loser rolls
    # back and re-reads the count (now incremented by the winner's commit).
    order = None
    for _ in range(5):
        next_number = db.query(Order).count() + 1
        candidate = Order(
            order_number=f"ORD-{next_number:05d}",
            order_type=payload.order_type,
            table_id=payload.table_id,
            customer_id=payload.customer_id,  # NULL for walk-ins
            delivery_address=payload.delivery_address,  # NULL for non-delivery; snapshot per Rule 7
            status="PAID",
            subtotal=subtotal,
            discount=discount,
            tax=tax,
            tax_rate=tax_rate,  # snapshot per Rule 7
            delivery_charge=delivery_charge if payload.order_type == "DELIVERY" else None,  # snapshot per Rule 7; NULL for non-delivery
            total=total,
            payment_method=payload.payment_method,
            amount_received=received,
            change_amount=change,
            paid_at=datetime.utcnow(),
            performed_by_user_id=performed_by_user_id,  # Stage 7: user attribution
        )
        db.add(candidate)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        order = candidate
        break
    if order is None:
        raise HTTPException(409, "Could not create the order, please try again.")

    # Atomic, race-safe stock decrement for regular products (existing logic, unchanged)
    # The WHERE clause re-checks stock at write time, so if two orders race for the last unit,
    # only one UPDATE can match `stock >= quantity` — the loser rolls back instead.
    for product_id, quantity in requested.items():
        result = db.execute(
            update(Product)
            .where(Product.id == product_id, Product.stock >= quantity)
            .values(stock=Product.stock - quantity, updated_at=datetime.utcnow())
        )
        if result.rowcount == 0:
            db.rollback()
            product = db.get(Product, product_id)
            name = product.name_display if product else product_id
            available = product.stock if product else 0
            raise HTTPException(400, f'Only {available} of "{name}" available.')

        product = products[product_id]
        db.refresh(product)
        stock_after = product.stock
        stock_before = stock_after + quantity

        db.add(StockMovement(
            item_type="PRODUCT",
            item_id=product.id,
            item_name=product.name_display,
            movement_type="SALE",
            quantity_change=-quantity,
            reason="Sale",
            supplier=None,
            purchase_price=None,
            stock_before=stock_before,
            stock_after=stock_after,
            reference=order.order_number,
        ))

    # Stock decrement for deals: each component is decremented separately (Phase 11)
    # All-or-nothing: if ANY component fails, the entire order is rolled back
    # CRITICAL: Maps key off the ORIGINAL component_product_id, but stock is decremented for the REPLACEMENT product
    deal_item_components: dict[int, list[OrderItemComponent]] = {}  # item_index -> components
    for i, (product_id, quantity, size_id, price, size_name, is_deal, deal_mods, price_override) in enumerate(item_details):
        if is_deal:
            deal = deals[product_id]
            components_data = deal_components_data[deal.id]

            # If deal has modifications, filter and map components
            if deal_mods:
                # Build maps keyed off ORIGINAL component_product_id (use product_id_original if set, else product_id)
                removed_map = {}  # original_product_id -> was_removed
                product_map = {}  # original_product_id -> replacement_product_id (if swapped) or original
                size_map = {}     # original_product_id -> size_id (if changed)

                for comp_mod in deal_mods.components:
                    orig_id = comp_mod.product_id_original or comp_mod.product_id
                    removed_map[orig_id] = comp_mod.was_removed
                    product_map[orig_id] = comp_mod.product_id  # what's actually being served
                    size_map[orig_id] = comp_mod.size_id

                components_to_decrement = []
                for comp, stock in components_data:
                    orig_product_id = comp.component_product_id
                    if orig_product_id not in removed_map or not removed_map[orig_product_id]:
                        components_to_decrement.append((comp, stock))
            else:
                components_to_decrement = components_data
                product_map = {}  # unused when no modifications

            item_components = _decrement_deal_components(db, deal, components_to_decrement, quantity, order.order_number, product_map if deal_mods else None)
            deal_item_components[i] = item_components

    # Create OrderItem rows for each item (including deals)
    for i, (product_id, quantity, size_id, price, size_name, is_deal, deal_mods, price_override) in enumerate(item_details):
        if is_deal:
            deal = deals[product_id]
            order_item = OrderItem(
                order_id=order.id,
                product_id=deal.id,
                product_name=deal.name_display,
                size_name=None,
                quantity=quantity,
                price=price,  # charged price (may differ from standard if modified)
                line_total=price * quantity,
                cost=deal.purchase_price,
                deal_id=deal.id,
                price_override=price_override,  # standard price from DB, only if differs
            )
            db.add(order_item)
            db.flush()  # Get the order_item.id before adding components

            # Create OrderItemComponent rows for each deal component (including removed ones)
            if deal_mods:
                # For modified deals, create components with was_removed flag and modified size_id
                removed_map = {c.product_id: c.was_removed for c in deal_mods.components}
                size_map = {c.product_id: c.size_id for c in deal_mods.components}
                for comp_data in deal_item_components.get(i, []):
                    was_removed = removed_map.get(comp_data["product_id"], False)
                    # Use modified size_id if it was changed, otherwise use original
                    modified_size_id = size_map.get(comp_data["product_id"], comp_data["size_id"])
                    db.add(OrderItemComponent(
                        order_item_id=order_item.id,
                        deal_component_id=comp_data["deal_component_id"],
                        product_id=comp_data["product_id"],
                        product_name=comp_data["product_name"],
                        quantity=comp_data["quantity"],
                        size_id=modified_size_id,
                        was_removed=was_removed,
                    ))
                # Also create OrderItemComponent rows for removed components (these won't have stock decrements)
                for comp_mod in deal_mods.components:
                    if comp_mod.was_removed:
                        # Find the original component definition to get its data
                        orig_comp = next((c for c in deal.components if c.component_product_id == comp_mod.product_id), None)
                        if orig_comp:
                            comp_product = db.get(Product, comp_mod.product_id)
                            db.add(OrderItemComponent(
                                order_item_id=order_item.id,
                                deal_component_id=orig_comp.id,
                                product_id=comp_mod.product_id,
                                product_name=comp_product.name_display if comp_product else "Unknown",
                                quantity=orig_comp.quantity * quantity,
                                size_id=comp_mod.size_id,
                                was_removed=True,
                            ))
            else:
                # For unmodified deals, create components normally
                for comp_data in deal_item_components.get(i, []):
                    db.add(OrderItemComponent(
                        order_item_id=order_item.id,
                        deal_component_id=comp_data["deal_component_id"],
                        product_id=comp_data["product_id"],
                        product_name=comp_data["product_name"],
                        quantity=comp_data["quantity"],
                        size_id=comp_data["size_id"],
                    ))
        else:
            product = products[product_id]
            db.add(OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name_display,
                size_name=size_name,
                quantity=quantity,
                price=price,
                line_total=price * quantity,
                cost=product.purchase_price,
            ))

    db.commit()
    order_result = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order.id).first()

    # Phase 3.5: Update customer address convenience field if DELIVERY order with customer and address
    # This happens AFTER the main commit, in a separate transaction, so order is safe even if it fails
    if (
        payload.order_type == "DELIVERY"
        and payload.customer_id is not None
        and payload.delivery_address
    ):
        try:
            addr_trimmed = payload.delivery_address.strip()
            if addr_trimmed:  # Don't update if whitespace-only
                customer = db.get(Customer, payload.customer_id)
                if customer:
                    customer.address = addr_trimmed
                    db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update customer {payload.customer_id} address: {e}")
            # Order is already saved; don't fail the response over a convenience field

    return order_result


def cancel_order(db: Session, order_id: int, payload: OrderCancelIn, performed_by_user_id: int | None = None) -> Order:
    """Phase 7–8: mark an order CANCELLED with a required reason, then restore its inventory.

    Phase 7: The order row is never deleted — only its status/cancellation fields change —
    and cancellation is a single atomic conditional UPDATE (WHERE status IN ('OPEN', 'PAID')),
    not a read-then-write, so two concurrent cancel requests for the same order can't both
    succeed: only the one that actually flips to CANCELLED wins, the other gets a
    clean 400 instead of double-cancelling.

    Phase 8 (Stage 4 B3 onwards): Inventory restoration (reversing the order's SALE
    StockMovements, identifiable via StockMovement.reference == order.order_number) happens
    in the same transaction as the status change. The original SALE movements remain untouched;
    new CANCELLATION movements are created for the restored quantities. PENDING items (never
    sent to kitchen) have no SALE movements, so they are automatically excluded.
    If the status change fails (order already cancelled or not found), the entire transaction
    is rolled back and no inventory is restored. If inventory restoration fails after the
    status change succeeded, the entire transaction is rolled back, so the order remains
    in its previous state.
    """
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found.")

    # No status branching needed: PENDING items never produced a SALE movement, so an
    # OPEN order's unsent items are excluded automatically. The same stock restoration
    # path works correctly for both OPEN and PAID orders.

    label = CANCEL_REASON_LABELS[payload.reason]
    if payload.reason == "OTHER" and payload.note and payload.note.strip():
        label = f"Other: {payload.note.strip()}"

    result = db.execute(
        update(Order)
        .where(Order.id == order_id, Order.status.in_(["OPEN", "PAID"]))
        .values(status="CANCELLED", cancelled_at=datetime.utcnow(), cancelled_reason=label, cancel_order_performed_by_user_id=performed_by_user_id)
    )
    if result.rowcount == 0:
        db.rollback()
        current = db.get(Order, order_id)
        if current and current.status == "CANCELLED":
            raise HTTPException(400, "This order has already been cancelled.")
        raise HTTPException(400, "Only an open or paid order can be cancelled.")

    # --- Phase 8: Inventory restoration, within the same transaction. ---
    # Find the original SALE movements for this order and restore each product's stock.
    sale_movements = db.query(StockMovement).filter(
        StockMovement.reference == order.order_number,
        StockMovement.movement_type == "SALE"
    ).all()

    for sale_movement in sale_movements:
        # Restore the quantity: undo the negative quantity_change from the SALE.
        restore_quantity = -sale_movement.quantity_change  # e.g., SALE was -2, restore is +2

        # For now, all movements are PRODUCT type. Get the product to update its stock.
        # Stage 6 will handle INGREDIENT type separately.
        if sale_movement.item_type == "PRODUCT":
            product = db.get(Product, sale_movement.item_id)
            # Atomic increment: update Product.stock by restore_quantity.
            db.execute(
                update(Product)
                .where(Product.id == product.id)
                .values(stock=Product.stock + restore_quantity, updated_at=datetime.utcnow())
            )

            # Refresh to get the new current stock value.
            db.refresh(product)
            stock_after = product.stock
            stock_before = stock_after - restore_quantity

            # Create a new CANCELLATION movement, referencing the same order.
            cancellation_movement = StockMovement(
                item_type=sale_movement.item_type,
                item_id=sale_movement.item_id,
                item_name=sale_movement.item_name,
                movement_type="CANCELLATION",
                quantity_change=restore_quantity,
                reason="Order cancellation",
                supplier=None,
                purchase_price=None,
                stock_before=stock_before,
                stock_after=stock_after,
                reference=order.order_number,
            )
            db.add(cancellation_movement)

    db.commit()
    return db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id).first()


def create_open_order(db: Session, payload: OpenOrderCreate) -> Order:
    """
    Create an OPEN dine-in order for a table (running tab).

    Order starts with status="OPEN", no items, no payment, no stock deduction.
    Items are added later via add_items_to_order (not yet implemented).
    Payment is taken later via pay_order (not yet implemented).

    Args:
        db: database session
        payload: OpenOrderCreate with table_id and optional customer_id

    Returns:
        Order with status="OPEN", empty items, all monetary fields = 0

    Raises:
        HTTPException for validation errors
    """
    # Validate table
    table = db.get(RestaurantTable, payload.table_id)
    if not table or not table.active:
        raise HTTPException(400, "Selected table is not available.")

    # Validate customer if provided
    if payload.customer_id is not None:
        customer = db.get(Customer, payload.customer_id)
        if not customer:
            raise HTTPException(404, "Customer not found.")
        if not customer.is_active:
            raise HTTPException(400, f'"{customer.name_display}" is inactive.')

    # Explicit check: no other OPEN order on this table
    existing_open = db.query(Order).filter(
        Order.table_id == payload.table_id,
        Order.status == "OPEN"
    ).first()
    if existing_open:
        raise HTTPException(400, f'"{table.name}" already has an open order.')

    # Get tax_rate from settings (snapshot per Rule 7)
    settings = db.query(Settings).filter(Settings.id == 1).first()
    tax_rate = settings.tax_rate if settings and settings.tax_enabled else 0

    # Insert order with retry loop for order_number uniqueness
    order = None
    for _ in range(5):
        next_number = db.query(Order).count() + 1
        candidate = Order(
            order_number=f"ORD-{next_number:05d}",
            order_type="DINE_IN",
            table_id=payload.table_id,
            customer_id=payload.customer_id,
            status="OPEN",
            payment_method=None,  # NULL, never ""
            subtotal=0,
            discount=0,
            tax=0,
            total=0,
            amount_received=0,
            change_amount=0,
            tax_rate=tax_rate,
            delivery_charge=None,
            delivery_address=None,
        )
        db.add(candidate)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            # This branch handles the race condition where another concurrent request
            # creates an OPEN order on the same table between our explicit pre-check
            # (above) and our INSERT. It is unreachable in unit tests (the explicit
            # pre-check always fires first) but necessary for production concurrency.
            existing_open = db.query(Order).filter(
                Order.table_id == payload.table_id,
                Order.status == "OPEN"
            ).first()
            if existing_open:
                raise HTTPException(400, f'"{table.name}" already has an open order.')
            continue
        order = candidate
        break

    if order is None:
        raise HTTPException(409, "Could not create the order, please try again.")

    db.commit()
    order_result = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order.id).first()
    return order_result


def add_items_to_order(db: Session, order_id: int, payload: AddItemsIn) -> Order:
    """
    Add items to an existing OPEN dine-in order (running tab).

    Items are inserted with batch_id=None (PENDING), sent_at=None. No stock is
    deducted (per Rule 8: stock moves only on Send to Kitchen, per batch in B3).
    Order's money fields (subtotal, tax, total) are recomputed from ALL items
    (existing + new) using the order's snapshotted tax_rate.

    Args:
        db: database session
        order_id: the order to add items to
        payload: AddItemsIn with items list

    Returns:
        Updated Order with all items (existing + new), with recomputed totals

    Raises:
        HTTPException for validation errors
    """
    # Load order and validate it exists and is OPEN
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found.")
    if order.status != "OPEN":
        raise HTTPException(400, "Only an open order can be modified.")

    # Validate sizes and resolve prices for each item; separate regular products from deals
    item_details: list[tuple[int, int, int | None, int, str | None, bool, dict | None, int | None]] = []
    requested: dict[int, int] = defaultdict(int)  # product_id -> total quantity (regular products only)
    deal_requests: list[tuple[Product, int, dict | None]] = []  # (deal Product, quantity, deal_modifications or None)
    products: dict[int, Product] = {}  # product_id -> Product (regular products only)
    deals: dict[int, Product] = {}  # product_id -> Product (deals only)

    for item in payload.items:
        product = db.query(Product).options(joinedload(Product.category), joinedload(Product.sizes), joinedload(Product.components)).filter(Product.id == item.product_id).first()
        if not product:
            raise HTTPException(400, "Product not found.")
        if not product.available:
            raise HTTPException(400, f'"{product.name_display}" is disabled.')
        if not product.category.active:
            raise HTTPException(400, f'"{product.name_display}" is in a disabled category.')

        is_deal = product.product_type == "DEAL"

        if is_deal:
            # Check if this deal has modifications
            if item.deal_modifications:
                # Modified deal: validate and use charged price
                charged_price = item.deal_modifications.price
                standard_price = product.price
                price_override = standard_price if charged_price != standard_price else None

                # Validate each component in deal_modifications
                for comp_mod in item.deal_modifications.components:
                    # If this component is swapped, validate that the original is actually in the deal
                    if comp_mod.product_id_original:
                        orig_comp = next((c for c in product.components if c.component_product_id == comp_mod.product_id_original), None)
                        if not orig_comp:
                            raise HTTPException(400, f'Component {comp_mod.product_id_original} is not part of "{product.name_display}".')

                    # Validate the component being served (replacement product if swapped, original otherwise)
                    comp_product = db.get(Product, comp_mod.product_id)
                    if not comp_product:
                        raise HTTPException(400, f'Component product {comp_mod.product_id} not found.')
                    if comp_product.product_type == "DEAL":
                        raise HTTPException(400, f'Component "{comp_product.name_display}" is a deal. Deals cannot contain other deals.')
                    if not comp_product.available:
                        raise HTTPException(400, f'Component "{comp_product.name_display}" is disabled.')
                    if not comp_product.category.active:
                        raise HTTPException(400, f'Component "{comp_product.name_display}" is in a disabled category.')

                    # Validate size if provided
                    if comp_mod.size_id:
                        size = db.query(ProductSize).filter(
                            ProductSize.id == comp_mod.size_id,
                            ProductSize.product_id == comp_mod.product_id
                        ).first()
                        if not size:
                            raise HTTPException(400, f'Selected size does not exist or does not belong to "{comp_product.name_display}".')

                # Validate that not all components are removed
                active_comps = [c for c in item.deal_modifications.components if not c.was_removed]
                if not active_comps:
                    raise HTTPException(400, "Deal cannot have all components removed.")

                price = charged_price
                size_name = None
                item_details.append((item.product_id, item.quantity, None, price, size_name, True, item.deal_modifications, price_override))
                deal_requests.append((product, item.quantity, item.deal_modifications))
                deals[item.product_id] = product
            else:
                # Unmodified deal: existing logic
                price = product.price
                size_name = None
                item_details.append((item.product_id, item.quantity, None, price, size_name, True, None, None))
                deal_requests.append((product, item.quantity, None))
                deals[item.product_id] = product
        else:
            # Regular product: validate size and get price
            price, size_name = _validate_and_resolve_item_price(db, product, item.size_id)
            item_details.append((item.product_id, item.quantity, item.size_id, price, size_name, False, None, None))
            requested[item.product_id] += item.quantity
            products[item.product_id] = product

    # Validate stock for regular products, accounting for existing PENDING items
    for product_id, quantity in requested.items():
        product = products[product_id]
        if product.stock <= 0:
            raise HTTPException(400, f'"{product.name_display}" is out of stock.')

        # Stock check must account for PENDING items already on this order
        pending_total = db.query(
            func.coalesce(func.sum(OrderItem.quantity), 0)
        ).filter(
            OrderItem.order_id == order_id,
            OrderItem.product_id == product_id,
            OrderItem.batch_id.is_(None),
        ).scalar()
        total_needed = pending_total + quantity

        if product.stock < total_needed:
            available = product.stock - pending_total
            raise HTTPException(400, f'Only {available} of "{product.name_display}" available.')

    # Validate deals (no stock check for PENDING items; stock is checked at send time)
    # But we DO validate that deal and components exist and have definitions
    deal_components_data: dict[int, list[tuple[DealComponent, int]]] = {}
    deal_modifications_map: dict[int, dict | None] = {}
    for deal, quantity, deal_mods in deal_requests:
        components_data = _validate_deal_components(db, deal, quantity)
        deal_components_data[deal.id] = components_data
        deal_modifications_map[deal.id] = deal_mods

    # Add or merge OrderItem rows for each item (do NOT decrement stock; PENDING items)
    # For regular products: merge key is product + size.
    # For deals: do not merge; each deal is a separate line with its components.
    for i, (product_id, quantity, size_id, price, size_name, is_deal, deal_mods, price_override) in enumerate(item_details):
        if is_deal:
            # Deals are never merged; always create a new line
            deal = deals[product_id]
            order_item = OrderItem(
                order_id=order.id,
                product_id=deal.id,
                product_name=deal.name_display,
                size_name=None,
                quantity=quantity,
                price=price,  # charged price (may differ from standard if modified)
                line_total=price * quantity,
                cost=deal.purchase_price,
                batch_id=None,
                sent_at=None,
                deal_id=deal.id,
                price_override=price_override,  # standard price from DB, only if differs
            )
            db.add(order_item)
            db.flush()  # Get the order_item.id before adding components

            # Create OrderItemComponent rows for each deal component (including removed ones)
            if deal_mods:
                # For modified deals: key maps off ORIGINAL component_product_id
                # removed_map, size_map, product_map all use original_id as key
                removed_map = {}  # original_product_id -> was_removed
                product_map = {}  # original_product_id -> replacement_product_id (if swapped) or original
                size_map = {}     # original_product_id -> size_id

                for comp_mod in deal_mods.components:
                    orig_id = comp_mod.product_id_original or comp_mod.product_id
                    removed_map[orig_id] = comp_mod.was_removed
                    product_map[orig_id] = comp_mod.product_id  # what's actually being served
                    size_map[orig_id] = comp_mod.size_id

                for comp_data in deal_components_data[deal.id]:
                    orig_product_id = comp_data[0].component_product_id
                    # Calculate component quantity for THIS deal line (component qty × line qty)
                    component_qty = comp_data[0].quantity * quantity
                    was_removed = removed_map.get(orig_product_id, False)
                    # Use modified size_id if it was changed, otherwise use original
                    modified_size_id = size_map.get(orig_product_id, comp_data[0].size_id)
                    # Use REPLACEMENT product_id if swapped, original otherwise (deal_component_id always points to original)
                    served_product_id = product_map.get(orig_product_id, orig_product_id)
                    served_product = db.get(Product, served_product_id)

                    db.add(OrderItemComponent(
                        order_item_id=order_item.id,
                        deal_component_id=comp_data[0].id,
                        product_id=served_product_id,  # REPLACEMENT if swapped, original otherwise
                        product_name=served_product.name_display if served_product else "Unknown",
                        quantity=component_qty,
                        size_id=modified_size_id,
                        was_removed=was_removed,
                    ))
                # Also create OrderItemComponent rows for removed components
                for comp_mod in deal_mods.components:
                    if comp_mod.was_removed:
                        # For removed components, comp_mod.product_id is what the original component was
                        # Find the original deal component definition
                        orig_id = comp_mod.product_id_original or comp_mod.product_id
                        orig_comp = next((c for c in deal.components if c.component_product_id == orig_id), None)
                        if orig_comp:
                            # Use what's being served (replacement if swapped, original if not)
                            served_product_id = comp_mod.product_id
                            comp_product = db.get(Product, served_product_id)
                            db.add(OrderItemComponent(
                                order_item_id=order_item.id,
                                deal_component_id=orig_comp.id,
                                product_id=served_product_id,  # REPLACEMENT if swapped, original if not
                                product_name=comp_product.name_display if comp_product else "Unknown",
                                quantity=orig_comp.quantity * quantity,
                                size_id=comp_mod.size_id,
                                was_removed=True,
                            ))
            else:
                # For unmodified deals, create components normally
                for comp_data in deal_components_data[deal.id]:
                    # Calculate component quantity for THIS deal line (component qty × line qty)
                    component_qty = comp_data[0].quantity * quantity

                    db.add(OrderItemComponent(
                        order_item_id=order_item.id,
                        deal_component_id=comp_data[0].id,
                        product_id=comp_data[0].component_product_id,
                        product_name=db.get(Product, comp_data[0].component_product_id).name_display,
                        quantity=component_qty,
                        size_id=comp_data[0].size_id,
                    ))
        else:
            # Regular product: merge if PENDING line with same product+size exists
            product = products[product_id]

            # Look for an existing PENDING line (batch_id IS NULL) for this product+size combo
            existing_pending = db.query(OrderItem).filter(
                OrderItem.order_id == order.id,
                OrderItem.product_id == product_id,
                OrderItem.size_name == size_name,
                OrderItem.batch_id.is_(None),
                OrderItem.deal_id.is_(None),  # Not a deal
            ).first()

            if existing_pending:
                # Merge: increase quantity and recompute line_total using the line's original price
                existing_pending.quantity += quantity
                existing_pending.line_total = existing_pending.price * existing_pending.quantity
            else:
                # No PENDING line exists for this product+size; create a new one
                db.add(OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    product_name=product.name_display,
                    size_name=size_name,
                    quantity=quantity,
                    price=price,
                    line_total=price * quantity,
                    cost=product.purchase_price,
                    batch_id=None,
                    sent_at=None,
                ))

    # Recompute order's money fields from ALL items (existing + new)
    db.flush()  # Ensure new items are in the session before we query
    all_items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
    subtotal = sum(item.line_total for item in all_items)
    taxable = subtotal - order.discount
    tax = (taxable * order.tax_rate + 5000) // 10000
    total = taxable + tax

    # Update order's money fields
    order.subtotal = subtotal
    order.tax = tax
    order.total = total
    # Leave discount, amount_received, change_amount, payment_method, delivery_charge unchanged

    db.commit()
    order_result = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order.id).first()
    return order_result


def update_pending_item(db: Session, order_id: int, item_id: int, payload: UpdatePendingItemIn) -> Order:
    """
    Update the quantity of a PENDING item in an OPEN order, or remove a SENT item.

    Phase 4 B6 (PENDING items):
    Items can only be updated while they are PENDING (batch_id IS NULL). When quantity is
    set to 0, the item is deleted from the order entirely. The waiter can always reduce or
    remove a line, even if the product is later disabled — only increases are blocked by
    product availability.

    Phase 4 B8 (SENT items):
    SENT items (batch_id NOT NULL) can ONLY be removed (quantity=0). Removal reverses the
    SALE StockMovement by restoring stock and creating a RETURN movement. Optional reason
    applies to SENT-item removals only. Hard-deletes the OrderItem and recomputes totals.

    Order's money fields (subtotal, tax, total) are recomputed from ALL remaining items
    using the order's snapshotted tax_rate.

    Args:
        db: database session
        order_id: the order containing the item
        item_id: the specific item to update or remove
        payload: UpdatePendingItemIn with quantity (0 = delete) and optional reason (B8 only)

    Returns:
        Updated Order with recomputed totals

    Raises:
        HTTPException for validation errors
    """
    # Load order and validate it exists and is OPEN
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found.")
    if order.status != "OPEN":
        raise HTTPException(400, "Only an open order can be modified.")

    # Load item and validate it exists and belongs to this order
    item = db.get(OrderItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found.")
    if item.order_id != order_id:
        raise HTTPException(404, "Item not found.")

    # --- SENT item removal (B8): quantity must be 0, stock reversal required ---
    if item.batch_id is not None:
        if payload.quantity != 0:
            raise HTTPException(400, "Cannot modify an item that has been sent to the kitchen.")

        # Reverse stock: atomic update + refresh (mirror cancel_order pattern)
        product = db.get(Product, item.product_id)
        if not product:
            raise HTTPException(400, "Product not found.")

        result = db.execute(
            update(Product)
            .where(Product.id == product.id)
            .values(stock=Product.stock + item.quantity, updated_at=datetime.utcnow())
        )
        db.refresh(product)
        stock_after = product.stock
        stock_before = stock_after - item.quantity

        # Create RETURN movement for this item
        return_reason = payload.reason or "Item removed"
        return_movement = StockMovement(
            item_type="PRODUCT",
            item_id=item.product_id,
            item_name=item.product_name,  # snapshot from OrderItem (Rule 7)
            movement_type="RETURN",
            quantity_change=item.quantity,  # positive, mirrors SALE's negative
            reason=return_reason,
            supplier=None,
            purchase_price=None,
            stock_before=stock_before,
            stock_after=stock_after,
            reference=order.order_number,
        )
        db.add(return_movement)

        # Hard-delete the OrderItem
        db.delete(item)
        db.flush()

        # Recompute totals from remaining items
        all_items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
        subtotal = sum(item_obj.line_total for item_obj in all_items)
        taxable = subtotal - order.discount
        tax = (taxable * order.tax_rate + 5000) // 10000
        total = taxable + tax

        order.subtotal = subtotal
        order.tax = tax
        order.total = total
        db.commit()
        order_result = db.query(Order).options(joinedload(Order.items), joinedload(Order.table)).filter(Order.id == order.id).first()
        return order_result

    # --- PENDING item operations (B6): quantity=0 deletes, else updates ---
    if payload.quantity == 0:
        db.delete(item)
        db.flush()
        # Recompute totals from remaining items
        all_items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
        subtotal = sum(item_obj.line_total for item_obj in all_items)
        taxable = subtotal - order.discount
        tax = (taxable * order.tax_rate + 5000) // 10000
        total = taxable + tax

        order.subtotal = subtotal
        order.tax = tax
        order.total = total
        db.commit()
        order_result = db.query(Order).options(joinedload(Order.items), joinedload(Order.table)).filter(Order.id == order.id).first()
        return order_result

    # For increases, get the product and validate stock availability
    quantity_delta = payload.quantity - item.quantity
    if quantity_delta > 0:
        product = db.query(Product).options(joinedload(Product.category)).filter(Product.id == item.product_id).first()
        if not product:
            raise HTTPException(400, "Product not found.")
        if not product.available:
            raise HTTPException(400, f'"{product.name_display}" is disabled.')
        if not product.category.active:
            raise HTTPException(400, f'"{product.name_display}" is in a disabled category.')

        # Sum quantities of OTHER PENDING items for this product (excluding the current item)
        other_pending = db.query(
            func.coalesce(func.sum(OrderItem.quantity), 0)
        ).filter(
            OrderItem.order_id == order_id,
            OrderItem.product_id == item.product_id,
            OrderItem.batch_id.is_(None),
            OrderItem.id != item_id,
        ).scalar()
        total_needed = other_pending + payload.quantity

        # Stock must be available for the new total
        if product.stock < total_needed:
            available = product.stock - other_pending
            raise HTTPException(400, f'Only {available} of "{product.name_display}" available.')

    # Update item quantity and recompute line_total using the line's original price
    item.quantity = payload.quantity
    item.line_total = item.price * item.quantity

    # Recompute order's money fields from ALL items (existing + updated)
    db.flush()
    all_items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
    subtotal = sum(item_obj.line_total for item_obj in all_items)
    taxable = subtotal - order.discount
    tax = (taxable * order.tax_rate + 5000) // 10000
    total = taxable + tax

    # Update order's money fields
    order.subtotal = subtotal
    order.tax = tax
    order.total = total
    # Leave discount, amount_received, change_amount, payment_method, delivery_charge unchanged

    db.commit()
    order_result = db.query(Order).options(joinedload(Order.items), joinedload(Order.table)).filter(Order.id == order.id).first()
    return order_result


def send_batch_to_kitchen(db: Session, order_id: int) -> Order:
    """
    Send all currently PENDING items on an OPEN order to the kitchen as one batch.

    This is the FIRST and ONLY place stock is decremented for dine-in (Rule 8). Items are stamped
    with a batch_id (1, 2, 3...) and sent_at timestamp. If ANY item cannot be decremented
    (insufficient stock), the ENTIRE transaction is rolled back (all-or-nothing).

    Batch numbering is per-order: order 5 and order 9 each start at batch 1.

    For deals: each component is decremented separately (Phase 11).

    Args:
        db: database session
        order_id: the order to send to kitchen

    Returns:
        Updated Order with PENDING items now stamped and stock decremented

    Raises:
        HTTPException for validation errors
    """
    # Load order and validate
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found.")
    if order.status != "OPEN":
        raise HTTPException(400, "Only an open order can be sent to the kitchen.")

    # Collect PENDING items (batch_id IS NULL)
    pending_items = db.query(OrderItem).filter(
        OrderItem.order_id == order_id,
        OrderItem.batch_id.is_(None),
    ).all()
    if not pending_items:
        raise HTTPException(400, "There are no new items to send.")

    # Determine next batch number for this order
    max_batch = db.query(func.max(OrderItem.batch_id)).filter(
        OrderItem.order_id == order_id
    ).scalar()
    next_batch = (max_batch or 0) + 1

    # Separate regular products from deal items
    regular_items: dict[int, int] = defaultdict(int)  # product_id -> total quantity
    deal_items: list[OrderItem] = []  # OrderItem objects that are deals

    for item in pending_items:
        if item.deal_id is not None:
            deal_items.append(item)
        else:
            regular_items[item.product_id] += item.quantity

    # Decrement regular products (existing logic, unchanged)
    for product_id, quantity in regular_items.items():
        product = db.get(Product, product_id)
        if not product:
            raise HTTPException(400, "Product not found.")

        # Atomic conditional decrement
        result = db.execute(
            update(Product)
            .where(Product.id == product_id, Product.stock >= quantity)
            .values(stock=Product.stock - quantity, updated_at=datetime.utcnow())
        )
        if result.rowcount == 0:
            db.rollback()
            product = db.get(Product, product_id)
            name = product.name_display if product else product_id
            available = product.stock if product else 0
            raise HTTPException(400, f'Only {available} of "{name}" available.')

        # Refresh to get the new stock value and write StockMovement immediately
        db.refresh(product)
        stock_after = product.stock
        stock_before = stock_after + quantity

        db.add(StockMovement(
            item_type="PRODUCT",
            item_id=product.id,
            item_name=product.name_display,
            movement_type="SALE",
            quantity_change=-quantity,
            reason="Sale",
            supplier=None,
            purchase_price=None,
            stock_before=stock_before,
            stock_after=stock_after,
            reference=order.order_number,
        ))

    # Decrement deal components (Phase 11)
    # Each deal's components are decremented with all-or-nothing semantics
    for deal_item in deal_items:
        deal = db.get(Product, deal_item.product_id)
        if not deal:
            raise HTTPException(400, "Deal product not found.")

        # Load this deal's components from OrderItemComponent rows (the snapshot)
        item_components = db.query(OrderItemComponent).filter(
            OrderItemComponent.order_item_id == deal_item.id
        ).all()

        for item_component in item_components:
            comp_product = db.get(Product, item_component.product_id)
            if not comp_product:
                raise HTTPException(400, "Component product not found.")

            needed = item_component.quantity  # Already includes line_quantity × component.quantity

            # Atomic conditional decrement
            result = db.execute(
                update(Product)
                .where(Product.id == item_component.product_id, Product.stock >= needed)
                .values(stock=Product.stock - needed, updated_at=datetime.utcnow())
            )
            if result.rowcount == 0:
                db.rollback()
                raise HTTPException(
                    400,
                    f'Only {comp_product.stock} of "{comp_product.name_display}" available '
                    f'(need {needed} for this deal).'
                )

            # Refresh to get the new stock value
            db.refresh(comp_product)
            stock_after = comp_product.stock
            stock_before = stock_after + needed

            # Create StockMovement for this component
            db.add(StockMovement(
                item_type="PRODUCT",
                item_id=comp_product.id,
                item_name=comp_product.name_display,
                movement_type="SALE",
                quantity_change=-needed,
                reason="Sale",
                supplier=None,
                purchase_price=None,
                stock_before=stock_before,
                stock_after=stock_after,
                reference=order.order_number,
            ))

    # Stamp every PENDING item with batch_id and sent_at
    for item in pending_items:
        item.batch_id = next_batch
        item.sent_at = datetime.utcnow()

    # Do NOT change order's money fields or payment_method
    db.commit()
    order_result = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order.id).first()
    return order_result


def pay_order(db: Session, order_id: int, payload: PayOrderIn, performed_by_user_id: int | None = None) -> Order:
    """
    Close an OPEN dine-in order by taking payment.

    An order must be OPEN, have all items sent to kitchen (no PENDING items),
    and pass payment validation before it can be paid. Payment details are
    written only after all validations pass — a rejected payment leaves the
    order exactly as it was.

    Stock is NOT decremented here (Rule 8): it already moved in send_batch_to_kitchen.

    Args:
        db: database session
        order_id: the order to pay
        payload: PayOrderIn with payment_method, discount, amount_received

    Returns:
        Updated Order with status="PAID", paid_at set, and money fields finalized

    Raises:
        HTTPException for validation errors
    """
    # Load order and validate
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found.")
    if order.status != "OPEN":
        raise HTTPException(400, "Only an open order can be paid.")

    # Order must have at least one item
    if not order.items:
        raise HTTPException(400, "This order has no items.")

    # Reject if any item is still PENDING (batch_id IS NULL)
    pending_count = db.query(OrderItem).filter(
        OrderItem.order_id == order_id,
        OrderItem.batch_id.is_(None),
    ).count()
    if pending_count > 0:
        raise HTTPException(400, "Send all items to the kitchen before taking payment.")

    # Recompute subtotal from ALL items
    subtotal = sum(item.line_total for item in order.items)

    # Clamp discount to subtotal
    discount = min(payload.discount, subtotal)

    # Compute tax using the order's snapshotted tax_rate
    taxable = subtotal - discount
    tax = (taxable * order.tax_rate + 5000) // 10000
    total = taxable + tax

    # Validate payment
    change = 0
    if payload.payment_method == "CASH":
        if payload.amount_received < total:
            raise HTTPException(400, f"Cash received must be at least {total}.")
        change = payload.amount_received - total

    # All validations passed. Write payment details.
    order.status = "PAID"
    order.payment_method = payload.payment_method
    order.subtotal = subtotal
    order.discount = discount
    order.tax = tax
    order.total = total
    order.amount_received = payload.amount_received
    order.change_amount = change
    order.paid_at = datetime.utcnow()
    order.performed_by_user_id = performed_by_user_id  # Stage 7: user attribution

    db.commit()
    order_result = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order.id).first()
    return order_result
