# Test script for Phase 11 Deals API
# This script tests deal creation, retrieval, and validation without UI
# Usage: Run this script from the backend directory with the server running

$apiBase = "http://localhost:8000/api"
$headers = @{"Content-Type" = "application/json"}

# Step 1: Login to get token
Write-Host "===== Step 1: LOGIN =====" -ForegroundColor Cyan
$loginPayload = @{
    name = "Zohaib"
    pin = "9642"
} | ConvertTo-Json

Write-Host "POST /api/auth/login"
Write-Host "Body: $loginPayload"

$loginResponse = Invoke-WebRequest -Uri "$apiBase/auth/login" `
    -Method POST `
    -Headers $headers `
    -Body $loginPayload `
    -UseBasicParsing

$loginData = $loginResponse.Content | ConvertFrom-Json
$token = $loginData.token

Write-Host "Token received: $($token.Substring(0, 20))..." -ForegroundColor Green
Write-Host ""

# Update headers with auth token
$headers["Authorization"] = "Bearer $token"

# Step 2: Get a real product ID to use as a non-sized component
Write-Host "===== Step 2: FETCH REAL PRODUCTS =====" -ForegroundColor Cyan
Write-Host "GET /api/catalog/products"

$productsResponse = Invoke-WebRequest -Uri "$apiBase/catalog/products" `
    -Method GET `
    -Headers $headers `
    -UseBasicParsing

$products = $productsResponse.Content | ConvertFrom-Json
$nonSizedProduct = $products[0]
$sizedProduct = $null

# Find a product with sizes
foreach ($p in $products) {
    if ($p.sizes -and $p.sizes.Count -gt 0) {
        $sizedProduct = $p
        break
    }
}

if ($nonSizedProduct) {
    Write-Host "Non-sized component: $($nonSizedProduct.name_display) (ID: $($nonSizedProduct.id))"
}
if ($sizedProduct) {
    Write-Host "Sized component: $($sizedProduct.name_display) (ID: $($sizedProduct.id)) with size: $($sizedProduct.sizes[0].name) (ID: $($sizedProduct.sizes[0].id))"
}
Write-Host ""

# Step 3: Create a deal with two components
Write-Host "===== Step 3: CREATE DEAL (Happy Path) =====" -ForegroundColor Cyan

if ($sizedProduct -and $nonSizedProduct) {
    $dealPayload = @{
        category_id = $nonSizedProduct.category_id
        name = "Test Deal - Pizza + Drink"
        price = 250000  # Rs. 2500
        components = @(
            @{
                product_id = $sizedProduct.id
                quantity = 1
                size_id = $sizedProduct.sizes[0].id
            },
            @{
                product_id = $nonSizedProduct.id
                quantity = 1
                size_id = $null
            }
        )
    } | ConvertTo-Json

    Write-Host "POST /api/deals"
    Write-Host "Body: $dealPayload"

    $createResponse = Invoke-WebRequest -Uri "$apiBase/deals" `
        -Method POST `
        -Headers $headers `
        -Body $dealPayload `
        -UseBasicParsing

    $createdDeal = $createResponse.Content | ConvertFrom-Json
    $dealId = $createdDeal.id

    Write-Host "Deal created: $($createdDeal.name_display) (ID: $dealId, Price: Rs. $($createdDeal.price / 100))" -ForegroundColor Green
    Write-Host "Components: $($createdDeal.components.Count) items"
    Write-Host ""

    # Step 4: Read the deal back
    Write-Host "===== Step 4: READ DEAL BACK =====" -ForegroundColor Cyan
    Write-Host "GET /api/deals/$dealId"

    $readResponse = Invoke-WebRequest -Uri "$apiBase/deals/$dealId" `
        -Method GET `
        -Headers $headers `
        -UseBasicParsing

    $readDeal = $readResponse.Content | ConvertFrom-Json
    Write-Host "Deal retrieved: $($readDeal.name_display)" -ForegroundColor Green
    Write-Host "Components:"
    foreach ($comp in $readDeal.components) {
        Write-Host "  - Product ID: $($comp.product_id), Qty: $($comp.quantity), Size ID: $($comp.size_id)"
    }
    Write-Host ""
} else {
    Write-Host "ERROR: Could not find suitable products for test" -ForegroundColor Red
    exit 1
}

# Step 5: Try to create a deal with a component that is itself a deal (should fail cleanly)
Write-Host "===== Step 5: CREATE DEAL WITH DEAL AS COMPONENT (Expected Error) =====" -ForegroundColor Yellow

$invalidPayload = @{
    category_id = $nonSizedProduct.category_id
    name = "Invalid Deal - Contains Deal"
    price = 300000
    components = @(
        @{
            product_id = $dealId  # This is a deal, not a product
            quantity = 1
            size_id = $null
        }
    )
} | ConvertTo-Json

