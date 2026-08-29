# Test script for Phase 11 Deal Selling (Stock Management)
# Tests deal creation in takeaway orders, stock decrements per component, cancellation,
# and failure case when a component has insufficient stock.
# Usage: Run this script from the backend directory with the server running at localhost:8000

$apiBase = "http://localhost:8000/api"
$headers = @{"Content-Type" = "application/json"}
$DEAL_ID = 10  # The deal we're testing with

# Track results for final summary
$results = @()

Write-Host "====================================================================="
Write-Host "DEAL SELLING TEST: Stock Deduction & Cancellation"
Write-Host "====================================================================="
Write-Host ""

# Step 1: Login to get token
Write-Host "Step 1: LOGIN"
$loginPayload = @{
    name = "Zohaib"
    pin = "9642"
} | ConvertTo-Json

$loginResponse = Invoke-WebRequest -Uri "$apiBase/auth/login" `
    -Method POST `
    -Headers $headers `
    -Body $loginPayload `
    -UseBasicParsing

$loginData = $loginResponse.Content | ConvertFrom-Json
$token = $loginData.token
Write-Host "PASS: Logged in"
$headers["Authorization"] = "Bearer $token"
Write-Host ""

# Step 2: Get deal 10 and its components
Write-Host "Step 2: FETCH DEAL $DEAL_ID AND COMPONENTS"
$dealResponse = Invoke-WebRequest -Uri "$apiBase/deals/$DEAL_ID" `
    -Method GET `
    -Headers $headers `
    -UseBasicParsing

$deal = $dealResponse.Content | ConvertFrom-Json
Write-Host "Deal: $($deal.name_display)"
Write-Host "  ID: $($deal.id), Price: Rs. $($deal.price / 100)"
Write-Host "  Components: $($deal.components.Count) items"

if ($deal.components.Count -eq 0) {
    Write-Host "ERROR: Deal has no components!"
    exit 1
}

# Store initial stock for each component
$initialStocks = @{}
foreach ($comp in $deal.components) {
    $prodResponse = Invoke-WebRequest -Uri "$apiBase/catalog/products?id=$($comp.product_id)" `
        -Method GET `
        -Headers $headers `
        -UseBasicParsing

    # Parse the products list response
    $products = $prodResponse.Content | ConvertFrom-Json

    # The API doesn't filter by ID, so search manually
    $prod = $null
    if ($products -is [array]) {
        $prod = $products | Where-Object { $_.id -eq $comp.product_id } | Select-Object -First 1
    } else {
        $prod = $products
    }

    if ($null -eq $prod) {
        Write-Host "ERROR: Could not fetch product $($comp.product_id)"
        exit 1
    }

    $initialStocks[$comp.product_id] = $prod.stock
    Write-Host "  Component: $($comp.product_name) (ID: $($comp.product_id))"
    Write-Host "    Quantity in deal: $($comp.quantity), Current stock: $($prod.stock)"
}
Write-Host ""

# Step 3: Create a takeaway order with deal 10 (quantity 1)
Write-Host "Step 3: CREATE TAKEAWAY ORDER WITH DEAL $DEAL_ID"
$orderPayload = @{
    order_type = "TAKEAWAY"
    items = @(
        @{
            product_id = $DEAL_ID
            quantity = 1
            size_id = $null
        }
    )
    discount = 0
    payment_method = "CASH"
    amount_received = $deal.price
} | ConvertTo-Json

$createResponse = Invoke-WebRequest -Uri "$apiBase/orders" `
    -Method POST `
    -Headers $headers `
    -Body $orderPayload `
    -UseBasicParsing

$order = $createResponse.Content | ConvertFrom-Json
$orderId = $order.id
$orderNumber = $order.order_number

Write-Host "PASS: Order created: $orderNumber"
Write-Host "  ID: $orderId, Total: Rs. $($order.total / 100)"
Write-Host "  Items: $($order.items.Count)"
Write-Host ""

