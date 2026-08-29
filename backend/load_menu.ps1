# ============================================================================
# Restaurant POS Menu Loader Script
# ============================================================================
# This script loads the full menu (categories and products) into the POS
# through the REST API.
#
# MODES:
#   -Mode "full"  : Bootstrap, create all categories and products, then drinks and deals.
#                   Use after fresh database wipe. Default.
#   -Mode "deals" : Login only (assumes owner exists), skip products, create only
#                   Drinks category, drink products, and 11 deals. Safe for live database.
#
# STRUCTURE:
#   1. CONFIG - API endpoint and owner credentials
#   2. DATA_BLOCK - Menu definition (categories and products)
#   3. DEALS_DATA - Deal definitions (11 deals)
#   4. FUNCTIONS - API call helpers
#   5. MAIN - Execution logic
#
# For a different restaurant, edit the DATA_BLOCK only.
# Keep all other sections unchanged.
# ============================================================================

param([string]$Mode = "full")

if ($Mode -notmatch "^(full|deals)$") {
    Write-Host -ForegroundColor Red "ERROR: Mode must be 'full' or 'deals'. Got: $Mode"
    exit 1
}

# ============================================================================
# CONFIG
# ============================================================================
$API_BASE = "http://localhost:8000/api"

# Owner account (created at startup, no user exists yet)
$OWNER_NAME = "Zohaib"
$OWNER_PIN = "9642"

# ============================================================================
# DATA_BLOCK - Restaurant Menu Definition
# ============================================================================
# Edit this section to load a different restaurant's menu.
# Format:
#   @{
#       categories = @(
#           @{ name = "CategoryName" }
#       )
#       products = @(
#           @{ category = "CategoryName", name = "ProductName", price = 45000, stock = 999, sizes = @(...) }
#       )
#   }
#
# Money is always in paisa (integer, no decimals):
#   Rs. 450 = 45000 paisa
#   Rs. 900 = 90000 paisa
#
# Stock is 999 for all products (no counting in this restaurant).
#
# Sizes format (optional):
#   sizes = @(
#       @{ name = "Small", price = 45000, sort_order = 1 }
#       @{ name = "Medium", price = 90000, sort_order = 2 }
#       @{ name = "Large", price = 120000, sort_order = 3 }
#   )