Write-Host "POST /api/deals (component is a deal)"
Write-Host "Expected: 400 error, got:"

try {
    $invalidResponse = Invoke-WebRequest -Uri "$apiBase/deals" `
        -Method POST `
        -Headers $headers `
        -Body $invalidPayload `
        -UseBasicParsing
    Write-Host "ERROR: Request succeeded when it should have failed!" -ForegroundColor Red
} catch {
    $statusCode = $_.Exception.Response.StatusCode
    $errorBody = $_.Exception.Response.Content | ConvertFrom-Json -ErrorAction SilentlyContinue
    Write-Host "Status Code: $statusCode" -ForegroundColor Green
    if ($errorBody) {
        Write-Host "Error Detail: $($errorBody.detail)"
    }
}
Write-Host ""

# Step 6: Try to use a size that does not exist (should fail cleanly)
Write-Host "===== Step 6: CREATE DEAL WITH INVALID SIZE (Expected Error) =====" -ForegroundColor Yellow

if ($sizedProduct) {
    $wrongSizePayload = @{
        category_id = $nonSizedProduct.category_id
        name = "Invalid Deal - Invalid Size"
        price = 300000
        components = @(
            @{
                product_id = $sizedProduct.id
                quantity = 1
                size_id = 99999  # Use an ID that cannot possibly exist
            }
        )
    } | ConvertTo-Json

    Write-Host "POST /api/deals (size_id=99999 which does not exist)"
    Write-Host "Expected: 400 error, got:"

    try {
        $wrongSizeResponse = Invoke-WebRequest -Uri "$apiBase/deals" `
            -Method POST `
            -Headers $headers `
            -Body $wrongSizePayload `
            -UseBasicParsing
        Write-Host "ERROR: Request succeeded when it should have failed!" -ForegroundColor Red
    } catch {
        $statusCode = $_.Exception.Response.StatusCode
        $errorBody = $_.Exception.Response.Content | ConvertFrom-Json -ErrorAction SilentlyContinue
        Write-Host "Status Code: $statusCode" -ForegroundColor Green
        if ($errorBody) {
            Write-Host "Error Detail: $($errorBody.detail)"
        }
    }
} else {
    Write-Host "Skipped: No sized product available for test" -ForegroundColor Yellow
}
Write-Host ""

# Step 7: Verify filtering - deal should NOT appear in catalog
Write-Host "===== Step 7: VERIFY FILTERING - Deal NOT in /api/catalog/products =====" -ForegroundColor Cyan
Write-Host "GET /api/catalog/products"

$catalogResponse = Invoke-WebRequest -Uri "$apiBase/catalog/products" `
    -Method GET `
    -Headers $headers `
    -UseBasicParsing

$catalogProducts = $catalogResponse.Content | ConvertFrom-Json
$dealInCatalog = $catalogProducts | Where-Object { $_.id -eq $dealId }

if ($dealInCatalog) {
    Write-Host "FAILED: Deal appears in catalog!" -ForegroundColor Red
} else {
    Write-Host "PASSED: Deal correctly excluded from /api/catalog/products" -ForegroundColor Green
}
Write-Host ""

# Step 8: Verify filtering - deal should NOT appear in Products inventory
Write-Host "===== Step 8: VERIFY FILTERING - Deal NOT in /api/products =====" -ForegroundColor Cyan
Write-Host "GET /api/products"

$inventoryResponse = Invoke-WebRequest -Uri "$apiBase/products" `
    -Method GET `
    -Headers $headers `
    -UseBasicParsing

$inventoryProducts = $inventoryResponse.Content | ConvertFrom-Json
$dealInInventory = $inventoryProducts | Where-Object { $_.id -eq $dealId }

if ($dealInInventory) {
    Write-Host "FAILED: Deal appears in inventory!" -ForegroundColor Red
} else {
    Write-Host "PASSED: Deal correctly excluded from /api/products" -ForegroundColor Green
}
Write-Host ""

# Step 9: Verify deal DOES appear in /api/deals
Write-Host "===== Step 9: VERIFY FILTERING - Deal IS in /api/deals =====" -ForegroundColor Cyan
Write-Host "GET /api/deals"

$dealsResponse = Invoke-WebRequest -Uri "$apiBase/deals" `
    -Method GET `
    -Headers $headers `
    -UseBasicParsing

$allDeals = $dealsResponse.Content | ConvertFrom-Json
$dealInDeals = $allDeals | Where-Object { $_.id -eq $dealId }

if ($dealInDeals) {
    Write-Host "PASSED: Deal correctly appears in /api/deals" -ForegroundColor Green
} else {
    Write-Host "FAILED: Deal does not appear in /api/deals!" -ForegroundColor Red
}
Write-Host ""

Write-Host "===== TESTS COMPLETE =====" -ForegroundColor Cyan