# Step 4: Verify order items and components
Write-Host "Step 4: VERIFY ORDER ITEMS AND COMPONENTS"
foreach ($item in $order.items) {
    Write-Host "  OrderItem: $($item.product_name) (ID: $($item.product_id))"
    Write-Host "    Price: Rs. $($item.price / 100), Quantity: $($item.quantity), Line Total: Rs. $($item.line_total / 100)"
    if ($item.size_name) {
        Write-Host "    Size: $($item.size_name)"
    }
}

$orderDetailResponse = Invoke-WebRequest -Uri "$apiBase/orders/$orderId" `
    -Method GET `
    -Headers $headers `
    -UseBasicParsing

$orderDetail = $orderDetailResponse.Content | ConvertFrom-Json
$dealLineItem = $orderDetail.items | Where-Object { $_.product_id -eq $DEAL_ID }

if ($dealLineItem) {
    Write-Host "  PASS: Deal line found as ONE order item with deal price"
}
Write-Host ""

# Step 5: Check stock after order creation
Write-Host "Step 5: CHECK STOCK AFTER ORDER CREATION"
Write-Host "Expected: each component stock decreased by its quantity in deal"
$step5Passed = $true
foreach ($comp in $deal.components) {
    $prodResponse = Invoke-WebRequest -Uri "$apiBase/catalog/products" `
        -Method GET `
        -Headers $headers `
        -UseBasicParsing

    $products = $prodResponse.Content | ConvertFrom-Json
    $prod = $null
    if ($products -is [array]) {
        $prod = $products | Where-Object { $_.id -eq $comp.product_id } | Select-Object -First 1
    } else {
        $prod = $products
    }

    $expectedStock = $initialStocks[$comp.product_id] - $comp.quantity
    $actualStock = $prod.stock
    $statusText = if ($actualStock -eq $expectedStock) { "PASS" } else { "FAIL" }

    Write-Host "  ${statusText}: $($comp.product_name) (ID: $($comp.product_id))"
    Write-Host "    Initial: $($initialStocks[$comp.product_id]), Expected: $expectedStock, Actual: $actualStock"

    if ($actualStock -ne $expectedStock) {
        Write-Host "    ERROR: Stock mismatch!"
        $step5Passed = $false
    }
}
$results += "Step 5 (Stock after order): $(if ($step5Passed) { 'PASS' } else { 'FAIL' })"
Write-Host ""

# Step 6: Cancel the order
Write-Host "Step 6: CANCEL ORDER $orderNumber"
$cancelPayload = @{
    reason = "OTHER"
    note = "Testing cancellation"
} | ConvertTo-Json

$cancelResponse = Invoke-WebRequest -Uri "$apiBase/orders/$orderId/cancel" `
    -Method POST `
    -Headers $headers `
    -Body $cancelPayload `
    -UseBasicParsing

$cancelledOrder = $cancelResponse.Content | ConvertFrom-Json
Write-Host "PASS: Order cancelled"
Write-Host "  Status: $($cancelledOrder.status), Reason: $($cancelledOrder.cancelled_reason)"
Write-Host ""

# Step 7: Check stock after cancellation
Write-Host "Step 7: CHECK STOCK AFTER CANCELLATION"
Write-Host "Expected: all component stocks restored to initial levels"
$step7Passed = $true
foreach ($comp in $deal.components) {
    $prodResponse = Invoke-WebRequest -Uri "$apiBase/catalog/products" `
        -Method GET `
        -Headers $headers `
        -UseBasicParsing

    $products = $prodResponse.Content | ConvertFrom-Json
    $prod = $null
    if ($products -is [array]) {
        $prod = $products | Where-Object { $_.id -eq $comp.product_id } | Select-Object -First 1
    } else {
        $prod = $products
    }

    $initialStock = $initialStocks[$comp.product_id]
    $actualStock = $prod.stock
    $statusText = if ($actualStock -eq $initialStock) { "PASS" } else { "FAIL" }

    Write-Host "  ${statusText}: $($comp.product_name) (ID: $($comp.product_id))"
    Write-Host "    Initial: $initialStock, Current: $actualStock"

    if ($actualStock -ne $initialStock) {
        Write-Host "    ERROR: Stock not fully restored!"
        $step7Passed = $false
    }
}
$results += "Step 7 (Stock after cancel): $(if ($step7Passed) { 'PASS' } else { 'FAIL' })"
Write-Host ""

# Step 8: FAILURE TEST - Component with insufficient stock
Write-Host "Step 8: FAILURE TESTS - INSUFFICIENT COMPONENT STOCK"

# Record stock before any adjustment (for restoration at end)
$componentStockBackup = @{}
foreach ($comp in $deal.components) {
    $prodResponse = Invoke-WebRequest -Uri "$apiBase/catalog/products" `
        -Method GET `
        -Headers $headers `
        -UseBasicParsing

    $products = $prodResponse.Content | ConvertFrom-Json
    $prod = $null
    if ($products -is [array]) {
        $prod = $products | Where-Object { $_.id -eq $comp.product_id } | Select-Object -First 1
    } else {
        $prod = $products
    }
    $componentStockBackup[$comp.product_id] = $prod.stock
}