$MENU_DATA = @{
    categories = @(
        @{ name = "Pizza" }
        @{ name = "Special Pizza" }
        @{ name = "Extra Topping" }
        @{ name = "Sauce" }
        @{ name = "Pasta" }
        @{ name = "Burgers" }
        @{ name = "Shawarma" }
        @{ name = "Paratha" }
        @{ name = "Rolls" }
        @{ name = "Hot Wings & Nuggets" }
        @{ name = "Drinks" }
        @{ name = "Deals" }
    )

    products = @(
        # Pizza (S/M/L = 450 / 900 / 1200 each)
        @{
            category = "Pizza"
            name = "Chicken Fajita"
            price = 45000
            stock = 999
            sizes = @(
                @{ name = "Small"; price = 45000; sort_order = 1 }
                @{ name = "Medium"; price = 90000; sort_order = 2 }
                @{ name = "Large"; price = 120000; sort_order = 3 }
            )
        }
        @{
            category = "Pizza"
            name = "Chicken Tikka"
            price = 45000
            stock = 999
            sizes = @(
                @{ name = "Small"; price = 45000; sort_order = 1 }
                @{ name = "Medium"; price = 90000; sort_order = 2 }
                @{ name = "Large"; price = 120000; sort_order = 3 }
            )
        }
        @{
            category = "Pizza"
            name = "Chicken Supreme"
            price = 45000
            stock = 999
            sizes = @(
                @{ name = "Small"; price = 45000; sort_order = 1 }
                @{ name = "Medium"; price = 90000; sort_order = 2 }
                @{ name = "Large"; price = 120000; sort_order = 3 }
            )
        }
        @{
            category = "Pizza"
            name = "Chicken Tandoori"
            price = 45000
            stock = 999
            sizes = @(
                @{ name = "Small"; price = 45000; sort_order = 1 }
                @{ name = "Medium"; price = 90000; sort_order = 2 }
                @{ name = "Large"; price = 120000; sort_order = 3 }
            )
        }
        @{
            category = "Pizza"
            name = "Cheese Lover"
            price = 45000
            stock = 999
            sizes = @(
                @{ name = "Small"; price = 45000; sort_order = 1 }
                @{ name = "Medium"; price = 90000; sort_order = 2 }
                @{ name = "Large"; price = 120000; sort_order = 3 }
            )
        }
        @{
            category = "Pizza"
            name = "Vege Lover"
            price = 45000
            stock = 999
            sizes = @(
                @{ name = "Small"; price = 45000; sort_order = 1 }
                @{ name = "Medium"; price = 90000; sort_order = 2 }
                @{ name = "Large"; price = 120000; sort_order = 3 }
            )
        }

        # Special Pizza
        @{
            category = "Special Pizza"
            name = "Domeno Special"
            price = 55000
            stock = 999
            sizes = @(
                @{ name = "Small"; price = 55000; sort_order = 1 }
                @{ name = "Medium"; price = 120000; sort_order = 2 }
                @{ name = "Large"; price = 170000; sort_order = 3 }
            )
        }
        @{
            category = "Special Pizza"
            name = "Malai Boti Pizza"
            price = 50000
            stock = 999
            sizes = @(
                @{ name = "Small"; price = 50000; sort_order = 1 }
                @{ name = "Medium"; price = 110000; sort_order = 2 }
                @{ name = "Large"; price = 140000; sort_order = 3 }
            )
        }
        @{
            category = "Special Pizza"
            name = "Cheese Stuffer"
            price = 130000
            stock = 999
            sizes = @(
                @{ name = "Medium"; price = 130000; sort_order = 1 }
                @{ name = "Large"; price = 200000; sort_order = 2 }
            )
        }
        @{
            category = "Special Pizza"
            name = "Kabab Stuffer"
            price = 130000
            stock = 999
            sizes = @(
                @{ name = "Medium"; price = 130000; sort_order = 1 }
                @{ name = "Large"; price = 180000; sort_order = 2 }
            )
        }
        @{
            category = "Special Pizza"
            name = "Double Cheese"
            price = 50000
            stock = 999
            sizes = @(
                @{ name = "Small"; price = 50000; sort_order = 1 }
                @{ name = "Medium"; price = 110000; sort_order = 2 }
                @{ name = "Large"; price = 140000; sort_order = 3 }
            )
        }
        @{
            category = "Special Pizza"
            name = "Behari Kabab"
            price = 55000
            stock = 999
            sizes = @(
                @{ name = "Small"; price = 55000; sort_order = 1 }
                @{ name = "Medium"; price = 110000; sort_order = 2 }
                @{ name = "Large"; price = 160000; sort_order = 3 }
            )
        }

        # Extra Topping (S/M/L)
        @{
            category = "Extra Topping"
            name = "Extra Chicken"
            price = 5000
            stock = 999
            sizes = @(
                @{ name = "Small"; price = 5000; sort_order = 1 }
                @{ name = "Medium"; price = 8000; sort_order = 2 }
                @{ name = "Large"; price = 12000; sort_order = 3 }
            )
        }
        @{
            category = "Extra Topping"
            name = "Extra Cheese"
            price = 5000
            stock = 999
            sizes = @(
                @{ name = "Small"; price = 5000; sort_order = 1 }
                @{ name = "Medium"; price = 8000; sort_order = 2 }
                @{ name = "Large"; price = 12000; sort_order = 3 }
            )
        }

        # Pasta (sizes F1 and F2)
        @{
            category = "Pasta"
            name = "Creamy"
            price = 45000
            stock = 999
            sizes = @(
                @{ name = "F1"; price = 45000; sort_order = 1 }
                @{ name = "F2"; price = 80000; sort_order = 2 }
            )
        }
        @{
            category = "Pasta"
            name = "Flaming"
            price = 45000
            stock = 999
            sizes = @(
                @{ name = "F1"; price = 45000; sort_order = 1 }
                @{ name = "F2"; price = 80000; sort_order = 2 }
            )
        }
        @{
            category = "Pasta"
            name = "Crunchy"
            price = 45000
            stock = 999
            sizes = @(
                @{ name = "F1"; price = 45000; sort_order = 1 }
                @{ name = "F2"; price = 80000; sort_order = 2 }
            )
        }
        @{
            category = "Pasta"
            name = "Special Pasta"
            price = 50000
            stock = 999
            sizes = @(
                @{ name = "F1"; price = 50000; sort_order = 1 }
                @{ name = "F2"; price = 90000; sort_order = 2 }
            )
        }
        @{
            category = "Pasta"
            name = "Malai Boti Pasta"
            price = 50000
            stock = 999
            sizes = @(
                @{ name = "F1"; price = 50000; sort_order = 1 }
                @{ name = "F2"; price = 90000; sort_order = 2 }
            )
        }

        # Sauce (no sizes)
        @{
            category = "Sauce"
            name = "Dip"
            price = 3000
            stock = 999
            sizes = @()
        }
        @{
            category = "Sauce"
            name = "Special Sauce"
            price = 5000
            stock = 999
            sizes = @()
        }

        # Burgers (no sizes)
        @{
            category = "Burgers"
            name = "Chicken Burger"
            price = 25000
            stock = 999
            sizes = @()
        }
        @{
            category = "Burgers"
            name = "Zinger Burger"
            price = 30000
            stock = 999
            sizes = @()
        }
        @{
            category = "Burgers"
            name = "Chicken Cheese Burger"
            price = 28000
            stock = 999
            sizes = @()
        }
        @{
            category = "Burgers"
            name = "Zinger Cheese Burger"
            price = 35000
            stock = 999
            sizes = @()
        }
        @{
            category = "Burgers"
            name = "Special Burger"
            price = 38000
            stock = 999
            sizes = @()
        }

        # Shawarma - Pizza Shawarma (Roll/Open sizes), others no sizes
        @{
            category = "Shawarma"
            name = "Pizza Shawarma"
            price = 30000
            stock = 999
            sizes = @(
                @{ name = "Roll"; price = 30000; sort_order = 1 }
                @{ name = "Open"; price = 35000; sort_order = 2 }
            )
        }
        @{
            category = "Shawarma"
            name = "Zinger Shawarma"
            price = 30000
            stock = 999
            sizes = @()
        }
        @{
            category = "Shawarma"
            name = "Chicken Cheese Shawarma"
            price = 28000
            stock = 999
            sizes = @()
        }
        @{
            category = "Shawarma"
            name = "Zinger Cheese Shawarma"
            price = 35000
            stock = 999
            sizes = @()
        }
        @{
            category = "Shawarma"
            name = "Malai Boti Shawarma"
            price = 32000
            stock = 999
            sizes = @()
        }
        @{
            category = "Shawarma"
            name = "Platter Shawarma"
            price = 40000
            stock = 999
            sizes = @()
        }

        # Paratha - Pizza Paratha (Roll/Open sizes), others no sizes
        @{
            category = "Paratha"
            name = "Pizza Paratha"
            price = 35000
            stock = 999
            sizes = @(
                @{ name = "Roll"; price = 35000; sort_order = 1 }
                @{ name = "Open"; price = 40000; sort_order = 2 }
            )
        }
        @{
            category = "Paratha"
            name = "Chicken Paratha"
            price = 25000
            stock = 999
            sizes = @()
        }
        @{
            category = "Paratha"
            name = "Zinger Paratha"
            price = 35000
            stock = 999
            sizes = @()
        }
        @{
            category = "Paratha"
            name = "Chicken Cheese Paratha"
            price = 30000
            stock = 999
            sizes = @()
        }
        @{
            category = "Paratha"
            name = "Zinger Cheese Paratha"
            price = 38000
            stock = 999
            sizes = @()
        }
        @{
            category = "Paratha"
            name = "Malai Boti Paratha"
            price = 35000
            stock = 999
            sizes = @()
        }

        # Rolls (no sizes)
        @{
            category = "Rolls"
            name = "Spin Roll"
            price = 45000
            stock = 999
            sizes = @()
        }
        @{
            category = "Rolls"
            name = "Behari Roll"
            price = 45000
            stock = 999
            sizes = @()
        }
        @{
            category = "Rolls"
            name = "Special Roll"
            price = 50000
            stock = 999
            sizes = @()
        }
        @{
            category = "Rolls"
            name = "Crunchy Roll"
            price = 50000
            stock = 999
            sizes = @()
        }

        # Hot Wings & Nuggets (no sizes)
        @{
            category = "Hot Wings & Nuggets"
            name = "5 Hot Wings"
            price = 30000
            stock = 999
            sizes = @()
        }
        @{
            category = "Hot Wings & Nuggets"
            name = "10 Hot Wings"
            price = 50000
            stock = 999
            sizes = @()
        }
        @{
            category = "Hot Wings & Nuggets"
            name = "5 Nuggets"
            price = 30000
            stock = 999
            sizes = @()
        }
        @{
            category = "Hot Wings & Nuggets"
            name = "10 Nuggets"
            price = 50000
            stock = 999
            sizes = @()
        }
    )
}

