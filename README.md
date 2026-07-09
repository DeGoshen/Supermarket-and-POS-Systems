# 🛒 TechRise Python Supermarket — POS & Inventory System

A fully featured **Point of Sale (POS) and Inventory Management System** built in pure Python, developed as part of the **TechRise Cohort 3** programming curriculum. The system simulates a real supermarket environment — processing customer sales, applying discounts, tracking stock levels, and generating a Pandas-powered daily analytics report with charts.

---

## 📋 Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Installation](#installation)
- [How to Run](#how-to-run)
- [System Roles](#system-roles)
- [Discount Types](#discount-types)
- [Analytics & Reports](#analytics--reports)
- [Generated Files](#generated-files)
- [Key Concepts Demonstrated](#key-concepts-demonstrated)
- [Sample Products](#sample-products)
- [Known Limitations](#known-limitations)

---

## ✨ Features

### Point of Sale
- Browse products by **category** or view all products
- Add items to cart with quantity validation
- Real-time **stock deduction** on checkout
- Supports **Cash**, **POS/Card**, and **Bank Transfer** payment methods
- Prints a formatted **receipt** with itemised breakdown, tax, and totals
- Handles **expired** and **out-of-stock** products gracefully

### Inventory Management
- Tracks stock levels with configurable **reorder levels**
- Triggers **restock alerts** when stock falls below reorder threshold
- Supports both regular and **perishable products** (with expiry dates)
- Manager can **add new products**, **update prices**, and **restock** items

### Discount System
- **Flat discount** — fixed ₦ amount off a line item
- **Percentage discount** — e.g. 10% off
- **Buy-One-Get-One (BOGO)** — every 2nd unit free
- Discounts can be applied by cashiers during checkout or by managers via override
- Discounts shown inline on receipt

### Analytics Layer (Pandas)
- Exports `reports/sales.csv` and `reports/inventory_snapshot.csv` after each session
- Live-updating `reports/products.csv` — rewrites automatically on every stock or price change
- Generates **4 charts** saved as PNG files
- Prints a **KPI summary** to the console

---

## 📁 Project Structure

```
project/
│
├── SuperMarket_and_Point_of_Sales.py   # Main application (all logic)
├── README.md                           # This file
│
└── reports/                            # Auto-created on first run
    ├── products.csv                    # Live product catalogue (auto-updating)
    ├── sales.csv                       # Completed sale line items
    ├── inventory_snapshot.csv          # Stock snapshot at report time
    ├── top_products.png                # Top 10 revenue-generating products
    ├── revenue_by_category.png         # Revenue breakdown by category
    ├── hourly_volume.png               # Units sold per hour of day
    └── low_stock_alert.png             # Products approaching stockout
```

---

## ⚙️ Requirements

- **Python 3.10+**
- **pandas**
- **matplotlib**

No other third-party libraries are required.

---

## 🔧 Installation

### 1. Clone or download the project

```bash
git clone https://github.com/your-username/techrise-supermarket-pos.git
cd techrise-supermarket-pos
```

Or simply place `SuperMarket_and_Point_of_Sales.py` in a folder of your choice.

### 2. Create and activate a virtual environment (recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install pandas matplotlib
```

---

## ▶️ How to Run

```bash
python SuperMarket_and_Point_of_Sales.py
```

On first launch the system will:
1. Load all 20 pre-configured products into inventory
2. Write the initial `reports/products.csv`
3. Display the main menu

---

## 👥 System Roles

### Customer / Till
Select a till (1–6), browse categories, add products to cart, and proceed to checkout. No login required.

### Cashier Login
Same shopping flow as Customer but accessed through a named cashier account. Cashiers can also apply discounts during checkout.

### Manager Portal
Login with any manager account. Default PIN: **`1234`**

| Option | Action |
|--------|--------|
| `[1]` | View full inventory |
| `[2]` | View low-stock alerts |
| `[3]` | Update a product's price |
| `[4]` | Restock a product |
| `[5]` | View total inventory value |
| `[6]` | Add a new product |
| `[7]` | Apply discount override (preview tool) |
| `[8]` | Generate daily analytics report + charts |
| `[9]` | Export products list to CSV |

---

## 💰 Discount Types

| Type | How it works | Example |
|------|-------------|---------|
| Flat | Fixed ₦ amount off the whole line | ₦500 off |
| Percentage | % of gross line value | 10% off |
| BOGO | Every 2nd unit is free (requires qty ≥ 2) | Buy 2, pay for 1 |

Discounts are applied **per line item** and are visible on the receipt.

---

## 📊 Analytics & Reports

Trigger the full report from the Manager Portal → **Option 8**.

### What gets generated

| Chart | File | Description |
|-------|------|-------------|
| Top Products | `top_products.png` | Horizontal bar — top 10 products by total revenue |
| Category Revenue | `revenue_by_category.png` | Bar chart — revenue split by product category |
| Hourly Volume | `hourly_volume.png` | Line chart — units sold per hour of the day |
| Low Stock Alert | `low_stock_alert.png` | Bar chart — 10 lowest-stocked products with reorder line |

### Console KPI Summary (printed automatically)

```
═══════════════════════════════════════════════════════
                 DAILY ANALYTICS SUMMARY
═══════════════════════════════════════════════════════
  Total Revenue          : ₦  1,218,720.00
  Total Units Sold       :              96
  Top-Selling Category   : Electronics
  Products Below Reorder :               0
═══════════════════════════════════════════════════════
```

### Live Products CSV

`reports/products.csv` is written at startup and **automatically rewritten** every time any product's stock level or price changes — no manual trigger needed.

---

## 📄 Generated Files

### `reports/products.csv`

| Column | Description |
|--------|-------------|
| `sku` | Unique product code |
| `name` | Product name |
| `category` | Category name |
| `tax_rate_pct` | Tax rate as a percentage |
| `price` | Current unit price (₦) |
| `quantity_in_stock` | Current stock level |
| `reorder_level` | Stock level that triggers a restock alert |
| `is_low_stock` | `True` if stock < reorder level |
| `is_perishable` | `True` for perishable products |
| `expiry_date` | Expiry date (perishable products only) |
| `is_expired` | `True` if product has passed its expiry date |
| `last_updated` | Timestamp of last CSV write |

### `reports/sales.csv`

| Column | Description |
|--------|-------------|
| `sale_id` | Unique sale identifier (e.g. SALE-00001) |
| `cashier_name` | Name of the cashier who processed the sale |
| `product_name` | Product name |
| `sku` | Product SKU |
| `category` | Product category |
| `quantity` | Units sold |
| `unit_price` | Price per unit at time of sale |
| `discount_applied` | Discount amount in ₦ (0 if none) |
| `line_total` | Net total for this line after discount |
| `timestamp` | Date and time of the sale |

---

## 🧠 Key Concepts Demonstrated

| Concept | Where used |
|---------|-----------|
| **OOP — Classes & Inheritance** | `Product → PerishableProduct`, `Staff → Cashier / Manager`, `Discount → FlatDiscount / PercentageDiscount / BuyOneGetOneDiscount` |
| **Properties & Setters** | `Product.price`, `Product.quantity_in_stock` — with validation and auto-export hooks |
| **Decorators** | `@requires_role` (access control), `@timer` (checkout timing), `@functools.wraps` |
| **Context Manager** | `sale_transaction` — auto-completes or voids a sale via `__enter__` / `__exit__` |
| **Generator** | `Inventory.low_stock_products()` — yields products below reorder level lazily |
| **Custom Exceptions** | `OutOfStockError`, `ExpiredProductError`, `InsufficientStockError`, `PermissionError` |
| **Monkey-patching** | `SaleItem.to_dict`, auto-export hooks on property setters |
| **Pandas** | CSV export, feature engineering, groupby aggregations |
| **Matplotlib** | 4 chart types — horizontal bar, vertical bar, line + fill, bar with reference line |

---

## 🛍️ Sample Products

The system ships with 20 pre-loaded products across 5 categories:

| Category | Examples |
|----------|---------|
| Food & Beverages | Golden Penny Rice 5kg, Dangote Sugar 1kg, Semovita 1kg |
| Drinks & Beverages | Coca-Cola 60cl, Malt Drink (crate), Hollandia Evap. Milk |
| Pharmaceuticals | Paracetamol 500mg, Vitamin C 1000mg, Amoxicillin 250mg |
| Electronics | Tecno Spark 20 Pro, Infinix HOT 40i, Oraimo USB-C Charger |
| Health & Hygiene | Close-Up Toothpaste, Dettol Soap, Nivea Body Lotion |

---

## ⚠️ Known Limitations

- **Data is not persistent between sessions** — all sales and stock changes reset when the program exits. A database (e.g. SQLite) would be needed for full persistence.
- The analytics report requires **at least one completed sale** in the current session to generate charts.
- The Manager PIN is hardcoded as `1234` — in a production system this would be hashed and stored securely.
- The system is a **CLI application** — no GUI or web interface.

---

## 👨‍💻 Author

Built by **Chukwuemeka** as part of the **TechRise Cohort 3** Python curriculum.

---

*TechRise Python Supermarket POS — Aba, Abia State, Nigeria*