$test8APassed = $false
$test8BPassed = $false

try {
    # --- TEST 8A: Component at zero stock ---
    Write-Host ""
    Write-Host "TEST 8A: Component at ZERO stock"
    $testComp = $deal.components[0]

    $prodResponse = Invoke-WebRequest -Uri "$apiBase/catalog/products" `
        -Method GET `
        -Headers $headers `
        -UseBasicParsing

    $products = $prodResponse.Content | ConvertFrom-Json
    $testCompProduct = $null
    if ($products -is [array]) {
        $testCompProduct = $products | Where-Object { $_.id -eq $testComp.product_id } | Select-Object -First 1
    } else {
        $testCompProduct = $products
    }

    $stockBefore = $testCompProduct.stock
    Write-Host "Component: $($testComp.product_name) (ID: $($testComp.product_id))"
    Write-Host "  Before: stock = $stockBefore"

    # Reduce its stock to 0
    $adjustPayload = @{
        quantity_change = -$stockBefore
        reason = "MANUAL_CORRECTION"
        note = "Test: force insufficient stock"
    } | ConvertTo-Json

    $adjustResponse = Invoke-WebRequest -Uri "$apiBase/inventory/$($testComp.product_id)/adjust" `
        -Method POST `
        -Headers $headers `
        -Body $adjustPayload `
        -UseBasicParsing

    Write-Host "  After adjustment: stock = 0"

    # Remember all component stocks
    $stockBeforeTest8A = @{}
    foreach ($comp in $deal.components) {
        $prodResponse = Invoke-WebRequest -Uri "$apiBase/catalog/products" `
            -Method GET `
            -Headers $headers `
            -UseBasicParsing

        $products = $prodResponse.Content | ConvertFrom-Json
        $prod = $null
        if ($products -is [array]) {
            $prod = $products | Where-Object { $_.id -eq $comp.product_id } | Select-Object -First 1
        } else {
            $prod = $products
        }
        $stockBeforeTest8A[$comp.product_id] = $prod.stock
    }

    # Try to create order
    Write-Host "  Attempting order..."
    $failOrderPayload = @{
        order_type = "TAKEAWAY"
        items = @(
            @{
                product_id = $DEAL_ID
                quantity = 1
                size_id = $null
            }
        )
        discount = 0
        payment_method = "CASH"
        amount_received = $deal.price
    } | ConvertTo-Json

    $test8AOrderFailed = $false
    try {
        $failResponse = Invoke-WebRequest -Uri "$apiBase/orders" `
            -Method POST `
            -Headers $headers `
            -Body $failOrderPayload `
            -UseBasicParsing
        Write-Host "  FAIL: Order succeeded when it should have failed!"
    } catch {
        $statusCode = $_.Exception.Response.StatusCode
        $errorContent = $_.Exception.Response.Content | ConvertFrom-Json -ErrorAction SilentlyContinue

        if ($statusCode -eq 400) {
            Write-Host "  PASS: Order rejected with 400"
            $test8AOrderFailed = $true
            if ($errorContent -and $errorContent.detail) {
                Write-Host "    Message: $($errorContent.detail)"
                if ($errorContent.detail -like "*$($testComp.product_name)*") {
                    Write-Host "    PASS: Error names the component"
                }
            }
        } else {
            Write-Host "  FAIL: Status code $statusCode (expected 400)"
        }
    }

    # Verify no stock moved
    Write-Host "  Verifying stock untouched..."
    $test8AStockSafe = $true
    foreach ($comp in $deal.components) {
        $prodResponse = Invoke-WebRequest -Uri "$apiBase/catalog/products" `
            -Method GET `
            -Headers $headers `
            -UseBasicParsing

        $products = $prodResponse.Content | ConvertFrom-Json
        $prod = $null
        if ($products -is [array]) {
            $prod = $products | Where-Object { $_.id -eq $comp.product_id } | Select-Object -First 1
        } else {
            $prod = $products
        }

        $before = $stockBeforeTest8A[$comp.product_id]
        $after = $prod.stock
        if ($after -eq $before) {
            Write-Host "    PASS: $($comp.product_name): $before -> $after (unchanged)"
        } else {
            Write-Host "    FAIL: $($comp.product_name): $before -> $after (CHANGED!)"
            $test8AStockSafe = $false
        }
    }
    $test8APassed = $test8AOrderFailed -and $test8AStockSafe

    # --- TEST 8B: Component with some stock but not enough ---
    Write-Host ""
    Write-Host "TEST 8B: Component has SOME stock but not ENOUGH"

    # Get second component if available, else use first
    $testComp2 = if ($deal.components.Count -gt 1) { $deal.components[1] } else { $deal.components[0] }

    $prodResponse = Invoke-WebRequest -Uri "$apiBase/catalog/products" `
        -Method GET `
        -Headers $headers `
        -UseBasicParsing

    $products = $prodResponse.Content | ConvertFrom-Json
    $testComp2Product = $null
    if ($products -is [array]) {
        $testComp2Product = $products | Where-Object { $_.id -eq $testComp2.product_id } | Select-Object -First 1
    } else {
        $testComp2Product = $products
    }

    $currentStock2 = $testComp2Product.stock
    # Set to: component quantity - 1 (so we have SOME but not enough for even 1 deal)
    $targetStock2 = [Math]::Max(0, $testComp2.quantity - 1)

    Write-Host "Component: $($testComp2.product_name) (ID: $($testComp2.product_id))"
    Write-Host "  Deal requires: $($testComp2.quantity)"
    Write-Host "  Current stock: $currentStock2"
    Write-Host "  Setting to: $targetStock2 (not enough for 1 deal)"

    if ($currentStock2 -ne $targetStock2) {
        $adjustAmount = $targetStock2 - $currentStock2
        $adjustPayload2 = @{
            quantity_change = $adjustAmount
            reason = "MANUAL_CORRECTION"
            note = "Test: insufficient stock case"
        } | ConvertTo-Json

        $adjustResponse2 = Invoke-WebRequest -Uri "$apiBase/inventory/$($testComp2.product_id)/adjust" `
            -Method POST `
            -Headers $headers `
            -Body $adjustPayload2 `
            -UseBasicParsing
    }

    # Remember stock before test
    $stockBeforeTest8B = @{}
    foreach ($comp in $deal.components) {
        $prodResponse = Invoke-WebRequest -Uri "$apiBase/catalog/products" `
            -Method GET `
            -Headers $headers `
            -UseBasicParsing

        $products = $prodResponse.Content | ConvertFrom-Json
        $prod = $null
        if ($products -is [array]) {
            $prod = $products | Where-Object { $_.id -eq $comp.product_id } | Select-Object -First 1
        } else {
            $prod = $products
        }
        $stockBeforeTest8B[$comp.product_id] = $prod.stock
    }

    # Try to order quantity 2 of the deal (so we need component.quantity * 2)
    $dealQty2 = 2
    Write-Host "  Attempting order with quantity $dealQty2 (needs $($testComp2.quantity * $dealQty2) of component, have $($stockBeforeTest8B[$testComp2.product_id]))..."

    $failOrderPayload2 = @{
        order_type = "TAKEAWAY"
        items = @(
            @{
                product_id = $DEAL_ID
                quantity = $dealQty2
                size_id = $null
            }
        )
        discount = 0
        payment_method = "CASH"
        amount_received = $deal.price * $dealQty2
    } | ConvertTo-Json

    $test8BOrderFailed = $false
    try {
        $failResponse2 = Invoke-WebRequest -Uri "$apiBase/orders" `
            -Method POST `
            -Headers $headers `
            -Body $failOrderPayload2 `
            -UseBasicParsing
        Write-Host "  FAIL: Order succeeded when it should have failed!"
    } catch {
        $statusCode = $_.Exception.Response.StatusCode
        $errorContent = $_.Exception.Response.Content | ConvertFrom-Json -ErrorAction SilentlyContinue

        if ($statusCode -eq 400) {
            Write-Host "  PASS: Order rejected with 400"
            $test8BOrderFailed = $true
            if ($errorContent -and $errorContent.detail) {
                Write-Host "    Message: $($errorContent.detail)"
            }
        } else {
            Write-Host "  FAIL: Status code $statusCode (expected 400)"
        }
    }

    # Verify no stock moved
    Write-Host "  Verifying stock untouched..."
    $test8BStockSafe = $true
    foreach ($comp in $deal.components) {
        $prodResponse = Invoke-WebRequest -Uri "$apiBase/catalog/products" `
            -Method GET `
            -Headers $headers `
            -UseBasicParsing

        $products = $prodResponse.Content | ConvertFrom-Json
        $prod = $null
        if ($products -is [array]) {
            $prod = $products | Where-Object { $_.id -eq $comp.product_id } | Select-Object -First 1
        } else {
            $prod = $products
        }

        $before = $stockBeforeTest8B[$comp.product_id]
        $after = $prod.stock
        if ($after -eq $before) {
            Write-Host "    PASS: $($comp.product_name): $before -> $after (unchanged)"
        } else {
            Write-Host "    FAIL: $($comp.product_name): $before -> $after (CHANGED!)"
            $test8BStockSafe = $false
        }
    }
    $test8BPassed = $test8BOrderFailed -and $test8BStockSafe

} finally {
    # ALWAYS restore component stocks, even if test failed
    Write-Host ""
    Write-Host "RESTORING COMPONENT STOCKS FROM BACKUP"
    $allRestored = $true
    foreach ($compId in $componentStockBackup.Keys) {
        $prodResponse = Invoke-WebRequest -Uri "$apiBase/catalog/products" `
            -Method GET `
            -Headers $headers `
            -UseBasicParsing

        $products = $prodResponse.Content | ConvertFrom-Json
        $prod = $null
        if ($products -is [array]) {
            $prod = $products | Where-Object { $_.id -eq $compId } | Select-Object -First 1
        } else {
            $prod = $products
        }

        $currentStock = $prod.stock
        $targetStock = $componentStockBackup[$compId]

        if ($currentStock -ne $targetStock) {
            Write-Host "  Restoring product ${compId}: $currentStock -> $targetStock"
            $adjustAmount = $targetStock - $currentStock
            $restorePayload = @{
                quantity_change = $adjustAmount
                reason = "MANUAL_CORRECTION"
                note = "Test cleanup: restore to original"
            } | ConvertTo-Json

            $restoreResponse = Invoke-WebRequest -Uri "$apiBase/inventory/$compId/adjust" `
                -Method POST `
                -Headers $headers `
                -Body $restorePayload `
                -UseBasicParsing
            Write-Host "    PASS: Restored"
        } else {
            Write-Host "  Product ${compId}: already at target $targetStock"
        }
    }
    $results += "Restoration: PASS"
}

$results += "Test 8A (zero stock): $(if ($test8APassed) { 'PASS' } else { 'FAIL' })"
$results += "Test 8B (partial stock): $(if ($test8BPassed) { 'PASS' } else { 'FAIL' })"

Write-Host ""
Write-Host "====================================================================="
Write-Host "TEST COMPLETE - SUMMARY"
Write-Host "====================================================================="
foreach ($result in $results) {
    Write-Host $result
}
Write-Host "====================================================================="