# ============================================================================
# DRINKS_DATA - Drink Products
# ============================================================================
# Drink products are created only in Deals mode, or in Full mode if running
# for the first time. Prices are 0 (component cost); the deal's own price
# is what is charged.

$DRINKS_DATA = @(
    @{
        category = "Drinks"
        name = "Half Ltr Drink"
        price = 1
        stock = 999
        sizes = @()
    }
    @{
        category = "Drinks"
        name = "1 Ltr Drink"
        price = 1
        stock = 999
        sizes = @()
    }
    @{
        category = "Drinks"
        name = "1.5 Ltr Drink"
        price = 1
        stock = 999
        sizes = @()
    }
)

# ============================================================================
# DEALS_DATA - Restaurant Deals Definition (11 Deals)
# ============================================================================
# Each deal references products by name and, where applicable, by size name.
# All deals go in the "Deals" category.
# Components must be looked up by product name from the API.

$DEALS_DATA = @(
    @{
        name = "Student Deal-1"
        price = 315000
        components = @(
            @{ product_name = "Domeno Special"; size_name = "Large"; quantity = 1 }
            @{ product_name = "Chicken Fajita"; size_name = "Medium"; quantity = 1 }
            @{ product_name = "Zinger Burger"; quantity = 1 }
            @{ product_name = "Creamy"; size_name = "F1"; quantity = 1 }
            @{ product_name = "1 Ltr Drink"; quantity = 1 }
        )
    }
    @{
        name = "Student Deal-2"
        price = 140000
        components = @(
            @{ product_name = "Domeno Special"; size_name = "Small"; quantity = 1 }
            @{ product_name = "Chicken Fajita"; size_name = "Small"; quantity = 1 }
            @{ product_name = "Creamy"; size_name = "F1"; quantity = 1 }
            @{ product_name = "Half Ltr Drink"; quantity = 1 }
        )
    }
    @{
        name = "Deal-4"
        price = 255000
        components = @(
            @{ product_name = "Domeno Special"; size_name = "Large"; quantity = 1 }
            @{ product_name = "Chicken Fajita"; size_name = "Medium"; quantity = 1 }
            @{ product_name = "1 Ltr Drink"; quantity = 1 }
        )
    }
    @{
        name = "Mega Deal-1"
        price = 84000
        components = @(
            @{ product_name = "Domeno Special"; size_name = "Small"; quantity = 1 }
            @{ product_name = "Zinger Burger"; quantity = 1 }
            @{ product_name = "Half Ltr Drink"; quantity = 1 }
        )
    }
    @{
        name = "Mega Deal-2"
        price = 165000
        components = @(
            @{ product_name = "Domeno Special"; size_name = "Medium"; quantity = 1 }
            @{ product_name = "Zinger Burger"; quantity = 2 }
            @{ product_name = "1 Ltr Drink"; quantity = 1 }
        )
    }
    @{
        name = "Mega Deal-3"
        price = 105000
        components = @(
            @{ product_name = "Domeno Special"; size_name = "Small"; quantity = 1 }
            @{ product_name = "Chicken Fajita"; size_name = "Small"; quantity = 1 }
            @{ product_name = "1 Ltr Drink"; quantity = 1 }
        )
    }
    @{
        name = "Mega Deal-4"
        price = 170000
        components = @(
            @{ product_name = "Domeno Special"; size_name = "Medium"; quantity = 1 }
            @{ product_name = "Creamy"; size_name = "F1"; quantity = 1 }
            @{ product_name = "Zinger Burger"; quantity = 1 }
            @{ product_name = "1 Ltr Drink"; quantity = 1 }
        )
    }
    @{
        name = "Family Deal"
        price = 250000
        components = @(
            @{ product_name = "Domeno Special"; size_name = "Large"; quantity = 1 }
            @{ product_name = "Zinger Burger"; quantity = 2 }
            @{ product_name = "Creamy"; size_name = "F2"; quantity = 1 }
            @{ product_name = "Half Ltr Drink"; quantity = 1 }
        )
    }
    @{
        name = "Bumper Deal-1"
        price = 140000
        components = @(
            @{ product_name = "Chicken Tikka"; size_name = "Small"; quantity = 1 }
            @{ product_name = "Chicken Fajita"; size_name = "Small"; quantity = 1 }
            @{ product_name = "Domeno Special"; size_name = "Small"; quantity = 1 }
            @{ product_name = "1 Ltr Drink"; quantity = 1 }
        )
    }
    @{
        name = "Bumper Deal-2"
        price = 285000
        components = @(
            @{ product_name = "Chicken Tikka"; size_name = "Medium"; quantity = 1 }
            @{ product_name = "Chicken Fajita"; size_name = "Medium"; quantity = 1 }
            @{ product_name = "Domeno Special"; size_name = "Medium"; quantity = 1 }
            @{ product_name = "1.5 Ltr Drink"; quantity = 1 }
        )
    }
    @{
        name = "Bumper Deal-3"
        price = 385000
        components = @(
            @{ product_name = "Chicken Tikka"; size_name = "Large"; quantity = 1 }
            @{ product_name = "Chicken Fajita"; size_name = "Large"; quantity = 1 }
            @{ product_name = "Domeno Special"; size_name = "Large"; quantity = 1 }
            @{ product_name = "1.5 Ltr Drink"; quantity = 1 }
        )
    }
)

# ============================================================================
# FUNCTIONS
# ============================================================================

function Write-Progress-Message {
    param([string]$Message)
    Write-Host -ForegroundColor Green $Message
}

function Write-Error-Message {
    param([string]$Message)
    Write-Host -ForegroundColor Red "ERROR: $Message"
}

function Invoke-ApiCall {
    param(
        [string]$Method,
        [string]$Endpoint,
        [object]$Body,
        [string]$Token
    )
    $Url = "$API_BASE$Endpoint"
    $Headers = @{
        "Content-Type" = "application/json"
    }
    if ($Token) {
        $Headers["Authorization"] = "Bearer $Token"
    }

    try {
        $Response = Invoke-RestMethod -Uri $Url -Method $Method -Headers $Headers -Body $Body
        return $Response
    }
    catch {
        $StatusCode = $_.Exception.Response.StatusCode.Value__
        $ErrorDetail = $_.ErrorDetails.Message
        $Detail = ""

        if ($ErrorDetail) {
            try {
                $ErrorBody = $ErrorDetail | ConvertFrom-Json -ErrorAction SilentlyContinue

                # Handle different error response formats
                if ($ErrorBody.detail) {
                    # detail can be a string or a list of validation errors
                    if ($ErrorBody.detail -is [array]) {
                        # List of field validation errors (common in 422 responses)
                        $Detail = "Validation errors: "
                        foreach ($err in $ErrorBody.detail) {
                            if ($err.msg) {
                                $Detail += "`n  - $($err.loc -join '.') : $($err.msg)"
                            }
                            else {
                                $Detail += "`n  - $($err)"
                            }
                        }
                    }
                    else {
                        # String error message
                        $Detail = $ErrorBody.detail
                    }
                }
                else {
                    # No detail field, try to show the whole body
                    $Detail = $ErrorBody | ConvertTo-Json -Depth 5
                }
            }
            catch {
                # If JSON parsing fails, show raw message
                $Detail = $ErrorDetail
            }
        }
        else {
            $Detail = $_.Exception.Message
        }

        throw "API Error (HTTP $StatusCode): $Detail"
    }
}

function Create-Owner {
    Write-Progress-Message "Creating owner account..."
    $Payload = @{
        name = $OWNER_NAME
        pin = $OWNER_PIN
        is_owner = $true
    } | ConvertTo-Json
    $Owner = Invoke-ApiCall -Method "POST" -Endpoint "/users" -Body $Payload
    Write-Progress-Message "Owner created: $($Owner.name)"
    return $Owner
}

function Login {
    Write-Progress-Message "Logging in..."
    $Payload = @{
        name = $OWNER_NAME
        pin = $OWNER_PIN
    } | ConvertTo-Json
    $LoginResponse = Invoke-ApiCall -Method "POST" -Endpoint "/auth/login" -Body $Payload
    $Token = $LoginResponse.token
    Write-Progress-Message "Logged in successfully"
    return $Token
}

function Create-Category {
    param(
        [string]$Name,
        [string]$Token
    )
    $Payload = @{
        name = $Name
    } | ConvertTo-Json
    $Category = Invoke-ApiCall -Method "POST" -Endpoint "/categories" -Body $Payload -Token $Token
    return $Category
}

function Create-Product {
    param(
        [int]$CategoryId,
        [string]$Name,
        [int]$Price,
        [int]$Stock,
        [array]$Sizes,
        [string]$Token
    )
    $Payload = @{
        category_id = $CategoryId
        name = $Name
        price = $Price
        purchase_price = 0
        stock = $Stock
        min_stock = 0
        sku = $null
        unit = "Piece"
        image = $null
    }

    if ($Sizes -and $Sizes.Count -gt 0) {
        $Payload["sizes"] = $Sizes
    }

    $PayloadJson = $Payload | ConvertTo-Json -Depth 10
    $Product = Invoke-ApiCall -Method "POST" -Endpoint "/products" -Body $PayloadJson -Token $Token
    return $Product
}

function Create-Deal {
    param(
        [int]$CategoryId,
        [string]$Name,
        [int]$Price,
        [array]$Components,
        [hashtable]$ProductMap,
        [string]$Token
    )
    $Payload = @{
        category_id = $CategoryId
        name = $Name
        price = $Price
        components = @()
    }

    foreach ($Component in $Components) {
        $ProdName = $Component.product_name
        $SizeName = $Component.size_name
        $Qty = $Component.quantity

        $Prod = $ProductMap[$ProdName]
        if (-not $Prod) {
            throw "Product not found for deal component: $ProdName"
        }

        $SizeId = $null
        if ($SizeName) {
            $Size = $Prod.sizes | Where-Object { $_.name -eq $SizeName }
            if (-not $Size) {
                throw "Size not found for product $ProdName : $SizeName"
            }
            $SizeId = $Size.id
        }

        $Payload.components += @{
            product_id = $Prod.id
            quantity = $Qty
            size_id = $SizeId
        }
    }

    $PayloadJson = $Payload | ConvertTo-Json -Depth 10
    $Deal = Invoke-ApiCall -Method "POST" -Endpoint "/deals" -Body $PayloadJson -Token $Token
    return $Deal
}

# ============================================================================
# MAIN
# ============================================================================

Write-Host "==============================================================="
Write-Host "Restaurant POS Menu Loader"
Write-Host "==============================================================="
Write-Host ""

Write-Host "Mode: $Mode"
Write-Host ""

try {
    $Token = $null
    $CategoryMap = @{}
    $ProductCount = 0
    $DealCount = 0

    # ========================================================================
    # FULL MODE: Bootstrap, create all categories and products, then deals
    # ========================================================================
    if ($Mode -eq "full") {
        # Step 1: Create owner account (bootstrap)
        Create-Owner | Out-Null

        # Step 2: Login to get token
        $Token = Login

        # Step 3: Create categories
        Write-Host ""
        Write-Progress-Message "Creating categories..."
        foreach ($Cat in $MENU_DATA.categories) {
            $CreatedCat = Create-Category -Name $Cat.name -Token $Token
            $CategoryMap[$Cat.name] = $CreatedCat.id
            Write-Host -ForegroundColor Cyan "  [+] Category: $($Cat.name)"
        }
        Write-Progress-Message "Categories created: $($MENU_DATA.categories.Count) total"

        # Step 4: Create products
        Write-Host ""
        Write-Progress-Message "Creating products..."
        foreach ($Product in $MENU_DATA.products) {
            $CatId = $CategoryMap[$Product.category]
            if (-not $CatId) {
                throw "Category not found: $($Product.category)"
            }

            $Sizes = @()
            if ($Product.sizes -and $Product.sizes.Count -gt 0) {
                $Sizes = $Product.sizes
            }

            $CreatedProduct = Create-Product `
                -CategoryId $CatId `
                -Name $Product.name `
                -Price $Product.price `
                -Stock $Product.stock `
                -Sizes $Sizes `
                -Token $Token

            $ProductCount += 1
            if ($Sizes.Count -gt 0) {
                Write-Host -ForegroundColor Cyan "  [+] Product: $($Product.name) ($($Sizes.Count) sizes)"
            }
            else {
                Write-Host -ForegroundColor Cyan "  [+] Product: $($Product.name)"
            }
        }
        Write-Progress-Message "Products created: $ProductCount total"
    }

    # ========================================================================
    # DEALS MODE: Login only, skip products, create Drinks and Deals only
    # ========================================================================
    elseif ($Mode -eq "deals") {
        # Step 1: Skip owner creation, just login (assume owner exists)
        $Token = Login

        # Step 2: Fetch existing categories to get their IDs
        Write-Host ""
        Write-Progress-Message "Fetching existing categories..."
        $ExistingCats = Invoke-ApiCall -Method "GET" -Endpoint "/categories" -Token $Token
        foreach ($Cat in $ExistingCats) {
            $CategoryMap[$Cat.name_display] = $Cat.id
        }

        # Step 3: Create only Drinks category (if it doesn't exist)
        if (-not $CategoryMap["Drinks"]) {
            Write-Progress-Message "Creating Drinks category..."
            $DrinksCategory = Create-Category -Name "Drinks" -Token $Token
            $CategoryMap["Drinks"] = $DrinksCategory.id
            Write-Host -ForegroundColor Cyan "  [+] Category: Drinks"
        }
        else {
            Write-Host -ForegroundColor Cyan "  [-] Category: Drinks (already exists)"
        }

        # Step 4: Create only Drinks products
        Write-Host ""
        Write-Progress-Message "Creating drinks products..."
        foreach ($Product in $DRINKS_DATA) {
            $CatId = $CategoryMap["Drinks"]
            $CreatedProduct = Create-Product `
                -CategoryId $CatId `
                -Name $Product.name `
                -Price $Product.price `
                -Stock $Product.stock `
                -Sizes $Product.sizes `
                -Token $Token

            $ProductCount += 1
            Write-Host -ForegroundColor Cyan "  [+] Product: $($Product.name)"
        }
        Write-Progress-Message "Drink products created: $ProductCount total"
    }

    # ========================================================================
    # BOTH MODES: Create deals
    # ========================================================================
    Write-Host ""
    Write-Progress-Message "Creating deals..."

    # Build a map of product names to product objects (with sizes)
    $AllProducts = Invoke-ApiCall -Method "GET" -Endpoint "/products" -Token $Token
    $ProductMap = @{}
    foreach ($Prod in $AllProducts) {
        $ProductMap[$Prod.name_display] = $Prod
    }

    if ($DEALS_DATA -and $DEALS_DATA.Count -gt 0) {
        # Get or fetch Deals category ID
        if (-not $CategoryMap["Deals"]) {
            $AllCats = Invoke-ApiCall -Method "GET" -Endpoint "/categories" -Token $Token
            foreach ($Cat in $AllCats) {
                if ($Cat.name_display -eq "Deals") {
                    $CategoryMap["Deals"] = $Cat.id
                    break
                }
            }
        }

        $DealsCategory = $CategoryMap["Deals"]
        if (-not $DealsCategory) {
            throw "Deals category not found"
        }

        foreach ($Deal in $DEALS_DATA) {
            $CreatedDeal = Create-Deal `
                -CategoryId $DealsCategory `
                -Name $Deal.name `
                -Price $Deal.price `
                -Components $Deal.components `
                -ProductMap $ProductMap `
                -Token $Token

            $DealCount += 1
            $ComponentCount = $Deal.components.Count
            Write-Host -ForegroundColor Cyan "  [+] Deal: $($Deal.name) ($ComponentCount components)"
        }
        Write-Progress-Message "Deals created: $DealCount total"
    }

    # ========================================================================
    # SUCCESS
    # ========================================================================
    Write-Host ""
    Write-Host "==============================================================="
    Write-Host -ForegroundColor Green "SUCCESS!"
    if ($Mode -eq "full") {
        Write-Host "  Categories: $($MENU_DATA.categories.Count)"
        Write-Host "  Products: $ProductCount"
    }
    elseif ($Mode -eq "deals") {
        Write-Host "  Drinks: $ProductCount"
    }
    if ($DealCount -gt 0) {
        Write-Host "  Deals: $DealCount"
    }
    Write-Host "==============================================================="
}
catch {
    Write-Error-Message $_.Exception.Message
    exit 1
}
