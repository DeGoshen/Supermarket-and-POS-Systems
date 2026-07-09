# ============================ SUPERMARKET INVENTORY AND POINT-OF-SALES (POS) SYSTEM ==========================
"""This Project takes in orders from the manager, cashier and enters them into the system, processes them,
applies the discount and the tax rate (if any) and prints the receipt
"""

from __future__ import annotations    #Enables postposed evaluation of data anotations. Datatypes that haven't been defined yet
import time             #Imports time modules which imports time related functions, getting the current time tools
import functools        #Contains higher function utilities commonly used for at
import os           #Helps in interacting with the operating system
from datetime import date, datetime #Imports two specific classess, date and time
from typing import Iterator #Used to anotate
import getpass        # Hides the password input on the screen
import hashlib        # Used for encrypting/hashing the password

REPORTS_DIR = "reports"         # All CSV and chart outputs go here

# ========== HELPERS ==========
def clear():                                            #Clears the terminal/console screen.
    os.system("cls" if os.name == "nt" else "clear")

def pause():                                            #Pauses the program until the user presses Enter.
    input("\n  Press ENTER to continue...")

def divider(char="─", width=62):            #Prints a horizontal line (The character used to draw the line (default is ─).), 
    print(char * width)                 #(The number of times the character is repeated (default is 62).)

def header(title: str):             #indicates that the title parameter is expected to be a string (a type hint).
    divider("═")                    #Calls divider("═") before and after the title to make it stand out.
    print(f"  {title}")
    divider("═")

# ========== CUSTOM EXCEPTIONS ==========
class OutOfStockError(Exception):
    pass

class ExpiredProductError(Exception):
    pass

class InsufficientStockError(Exception):
    pass

class PermissionError(Exception):
    pass

# ========== DECORATORS ==========
def requires_role(role: str):                       #Restricts a method so only users with the specified role can execute it.
    def decorator(func):                            #Receives the function to be protected.
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):         #Checks permissions before running the function.
            if getattr(self, "staff_role", None) != role:
                raise PermissionError(
                    f"'{func.__name__}' requires role '{role}', "
                    f"but caller has role '{getattr(self, 'staff_role', 'unknown')}'."
                )
            return func(self, *args, **kwargs)
        return wrapper
    return decorator

def timer(func):                                        #Measures how long a function takes to execute.
    @functools.wraps(func)                              #Preserves the original function's name, docstring, and other metadata after decoration.
    def wrapper(*args, **kwargs):
        start = time.perf_counter()                     #Starts and stops a high-precision timer.
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        print(f"\n   Checkout processed in {elapsed:.4f}s")
        return result
    return wrapper

# ========== DISCOUNT HIERARCHY ==========
class Discount:
    def apply(self, unit_price: float, quantity: int) -> float:
        raise NotImplementedError

class FlatDiscount(Discount):
    def __init__(self, amount: float):
        self.amount = amount
    def apply(self, unit_price: float, quantity: int) -> float:
        return max(0.0, self.amount)
    def __str__(self):
        return f"Flat ₦{self.amount:,.2f} off"

class PercentageDiscount(Discount):
    def __init__(self, percent: float):
        self.percent = percent
    def apply(self, unit_price: float, quantity: int) -> float:
        return (self.percent / 100) * unit_price * quantity
    def __str__(self):
        return f"{self.percent}% off"

class BuyOneGetOneDiscount(Discount):
    def apply(self, unit_price: float, quantity: int) -> float:
        return (quantity // 2) * unit_price
    def __str__(self):
        return "Buy-One-Get-One (every 2nd unit free)"

# ========== CATEGORY ==========
class Category:
    def __init__(self, name: str, tax_rate: float = 0.0):
        self.name = name
        self.tax_rate = tax_rate

    def __str__(self):
        return f"{self.name} (tax: {self.tax_rate * 100:.1f}%)"

# ========== PRODUCT HIERARCHY ==========
class Product:
    def __init__(self, name, sku, price, category, quantity_in_stock, reorder_level):
        self.name = name
        self.sku = sku
        self._price = price
        self.category = category
        self._quantity_in_stock = quantity_in_stock
        self.reorder_level = reorder_level
        self._restock_callback = None

    @property
    def price(self):
        return self._price

    @price.setter
    def price(self, value):
        if value < 0:
            raise ValueError("Price cannot be negative.")
        self._price = value

    @property
    def quantity_in_stock(self):
        return self._quantity_in_stock

    @quantity_in_stock.setter
    def quantity_in_stock(self, value):
        if value < 0:
            raise ValueError("Stock cannot go negative.")
        self._quantity_in_stock = value
        if self._restock_callback and value < self.reorder_level:
            self._restock_callback(self)

    def is_expired(self):
        return False

    def expiry_label(self):
        return "N/A"

    def __str__(self):
        return (
            f"[{self.sku}] {self.name} | ₦{self.price:,.2f} | "
            f"Stock: {self.quantity_in_stock} | {self.category.name}"
        )

class PerishableProduct(Product):
    def __init__(self, expiry_date: date, **kwargs):
        super().__init__(**kwargs)
        self.expiry_date = expiry_date

    def is_expired(self):
        return date.today() > self.expiry_date

    def expiry_label(self):
        tag = "  EXPIRED" if self.is_expired() else ""
        return f"{self.expiry_date}{tag}"

# ========== SUPPLIER & PURCHASE ORDER ==========
class Supplier:
    def __init__(self, name, contact, products_supplied=None):
        self.name = name
        self.contact = contact
        self.products_supplied = products_supplied or []

class PurchaseOrder:
    def __init__(self, supplier, items, order_date=None):
        self.supplier = supplier
        self.items = items
        self.order_date = order_date or date.today()
        self.delivery_status = "pending"

    def mark_delivered(self):
        self.delivery_status = "delivered"
        for item in self.items:
            item["product"].quantity_in_stock += item["qty"]

# ========== INVENTORY ==========
class Inventory:
    def __init__(self):
        self._products: dict[str, Product] = {}
        self._alerts: list[str] = []

    def add_product(self, product: Product):
        product._restock_callback = self._restock_alert
        self._products[product.sku] = product

    def all_products(self) -> list[Product]:
        return list(self._products.values())

    def products_by_category(self, category_name: str) -> list[Product]:
        return [p for p in self._products.values()
                if p.category.name == category_name]

    def get_product(self, sku: str) -> Product:
        product = self._products.get(sku)
        if product is None:
            raise KeyError(f"Product with SKU '{sku}' not found.")
        return product

    def _restock_alert(self, product: Product):
        msg = (f"  RESTOCK ALERT: '{product.name}' is low "
               f"(stock: {product.quantity_in_stock}, reorder at: {product.reorder_level})")
        self._alerts.append(msg)

    def deduct_stock(self, product: Product, qty: int):
        if product.is_expired():
            raise ExpiredProductError(
                f"'{product.name}' has expired and cannot be sold.")
        if product.quantity_in_stock == 0:
            raise OutOfStockError(f"'{product.name}' is out of stock.")
        if qty > product.quantity_in_stock:
            raise InsufficientStockError(
                f"Only {product.quantity_in_stock} unit(s) of '{product.name}' available.")
        product.quantity_in_stock -= qty

    def low_stock_products(self) -> Iterator[Product]:
        for p in self._products.values():
            if p.quantity_in_stock < p.reorder_level:
                yield p

    def total_inventory_value(self) -> float:
        return sum(p.price * p.quantity_in_stock for p in self._products.values())

    def __len__(self):
        return len(self._products)

# ========== STAFF ==========
class Staff:
    def __init__(self, staff_id, name):
        self.staff_id = staff_id
        self.name = name
        self.staff_role = "Staff"

class Cashier(Staff):
    def __init__(self, staff_id, name, till_number):
        super().__init__(staff_id, name)
        self.staff_role = "Cashier"
        self.till_number = till_number

class Manager(Staff):
    def __init__(self, staff_id, name, department):
        super().__init__(staff_id, name)
        self.staff_role = "Manager"
        self.department = department

    @requires_role("Manager")                   #Ensures only managers can call the decorated method.
    def void_sale(self, sale: "Sale"):          #Marks a sale as "voided".
        sale.status = "voided"

    @requires_role("Manager")                   #Ensures only managers can call the decorated method.
    def apply_discount(self, sale_item: "SaleItem", discount: Discount):
        sale_item.discount_applied = discount

# ========== SALE / SALE ITEM / RECEIPT ==========
class SaleItem:
    def __init__(self, product, quantity, unit_price):
        self.product = product
        self.quantity = quantity
        self.unit_price = unit_price
        self.discount_applied: Discount | None = None

    @property
    def line_total(self):
        gross = self.unit_price * self.quantity
        discount = (self.discount_applied.apply(self.unit_price, self.quantity)
                    if self.discount_applied else 0.0)
        return max(0.0, gross - discount)

    def __str__(self):
        disc = f"  [{self.discount_applied}]" if self.discount_applied else ""
        return (f"  {self.product.name:<32} {self.quantity:>3} × "
                f"₦{self.unit_price:>9,.2f}{disc}  = ₦{self.line_total:>11,.2f}")

_sale_counter = 0

class Sale:
    def __init__(self, cashier):
        global _sale_counter
        _sale_counter += 1
        self.sale_id = f"SALE-{_sale_counter:05d}"
        self.cashier = cashier
        self.timestamp = datetime.now()
        self.items: list[SaleItem] = []
        self.status = "open"

    def add_item(self, item: SaleItem):
        self.items.append(item)

    def subtotal(self):
        return sum(i.line_total for i in self.items)

    def __len__(self):
        return len(self.items)

class Receipt:
    def __init__(self, sale: Sale):
        self.sale = sale
        self.total_before_tax = sale.subtotal()
        self.tax = sum(i.line_total * i.product.category.tax_rate for i in sale.items)
        self.total_after_tax = self.total_before_tax + self.tax

    def __str__(self):
        s = self.sale
        W = 62
        sep = "─" * W
        lines = [
            "═" * W,
            "TECHRISE PYTHON SUPERMARKET — RECEIPT".center(W),
            "═" * W,
            f"  Sale ID  : {s.sale_id}",
            f"  Cashier  : {s.cashier.name}  (Till {s.cashier.till_number})",
            f"  Date     : {s.timestamp.strftime('%d %b %Y  %H:%M:%S')}",
            sep,
            f"  {'ITEM':<32} {'QTY':>4}   {'UNIT PRICE':>11}   {'TOTAL':>12}",
            sep,
        ]
        for item in s.items:
            lines.append(str(item))
        lines += [
            sep,
            f"  {'Subtotal':<45} ₦{self.total_before_tax:>12,.2f}",
            f"  {'VAT / Tax':<45} ₦{self.tax:>12,.2f}",
            "═" * W,
            f"  {'AMOUNT DUE':<45} ₦{self.total_after_tax:>12,.2f}",
            "═" * W,
            "  Thank you for shopping with us!".center(W),
            "═" * W,
        ]
        return "\n".join(lines)

# ========== CONTEXT MANAGER ==========
class sale_transaction:
    def __init__(self, cashier, inventory):
        self.cashier = cashier
        self.inventory = inventory
        self.sale = None

    def __enter__(self) -> Sale:
        self.sale = Sale(self.cashier)
        return self.sale

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.sale.status = "completed"
        else:
            self.sale.status = "voided"
        return False

# ========== CHECKOUT ==========
@timer
def process_checkout(sale: Sale, inventory: Inventory) -> Receipt:
    return Receipt(sale)

# ========== INTERACTIVE CLI ==========
def prompt(msg: str, valid: list[str] | None = None) -> str:
    while True:
        raw = input(f"  {msg} ").strip()
        if valid is None or raw.lower() in [v.lower() for v in valid]:
            return raw
        print(f"  ✗ Invalid choice. Please enter one of: {', '.join(valid)}")

def prompt_int(msg: str, min_val=1, max_val=9999) -> int:
    while True:
        raw = input(f"  {msg} ").strip()
        if raw.isdigit():
            n = int(raw)
            if min_val <= n <= max_val:
                return n
        print(f"  ✗ Please enter a number between {min_val} and {max_val}.")

# ========== DISCOUNT UI HELPER ==========
# This function drives the interactive discount menu used in BOTH the cashier checkout flow and the Manager Portal.  It receives the list of SaleItem objects that are already on the sale and lets the operator:
#   1. Pick which line item to discount
#   2. Choose the discount type (Flat ₦ / Percentage % / BOGO)
#   3. Enter the relevant value
#   4. Apply or skip
def apply_discount_ui(sale_items: list[SaleItem], actor_name: str = ""):
    """
    Interactive discount application for an in-progress sale.
    Works for both cashiers (during checkout) and managers (portal).
    `actor_name` is shown in the header for context.
    """
    if not sale_items:
        print("  ✗ No items in the sale to discount.")
        pause()
        return

    while True:
        clear()
        header(f"  APPLY DISCOUNT{' — ' + actor_name if actor_name else ''}")

        # ========== Show current items ==========
        divider()
        print(f"  {'#':<4} {'PRODUCT':<34} {'QTY':>4}  {'UNIT ₦':>10}  "
              f"{'LINE TOTAL':>12}  DISCOUNT")
        divider()
        for i, si in enumerate(sale_items, 1):
            disc_label = f"[{si.discount_applied}]" if si.discount_applied else "—"
            print(f"  {i:<4} {si.product.name:<34} {si.quantity:>4}  "
                  f"₦{si.unit_price:>9,.2f}  ₦{si.line_total:>11,.2f}  {disc_label}")
        divider()

        print("\n  Enter item number to discount, or [0] to finish.\n")
        raw = input("  Item #: ").strip()
        if raw == "0":
            break
        if not raw.isdigit() or not (1 <= int(raw) <= len(sale_items)):
            print(f"  ✗ Enter a number between 1 and {len(sale_items)}, or 0 to finish.")
            pause()
            continue

        sale_item = sale_items[int(raw) - 1]
        print(f"\n  Selected: {sale_item.product.name}  "
              f"| Qty: {sale_item.quantity}  "
              f"| Unit: ₦{sale_item.unit_price:,.2f}  "
              f"| Line: ₦{sale_item.line_total:,.2f}")

        # ========== Discount type ==========
        print("\n  DISCOUNT TYPE")
        print("    [1] Flat amount off  (e.g. ₦500 off the whole line)")
        print("    [2] Percentage off   (e.g. 10% off)")
        print("    [3] Buy-One-Get-One  (every 2nd unit free)")
        print("    [4] Remove existing discount")
        print("    [0] Cancel\n")

        dtype = prompt("Type:", ["1", "2", "3", "4", "0"])

        if dtype == "0":
            continue

        elif dtype == "4":
            sale_item.discount_applied = None
            print("  ✓ Discount removed.")
            pause()
            continue

        elif dtype == "1":
            raw_amt = input("  Flat discount amount (₦): ").strip().replace(",", "")
            try:
                amt = float(raw_amt)
                if amt <= 0:
                    raise ValueError
                gross = sale_item.unit_price * sale_item.quantity
                if amt > gross:
                    print(f"  ✗ Amount ₦{amt:,.2f} exceeds line gross ₦{gross:,.2f}.")
                    pause()
                    continue
                discount = FlatDiscount(amt)
            except ValueError:
                print("  ✗ Invalid amount.")
                pause()
                continue

        elif dtype == "2":
            raw_pct = input("  Percentage (e.g. 10 for 10%): ").strip()
            try:
                pct = float(raw_pct)
                if not (0 < pct <= 100):
                    raise ValueError
                discount = PercentageDiscount(pct)
            except ValueError:
                print("  ✗ Enter a percentage between 0 and 100.")
                pause()
                continue

        elif dtype == "3":
            if sale_item.quantity < 2:
                print("  ✗ BOGO requires at least 2 units in the line.")
                pause()
                continue
            discount = BuyOneGetOneDiscount()

        # ========== Preview & confirm ==========
        gross     = sale_item.unit_price * sale_item.quantity
        saving    = discount.apply(sale_item.unit_price, sale_item.quantity)
        new_total = max(0.0, gross - saving)

        print(f"\n  Discount   : {discount}")
        print(f"  Gross line : ₦{gross:,.2f}")
        print(f"  Saving     : ₦{saving:,.2f}")
        print(f"  New total  : ₦{new_total:,.2f}")
        confirm = prompt("\n  Apply this discount? (Y/N):", ["Y", "N"]).upper()
        if confirm == "Y":
            sale_item.discount_applied = discount
            print(f"  ✓ Discount applied: {discount}")
        else:
            print("  – Discount cancelled.")
        pause()

# ========== CUSTOMER SHOPPING ==========
def show_catalog(inventory: Inventory, category_filter: str | None = None):
    products = (inventory.products_by_category(category_filter)
                if category_filter else inventory.all_products())
    products = [p for p in products if not p.is_expired()]

    if not products:
        print("  No products available in this category.")
        return []

    divider()
    print(f"  {'#':<4} {'SKU':<11} {'PRODUCT':<34} {'PRICE':>10}  {'STOCK':>6}  EXPIRES")
    divider()
    for i, p in enumerate(products, 1):
        print(f"  {i:<4} {p.sku:<11} {p.name:<34} "
              f"₦{p.price:>9,.2f}  {p.quantity_in_stock:>6}  {p.expiry_label()}")
    divider()
    return products

def customer_shop(inventory: Inventory, cashier: Cashier) -> Receipt | None:
    cart: list[dict] = []

    categories = list({p.category.name for p in inventory.all_products()
                        if not p.is_expired()})
    categories.sort()

    while True:
        clear()
        header(" TECHRISE PYTHON SUPERMARKET — SHOPPING")

        if cart:
            print(f"  Cart: {sum(c['qty'] for c in cart)} item(s) in basket\n")

        print("  BROWSE BY CATEGORY\n")
        for i, cat in enumerate(categories, 1):
            print(f"    [{i}] {cat}")
        print(f"    [A] Show ALL products")
        print(f"    [V] View cart / Checkout")
        print(f"    [X] Cancel & Exit\n")

        choice = prompt("Your choice:").upper()

        if choice == "X":
            print("\n  Shopping cancelled. Goodbye!\n")
            return None

        elif choice == "A":
            clear()
            header("ALL PRODUCTS")
            products = show_catalog(inventory)
            _pick_from_list(products, cart, inventory)

        elif choice == "V":
            result = view_cart_and_checkout(cart, inventory, cashier)
            if result is not None:
                return result

        elif choice.isdigit() and 1 <= int(choice) <= len(categories):
            cat_name = categories[int(choice) - 1]
            clear()
            header(f" {cat_name.upper()}")
            products = show_catalog(inventory, cat_name)
            _pick_from_list(products, cart, inventory)

        else:
            print("  X Invalid choice.")
            pause()

def _pick_from_list(products: list[Product], cart: list[dict], inventory: Inventory):
    if not products:
        pause()
        return

    print("\n  Enter a product number to add to cart, or 0 to go back.")
    while True:
        raw = input("  Product #: ").strip()
        if raw == "0":
            break
        if not raw.isdigit() or not (1 <= int(raw) <= len(products)):
            print(f"  ✗ Enter a number between 1 and {len(products)}, or 0 to go back.")
            continue

        product = products[int(raw) - 1]
        print(f"\n  Selected: {product.name}  |  ₦{product.price:,.2f}  "
              f"|  {product.quantity_in_stock} in stock")

        existing = next((c for c in cart if c["product"].sku == product.sku), None)
        already_in_cart = existing["qty"] if existing else 0
        max_can_add = product.quantity_in_stock - already_in_cart

        if max_can_add <= 0:
            print("  ✗ You already have the full available stock in your cart.")
            continue

        qty = prompt_int(f"Quantity (1–{max_can_add}):", 1, max_can_add)

        if existing:
            existing["qty"] += qty
        else:
            cart.append({"product": product, "qty": qty})

        print(f"  ✓ Added {qty} × {product.name} to cart.")
        cont = prompt("Add another item? (Y/N):", ["Y", "N"]).upper()
        if cont == "N":
            break

def view_cart_and_checkout(cart: list[dict], inventory: Inventory,
                            cashier: Cashier) -> Receipt | None:
    while True:
        clear()
        header(" YOUR CART")

        if not cart:
            print("  Your cart is empty.\n")
            pause()
            return None

        subtotal = 0.0
        divider()
        print(f"  {'#':<4} {'PRODUCT':<34} {'QTY':>4}   {'UNIT PRICE':>11}   {'TOTAL':>12}")
        divider()
        for i, item in enumerate(cart, 1):
            p = item["product"]
            line = p.price * item["qty"]
            subtotal += line
            print(f"  {i:<4} {p.name:<34} {item['qty']:>4}   "
                  f"₦{p.price:>9,.2f}   ₦{line:>11,.2f}")
        divider()
        print(f"  {'SUBTOTAL (excl. tax)':<52} ₦{subtotal:>11,.2f}")
        divider()

        print("\n  OPTIONS")
        print("    [C] Confirm & Checkout")
        print("    [R] Remove an item")
        print("    [S] Continue Shopping")
        print("    [X] Cancel order\n")

        choice = prompt("Your choice:", ["C", "R", "S", "X"]).upper()

        if choice == "X":
            cart.clear()
            print("\n  Order cancelled.\n")
            pause()
            return None

        elif choice == "S":
            return None

        elif choice == "R":
            num = prompt_int(f"Enter item # to remove (1–{len(cart)}):", 1, len(cart))
            removed = cart.pop(num - 1)
            print(f"  ✓ Removed: {removed['product'].name}")
            pause()

        elif choice == "C":
            return _do_checkout(cart, inventory, cashier)

# ========== After all stock is deducted and SaleItems are created, the cashier sees: ==========
#   [D] Apply / edit discounts
#   [P] Proceed to payment
#   [X] Cancel sale
# Choosing [D] calls apply_discount_ui() which lets them discount any line. After discounts are done they choose [P] to pay.  The receipt then shows each discount inline on the relevant line.
# ==========
def _do_checkout(cart: list[dict], inventory: Inventory, cashier: Cashier) -> Receipt | None:
    clear()
    header("  CHECKOUT")

    receipt = None
    try:
        with sale_transaction(cashier, inventory) as sale:          
            # ========== Build SaleItems and deduct stock ==========
            for item in cart:
                product = item["product"]
                qty = item["qty"]
                inventory.deduct_stock(product, qty)
                sale_item = SaleItem(product, qty, product.price)
                sale.add_item(sale_item)

            # ========== Discount loop ==========
            while True:                     # Preview totals before deciding
                clear()
                header("  REVIEW ORDER & DISCOUNTS")
                divider()
                print(f"  {'#':<4} {'PRODUCT':<34} {'QTY':>4}  {'UNIT ₦':>10}  "
                      f"{'LINE TOTAL':>12}  DISCOUNT")
                divider()
                for i, si in enumerate(sale.items, 1):
                    disc_label = (f"[{si.discount_applied}]"
                                  if si.discount_applied else "—")
                    print(f"  {i:<4} {si.product.name:<34} {si.quantity:>4}  "
                          f"₦{si.unit_price:>9,.2f}  ₦{si.line_total:>11,.2f}  {disc_label}")
                divider()
                running_sub = sum(si.line_total for si in sale.items)
                print(f"  {'SUBTOTAL (after discounts, excl. tax)':<52} "
                      f"₦{running_sub:>11,.2f}")
                divider()

                print("\n  OPTIONS")
                print("    [D] Apply / edit discounts on a line item")
                print("    [P] Proceed to payment")
                print("    [X] Cancel & void sale\n")

                choice = prompt("Choice:", ["D", "P", "X"]).upper()

                if choice == "X":
                    sale.status = "voided"
                                                    # Restore stock
                    for item in cart:
                        item["product"].quantity_in_stock += item["qty"]
                    print("\n  Sale voided. Stock restored.\n")
                    cart.clear()
                    pause()
                    return None

                elif choice == "D":
                    apply_discount_ui(sale.items, actor_name=cashier.name)

                elif choice == "P":
                    break                                    # proceed to payment below
            receipt = process_checkout(sale, inventory)

        # ========== Payment ==========
        total = receipt.total_after_tax
        print(f"\n  TOTAL AMOUNT DUE: ₦{total:,.2f}\n")
        divider()
        print("  PAYMENT METHOD")
        print("    [1] Cash")
        print("    [2] POS / Card")
        print("    [3] Transfer\n")
        pay_choice = prompt("Select payment method:", ["1", "2", "3"])
        methods = {"1": "Cash", "2": "POS / Card", "3": "Bank Transfer"}
        method = methods[pay_choice]

        if pay_choice == "1":
            tendered = None
            while True:
                raw = input(f"  Amount tendered (₦): ").strip().replace(",", "")
                try:
                    tendered = float(raw)
                    if tendered >= total:
                        break
                    print(f"  ✗ Amount is less than total (₦{total:,.2f}). Try again.")
                except ValueError:
                    print("  ✗ Please enter a valid amount.")
            change = tendered - total
            print(f"\n  ✓ Payment received: ₦{tendered:,.2f}")
            print(f"  ✓ Change:           ₦{change:,.2f}")
        else:
            print(f"\n  ✓ {method} payment of ₦{total:,.2f} confirmed.")

        print(f"\n  Payment method : {method}")
        pause()
        clear()
        print(receipt)
        cart.clear()
        pause()
        return receipt

    except (OutOfStockError, InsufficientStockError, ExpiredProductError) as e:
        print(f"\n  ✗ ERROR: {e}")
        print("  The sale has been voided. Please remove the item and try again.")
        for item in list(cart):
            if item["product"].is_expired() or item["product"].quantity_in_stock == 0:
                cart.remove(item)
        pause()
        return None

# ========== MANAGER PORTAL ==========
def manager_portal(inventory: Inventory, manager: Manager, all_sales: list):
    while True:
        clear()
        header(f"  MANAGER PORTAL — {manager.name}")
        print("    [1] View full inventory")
        print("    [2] View low-stock alerts")
        print("    [3] Update product price")
        print("    [4] Restock a product (simulate delivery)")
        print("    [5] View total inventory value")
        print("    [6] Add new product")
        print("    [7] Apply discount to a sale (manager override)")
        print("    [8] Generate daily analytics report")
        print("    [9] Export products list to CSV")
        print("    [0] Back to main menu\n")

        choice = prompt("Select option:", ["1","2","3","4","5","6","7","8","9","0"])

        if choice == "0":
            break

        elif choice == "1":
            clear()
            header("  FULL INVENTORY")
            divider()
            print(f"  {'SKU':<11} {'PRODUCT':<34} {'PRICE':>10}  {'STOCK':>6}  "
                  f"{'REORDER':>7}  EXPIRES")
            divider()
            for p in inventory.all_products():
                flag = " ⚠" if p.quantity_in_stock < p.reorder_level else ""
                expired = " [EXPIRED]" if p.is_expired() else ""
                print(f"  {p.sku:<11} {p.name:<34} ₦{p.price:>9,.2f}  "
                      f"{p.quantity_in_stock:>6}  {p.reorder_level:>7}  "
                      f"{p.expiry_label()}{flag}{expired}")
            divider()
            print(f"  Total products: {len(inventory)}")
            pause()

        elif choice == "2":
            clear()
            header("  LOW-STOCK ALERTS")
            found = False
            for p in inventory.low_stock_products():
                print(f"  • {p.name} (SKU: {p.sku}) — "
                      f"stock: {p.quantity_in_stock}, reorder at: {p.reorder_level}")
                found = True
            if not found:
                print("  ✓ All products are adequately stocked.")
            pause()

        elif choice == "3":
            clear()
            header("₦  UPDATE PRODUCT PRICE")
            products = inventory.all_products()
            for i, p in enumerate(products, 1):
                print(f"  [{i}] {p.name}  —  current price: ₦{p.price:,.2f}")
            num = prompt_int(f"Select product (1–{len(products)}):", 1, len(products))
            p = products[num - 1]
            raw = input(f"  New price for '{p.name}' (₦): ").strip().replace(",", "")
            try:
                new_price = float(raw)
                old = p.price
                p.price = new_price
                print(f"  ✓ Price updated: ₦{old:,.2f} → ₦{new_price:,.2f}")
            except ValueError:
                print("  ✗ Invalid price.")
            pause()

        elif choice == "4":
            clear()
            header("  RESTOCK PRODUCT")
            products = inventory.all_products()
            for i, p in enumerate(products, 1):
                print(f"  [{i}] {p.name}  —  stock: {p.quantity_in_stock}")
            num = prompt_int(f"Select product (1–{len(products)}):", 1, len(products))
            p = products[num - 1]
            qty = prompt_int("Quantity to add:", 1, 10000)
            p.quantity_in_stock += qty
            print(f"  ✓ Restocked '{p.name}' by {qty}. New stock: {p.quantity_in_stock}")
            pause()

        elif choice == "5":
            clear()
            header("  INVENTORY VALUE")
            val = inventory.total_inventory_value()
            print(f"\n  Total inventory value: ₦{val:,.2f}\n")
            pause()

        elif choice == "6":
            clear()
            header("+  ADD NEW PRODUCT")
            name = input("  Product name: ").strip()
            sku  = input("  SKU code: ").strip().upper()
            if not name or not sku:
                print("  ✗ Name and SKU are required.")
                pause()
                continue
            try:
                inventory.get_product(sku)
                print(f"  ✗ SKU '{sku}' already exists.")
                pause()
                continue
            except KeyError:
                pass

            cats = list({p.category.name: p.category
                         for p in inventory.all_products()}.values())
            for i, c in enumerate(cats, 1):
                print(f"    [{i}] {c.name}  (tax: {c.tax_rate*100:.1f}%)")
            ci = prompt_int(f"Select category (1–{len(cats)}):", 1, len(cats))
            category = cats[ci - 1]

            price_raw = input("  Price (₦): ").strip().replace(",", "")
            try:
                price = float(price_raw)
            except ValueError:
                print("  ✗ Invalid price.")
                pause()
                continue

            stock = prompt_int("  Initial stock quantity:", 0, 99999)
            reorder = prompt_int("  Reorder level:", 1, 9999)

            perishable = prompt("  Is this product perishable? (Y/N):", ["Y","N"]).upper()
            if perishable == "Y":
                exp_str = input("  Expiry date (YYYY-MM-DD): ").strip()
                try:
                    exp_date = date.fromisoformat(exp_str)
                    product = PerishableProduct(
                        expiry_date=exp_date, name=name, sku=sku, price=price,
                        category=category, quantity_in_stock=stock, reorder_level=reorder
                    )
                except ValueError:
                    print("  ✗ Invalid date format.")
                    pause()
                    continue
            else:
                product = Product(name=name, sku=sku, price=price, category=category,
                                  quantity_in_stock=stock, reorder_level=reorder)

            inventory.add_product(product)
            print(f"\n  ✓ Product '{name}' (SKU: {sku}) added to inventory.")
            pause()

        elif choice == "8":
            clear()
            header("  DAILY ANALYTICS REPORT")
            run_daily_report(all_sales, inventory)
            pause()

        elif choice == "9":
            clear()
            header("  EXPORT PRODUCTS LIST")
            path = export_products_csv(inventory)
            print(f"\n  File written to: {os.path.abspath(path)}")
            pause()

        # ========== Manager discount override ==========        # The manager builds a temporary sale from any products in inventory, applies discounts, previews the result, then exits (no actual
        # purchase is made — this is meant as a "preview/setup" tool or can be extended to create a manager-initiated sale).
        elif choice == "7":
            clear()
            header("  MANAGER DISCOUNT OVERRIDE")
            print("  Build a temporary sale to apply and preview discounts.\n")
            print("  NOTE: This creates a preview sale. To finalise a real\n"
                  "  transaction, use the Cashier / Customer Shopping flow.\n")

            # Let manager pick products to put in a preview sale
            products = [p for p in inventory.all_products() if not p.is_expired()]
            if not products:
                print("  ✗ No products available.")
                pause()
                continue

            preview_items: list[SaleItem] = []

            while True:
                clear()
                header("  MANAGER DISCOUNT — BUILD PREVIEW SALE")
                divider()
                print(f"  {'#':<4} {'SKU':<11} {'PRODUCT':<34} {'PRICE':>10}  {'STOCK':>6}")
                divider()
                for i, p in enumerate(products, 1):
                    print(f"  {i:<4} {p.sku:<11} {p.name:<34} "
                          f"₦{p.price:>9,.2f}  {p.quantity_in_stock:>6}")
                divider()

                if preview_items:
                    print(f"\n  Items in preview sale: {len(preview_items)}")

                print("\n  Enter product # to add to preview, or:")
                print("    [D] Apply discounts to current items")
                print("    [0] Exit without saving\n")

                raw = input("  Product # / Command: ").strip().upper()

                if raw == "0":
                    break

                elif raw == "D":
                    if not preview_items:
                        print("  ✗ Add at least one product first.")
                        pause()
                    else:
                        apply_discount_ui(preview_items, actor_name=f"Manager {manager.name}")
                        clear()                                                                 # Show final preview
                        header("  DISCOUNT PREVIEW SUMMARY")
                        divider()
                        print(f"  {'PRODUCT':<34} {'QTY':>4}  {'GROSS ₦':>11}  "
                              f"{'DISCOUNT':>14}  {'NET ₦':>11}")
                        divider()
                        grand_gross = 0.0
                        grand_saving = 0.0
                        grand_net = 0.0
                        for si in preview_items:
                            gross = si.unit_price * si.quantity
                            saving = (si.discount_applied.apply(si.unit_price, si.quantity)
                                      if si.discount_applied else 0.0)
                            net = si.line_total
                            grand_gross  += gross
                            grand_saving += saving
                            grand_net    += net
                            disc_label = str(si.discount_applied) if si.discount_applied else "—"
                            print(f"  {si.product.name:<34} {si.quantity:>4}  "
                                  f"₦{gross:>10,.2f}  {disc_label:>14}  ₦{net:>10,.2f}")
                        divider()
                        print(f"  {'GROSS TOTAL':<52} ₦{grand_gross:>11,.2f}")
                        print(f"  {'TOTAL SAVINGS':<52} ₦{grand_saving:>11,.2f}")
                        print(f"  {'NET TOTAL (excl. tax)':<52} ₦{grand_net:>11,.2f}")
                        divider()
                        pause()
                    break

                elif raw.isdigit() and 1 <= int(raw) <= len(products):
                    product = products[int(raw) - 1]
                    max_qty = product.quantity_in_stock
                    if max_qty == 0:
                        print("  ✗ Product is out of stock.")
                        pause()
                        continue
                    qty = prompt_int(f"Quantity (1–{max_qty}):", 1, max_qty)
                    existing = next((si for si in preview_items                     # Check if already in preview
                                     if si.product.sku == product.sku), None)
                    if existing:
                        existing.quantity += qty
                        print(f"  ✓ Updated qty for '{product.name}' to {existing.quantity}.")
                    else:
                        preview_items.append(SaleItem(product, qty, product.price))
                        print(f"  ✓ Added {qty} × {product.name} to preview.")
                    pause()

                else:
                    print("  ✗ Invalid input.")
                    pause()

# ========== CASHIER LOGIN ==========
def cashier_menu(inventory: Inventory, cashiers: list[Cashier], all_sales: list):
    clear()
    header("  CASHIER LOGIN")
    for i, c in enumerate(cashiers, 1):
        print(f"    [{i}] {c.name}  (Till {c.till_number})")
    print(f"    [0] Back\n")

    choice = prompt("Select cashier:", [str(i) for i in range(len(cashiers) + 1)])
    if choice == "0":
        return
    cashier = cashiers[int(choice) - 1]

    while True:
        clear()
        header(f"  CASHIER: {cashier.name}  |  Till {cashier.till_number}")
        print("    [1] New customer sale")
        print("    [0] Log out\n")
        c = prompt("Choice:", ["1", "0"])
        if c == "0":
            break
        receipt = customer_shop(inventory, cashier)
        if receipt is not None:
            all_sales.append(receipt.sale)

# ========== MANAGER LOGIN ==========
def manager_login(inventory: Inventory, managers: list[Manager], all_sales: list):
    clear()
    header("^  MANAGER LOGIN")
    for i, m in enumerate(managers, 1):
        print(f"    [{i}] {m.name}  ({m.department})")
    print(f"    [0] Back\n")

    choice = prompt("Select manager:", [str(i) for i in range(len(managers) + 1)])
    if choice == "0":
        return
    manager = managers[int(choice) - 1]

    # --- SECURE PIN ENTRY & ENCRYPTION ---
    # getpass prevents the PIN from being visible on the screen while typing
    pin = getpass.getpass("  Enter PIN: ").strip()
    
    # We use SHA-256 hashing (a one-way encryption) to secure the password
    hashed_pin = hashlib.sha256(pin.encode('utf-8')).hexdigest()
    
    # This is the pre-computed SHA-256 hash for the correct PIN ("1234")
    correct_hash = "03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4"
    
    if hashed_pin != correct_hash:
        print("  ✗ Incorrect PIN.")
        pause()
        return
    # -------------------------------------

    manager_portal(inventory, manager, all_sales)

# ========== MAIN — BOOTSTRAP DATA + ENTRY POINT ==========
def bootstrap_inventory() -> Inventory:
    food    = Category("Food & Beverages",  tax_rate=0.005)
    pharma  = Category("Pharmaceuticals",   tax_rate=0.00)
    elec    = Category("Electronics",       tax_rate=0.0075)
    hygiene = Category("Health & Hygiene",  tax_rate=0.0025)
    drinks  = Category("Drinks & Beverages",tax_rate=0.005)

    products = [
        Product("Golden Penny Rice 5kg",    "RICE-001", 8_500,  food,    30, 10),
        Product("Dangote Sugar 1kg",         "SUGR-002", 1_200,  food,    60, 15),
        Product("Semovita 1kg",              "SEMI-003", 1_600,  food,    45, 10),
        Product("Honeywell Flour 2kg",       "FLOR-004", 2_300,  food,    40, 12),
        PerishableProduct(date(2026, 9, 30), name="Peak Full Cream Milk 400g",
                          sku="MILK-005", price=2_200, category=food,
                          quantity_in_stock=20, reorder_level=5),
        PerishableProduct(date(2026, 8, 15), name="Trader Joe's Butter 250g",
                          sku="BUTR-006", price=3_100, category=food,
                          quantity_in_stock=15, reorder_level=4),
        PerishableProduct(date(2025, 3, 1),  name="Chi Yoghurt 250ml",
                          sku="YOGT-007", price=900,   category=food,
                          quantity_in_stock=8,  reorder_level=3),
        Product("Malt Drink 33cl (crate)",  "MALT-010", 5_500,  drinks,  20, 5),
        Product("Coca-Cola 60cl",            "COKE-011", 500,    drinks,  80, 20),
        PerishableProduct(date(2026, 12, 31), name="Hollandia Evap. Milk 400g",
                          sku="EVML-012", price=1_800, category=drinks,
                          quantity_in_stock=25, reorder_level=8),
        PerishableProduct(date(2026, 12, 31), name="Paracetamol 500mg 24-tabs",
                          sku="PARA-020", price=650,   category=pharma,
                          quantity_in_stock=80, reorder_level=20),
        PerishableProduct(date(2027, 6, 1),   name="Vitamin C 1000mg 30-tabs",
                          sku="VITC-021", price=1_400, category=pharma,
                          quantity_in_stock=50, reorder_level=15),
        PerishableProduct(date(2026, 7, 1),   name="Amoxicillin 250mg (10 caps)",
                          sku="AMOX-022", price=2_100, category=pharma,
                          quantity_in_stock=30, reorder_level=10),
        Product("Tecno Spark 20 Pro",        "PHON-030", 195_000, elec,  3,  2),
        Product("Oraimo USB-C Charger 33W",  "CHGR-031", 8_500,   elec, 15,  5),
        Product("Infinix HOT 40i",           "PHON-032", 145_000, elec,  5,  2),
        Product("Close-Up Toothpaste 100ml", "TPST-040", 1_050,  hygiene, 55, 10),
        Product("Dettol Soap 130g",          "SOAP-041", 750,    hygiene, 70, 15),
        Product("Always Maxi Pads (10-pack)","PADS-042", 1_300,  hygiene, 40, 10),
        Product("Nivea Body Lotion 400ml",   "LOTН-043", 4_800,  hygiene, 18,  5),
    ]

    inv = Inventory()
    for p in products:
        inv.add_product(p)
    return inv

# ========================================================================================
# ========== SECTION D — PANDAS ANALYTICS LAYER (DAILY REPORT) ===========================
# ========================================================================================
"""
Analytics module for the TechRise Supermarket POS system.
Provides:
  A. Export: sales + inventory → CSV
  B. Feature engineering: numeric types, timestamps, discount %, session labels
  C. Charts: top products, revenue by category, hourly volume, low-stock alert
  D. Summary console print
"""

import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")          # Non-interactive backend — no display required
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ========== SaleItem.to_dict() ==========
def _sale_item_to_dict(self) -> dict:
    """Return a flat dict suitable for Pandas / CSV export."""
    discount_value = (
        self.discount_applied.apply(self.unit_price, self.quantity)
        if self.discount_applied else 0.0
    )
    return {
        "sale_id":        self._parent_sale_id,    # injected at export time
        "cashier_name":   self._parent_cashier,    # injected at export time
        "product_name":   self.product.name,
        "sku":            self.product.sku,
        "category":       self.product.category.name,
        "quantity":       self.quantity,
        "unit_price":     self.unit_price,
        "discount_applied": discount_value,
        "line_total":     self.line_total,         # qty × unit_price − discount
        "timestamp":      self._parent_timestamp,  # injected at export time
    }

SaleItem.to_dict = _sale_item_to_dict          # monkey-patch onto the class

# ========== A-2 ▸ export_sales_csv() ==========
def export_sales_csv(all_sales: list, path: str = None) -> str:
    """
    Collect all SaleItems from completed sales only and write to CSV.

    Parameters
    ----------
    all_sales : list[Sale]
        Every Sale object created during this session.
    path : str, optional
        Override the default 'reports/sales.csv' destination.

    Returns
    -------
    str  — absolute path of the file written, or empty string if no data.
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = path or os.path.join(REPORTS_DIR, "sales.csv")

    rows = []
    for sale in all_sales:
        if sale.status != "completed":
            continue
        for item in sale.items:
            # Inject parent-sale metadata so to_dict() can read them
            item._parent_sale_id  = sale.sale_id
            item._parent_cashier  = sale.cashier.name
            item._parent_timestamp = sale.timestamp
            rows.append(item.to_dict())

    if not rows:
        print("  ⚠ No completed sales found — sales.csv not written.")
        return ""

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    print(f"  ✓ Exported {len(df)} sale-item rows → {path}")
    return path

# ========== A-3 ▸ export_inventory_csv() ==========
def export_inventory_csv(inventory: "Inventory", path: str = None) -> str:
    """
    Write a snapshot of the current inventory to CSV.

    Columns: sku, name, category, quantity_in_stock,
             reorder_level, is_low_stock
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = path or os.path.join(REPORTS_DIR, "inventory_snapshot.csv")

    rows = [
        {
            "sku":              p.sku,
            "name":             p.name,
            "category":         p.category.name,
            "quantity_in_stock": p.quantity_in_stock,
            "reorder_level":    p.reorder_level,
            "is_low_stock":     p.quantity_in_stock < p.reorder_level,
        }
        for p in inventory.all_products()
    ]

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    print(f"  ✓ Exported {len(df)} inventory rows → {path}")
    return path

# ========== A-4 ▸ export_products_csv()  — live product catalogue export ==========
def export_products_csv(inventory: "Inventory", path: str = None, silent: bool = False) -> str:
    """
    Export the full product catalogue to CSV.  Can be called on-demand or
    triggered automatically whenever stock / price changes occur.

    Columns
    -------
    sku, name, category, tax_rate, price,
    quantity_in_stock, reorder_level, is_low_stock,
    is_perishable, expiry_date, is_expired, last_updated
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = path or os.path.join(REPORTS_DIR, "products.csv")

    rows = []
    for p in inventory.all_products():
        perishable = isinstance(p, PerishableProduct)
        rows.append({
            "sku":               p.sku,
            "name":              p.name,
            "category":          p.category.name,
            "tax_rate_pct":      round(p.category.tax_rate * 100, 2),
            "price":             p.price,
            "quantity_in_stock": p.quantity_in_stock,
            "reorder_level":     p.reorder_level,
            "is_low_stock":      p.quantity_in_stock < p.reorder_level,
            "is_perishable":     perishable,
            "expiry_date":       p.expiry_date.isoformat() if perishable else "",
            "is_expired":        p.is_expired(),
            "last_updated":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    if not silent:
        print(f"  ✓ Products exported ({len(df)} rows) → {path}")
    return path

def _attach_auto_export(inventory: "Inventory"):
    """
    Monkey-patch every Product's quantity_in_stock setter so the CSV is
    rewritten silently whenever any stock level changes (sale deduction,
    restock, manual update).  Also patches the price setter.
    """
    original_qty_setter = Product.quantity_in_stock.fset
    original_price_setter = Product.price.fset

    def _qty_setter_with_export(self, value):
        original_qty_setter(self, value)
        # Re-export only if this product belongs to a tracked inventory
        if hasattr(self, "_inventory_ref") and self._inventory_ref is not None:
            export_products_csv(self._inventory_ref, silent=True)

    def _price_setter_with_export(self, value):
        original_price_setter(self, value)
        if hasattr(self, "_inventory_ref") and self._inventory_ref is not None:
            export_products_csv(self._inventory_ref, silent=True)

    Product.quantity_in_stock = Product.quantity_in_stock.setter(_qty_setter_with_export)
    Product.price = Product.price.setter(_price_setter_with_export)

    # Tag every existing product with a back-reference to its inventory
    for p in inventory.all_products():
        p._inventory_ref = inventory

    # Also patch Inventory.add_product so future additions get the tag too
    original_add = inventory.add_product.__func__

    def _add_with_tag(self, product):
        original_add(self, product)
        product._inventory_ref = self

    inventory.add_product = lambda product: _add_with_tag(inventory, product)

# ========== B ▸ load_and_engineer() — clean & feature engineering ==========
def load_and_engineer(sales_path: str) -> pd.DataFrame:
    """
    Load sales.csv and return a fully feature-engineered DataFrame.

    New columns added
    -----------------
    discount_pct   : (discount_applied / (unit_price * quantity)) * 100, 1 dp
    hour_of_sale   : integer 0-23 extracted from timestamp
    session        : 'Morning' | 'Afternoon' | 'Evening' | 'Other'
    """
    df = pd.read_csv(sales_path)

    # ========== B-1  Cast numerics ==========
    for col in ("unit_price", "discount_applied", "line_total", "quantity"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # ========== B-2  Parse timestamp ==========
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # ========== B-3  Discount percentage ==========
    gross = df["unit_price"] * df["quantity"]
    df["discount_pct"] = (df["discount_applied"] / gross * 100).round(1)
    df["discount_pct"] = df["discount_pct"].fillna(0)   # zero-price edge case

    # ========== B-4  Hour & session ==========
    df["hour_of_sale"] = df["timestamp"].dt.hour

    def _session(h):
        if 8 <= h <= 12:
            return "Morning"
        elif 13 <= h <= 17:
            return "Afternoon"
        elif 18 <= h <= 21:
            return "Evening"
        return "Other"

    df["session"] = df["hour_of_sale"].apply(_session)

    return df

# ==========C ▸ generate_charts() ==========
# Shared style helper
def _style_ax(ax, title: str, xlabel: str = "", ylabel: str = ""):
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10)
    ax.tick_params(labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

def _naira(x, _):
    """Axis formatter: ₦1,200 → '₦1.2K', '₦1.2M' etc."""
    if x >= 1_000_000:
        return f"₦{x/1_000_000:.1f}M"
    if x >= 1_000:
        return f"₦{x/1_000:.0f}K"
    return f"₦{x:,.0f}"

def chart_top_products(df: pd.DataFrame, out_dir: str = REPORTS_DIR):
    """Horizontal bar — top 10 products by total line_total."""
    top = (
        df.groupby("product_name")["line_total"]
        .sum()
        .nlargest(10)
        .sort_values()                   # ascending so longest bar is at top
    )

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(top.index, top.values, color="#2196F3", edgecolor="white", height=0.6)

    # Inline value labels
    for bar, val in zip(bars, top.values):
        ax.text(val + top.values.max() * 0.01, bar.get_y() + bar.get_height() / 2,
                f"₦{val:,.0f}", va="center", fontsize=8)

    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_naira))
    _style_ax(ax, "Top 10 Revenue-Generating Products", xlabel="Total Revenue (₦)")
    fig.tight_layout()

    path = os.path.join(out_dir, "top_products.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ Chart saved → {path}")

def chart_revenue_by_category(df: pd.DataFrame, out_dir: str = REPORTS_DIR):
    """Bar chart — total line_total by category."""
    by_cat = df.groupby("category")["line_total"].sum().sort_values(ascending=False)

    palette = ["#4CAF50", "#FF9800", "#9C27B0", "#F44336", "#00BCD4"]
    colors = [palette[i % len(palette)] for i in range(len(by_cat))]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(by_cat.index, by_cat.values, color=colors, edgecolor="white", width=0.6)

    for bar, val in zip(bars, by_cat.values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + by_cat.values.max() * 0.01,
                f"₦{val:,.0f}", ha="center", va="bottom", fontsize=8)

    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_naira))
    ax.set_xticks(range(len(by_cat)))
    ax.set_xticklabels(by_cat.index, rotation=15, ha="right")
    _style_ax(ax, "Revenue by Product Category", ylabel="Total Revenue (₦)")
    fig.tight_layout()

    path = os.path.join(out_dir, "revenue_by_category.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ Chart saved → {path}")

def chart_hourly_volume(df: pd.DataFrame, out_dir: str = REPORTS_DIR):
    """Line chart — total quantity sold per hour_of_sale."""
    by_hour = (
        df.groupby("hour_of_sale")["quantity"]
        .sum()
        .reindex(range(24), fill_value=0)   # fill gaps so x-axis is continuous
    )

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(by_hour.index, by_hour.values, color="#FF5722", linewidth=2.5,
            marker="o", markersize=5, markerfacecolor="white", markeredgewidth=1.5)
    ax.fill_between(by_hour.index, by_hour.values, alpha=0.12, color="#FF5722")

    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 24, 2)], rotation=30, ha="right")
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    _style_ax(ax, "Sales Volume by Hour of Day",
              xlabel="Hour of Sale", ylabel="Total Units Sold")
    fig.tight_layout()

    path = os.path.join(out_dir, "hourly_volume.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ Chart saved → {path}")

def chart_low_stock_alert(inv_path: str, out_dir: str = REPORTS_DIR):
    """Bar chart — 10 products with lowest quantity_in_stock + red reorder line."""
    inv_df = pd.read_csv(inv_path)

    # Bottom 10 by stock
    low10 = inv_df.nsmallest(10, "quantity_in_stock").copy()
    max_reorder = low10["reorder_level"].max()

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = [
        "#F44336" if row["quantity_in_stock"] < row["reorder_level"] else "#FF9800"
        for _, row in low10.iterrows()
    ]
    bars = ax.bar(low10["name"], low10["quantity_in_stock"],
                  color=colors, edgecolor="white", width=0.6)

    # Red dashed reorder reference line
    ax.axhline(y=max_reorder, color="red", linestyle="--", linewidth=1.5,
               label=f"Max reorder level in subset ({max_reorder})")
    ax.legend(fontsize=9)

    for bar, val in zip(bars, low10["quantity_in_stock"]):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.3,
                str(int(val)), ha="center", va="bottom", fontsize=8)

    ax.set_xticks(range(len(low10)))
    ax.set_xticklabels(low10["name"], rotation=20, ha="right", fontsize=8)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    _style_ax(ax, "Products Approaching Stockout", ylabel="Units in Stock")

    # Legend: colour meanings
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#F44336", label="Below reorder level ⚠"),
        Patch(facecolor="#FF9800", label="Low but above reorder level"),
    ]
    ax.legend(handles=legend_elements + ax.get_legend_handles_labels()[0][1:], fontsize=8)

    fig.tight_layout()
    path = os.path.join(out_dir, "low_stock_alert.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ Chart saved → {path}")

# ==========D ▸ print_summary()  — console KPI report ==========
def print_summary(df: pd.DataFrame, inv_path: str):
    inv_df = pd.read_csv(inv_path)

    total_revenue   = df["line_total"].sum()
    total_units     = int(df["quantity"].sum())
    top_category    = df.groupby("category")["line_total"].sum().idxmax()
    below_reorder   = int((inv_df["quantity_in_stock"] < inv_df["reorder_level"]).sum())

    print()
    print("═" * 55)
    print("  DAILY ANALYTICS SUMMARY".center(55))
    print("═" * 55)
    print(f"  Total Revenue          : ₦{total_revenue:>14,.2f}")
    print(f"  Total Units Sold       : {total_units:>15,}")
    print(f"  Top-Selling Category   : {top_category}")
    print(f"  Products Below Reorder : {below_reorder:>15,}")
    print("═" * 55)
    print()

# ========== PUBLIC ENTRY POINT ==========
def run_daily_report(all_sales: list, inventory: "Inventory"):
    """
    Full pipeline: export CSVs → engineer features → generate 4 charts → print KPIs.

    Call this from main() after a session, or hook it into the Manager Portal.

    Parameters
    ----------
    all_sales : list[Sale]   — pass the session's sale ledger.
    inventory : Inventory    — the live inventory object.
    """
    print()
    print("═" * 55)
    print("  GENERATING DAILY REPORT …".center(55))
    print("═" * 55)

    os.makedirs(REPORTS_DIR, exist_ok=True)

    # ========== A: Export ==========
    sales_path = export_sales_csv(all_sales)
    inv_path   = export_inventory_csv(inventory)

    if not sales_path:
        print("  ⚠ No sales data to analyse. Complete at least one sale first.")
        return

    # ========== B: Feature engineering ==========
    df = load_and_engineer(sales_path)

    # ========== C: Charts ==========
    chart_top_products(df)
    chart_revenue_by_category(df)
    chart_hourly_volume(df)
    chart_low_stock_alert(inv_path)

    # ========== D: Summary ==========
    print_summary(df, inv_path)

    print(f"  All reports saved to ./{REPORTS_DIR}/")
    print()

# ========== MAIN — ENTRY POINT ==========
def main():
    inventory = bootstrap_inventory()
    all_sales: list = []        # ← session-wide sale ledger for analytics

    # ── Products CSV: export once at startup, then auto-update on every change
    os.makedirs(REPORTS_DIR, exist_ok=True)
    export_products_csv(inventory)          # initial snapshot
    _attach_auto_export(inventory)          # silent re-export on every stock/price change

    cashiers = [
        Cashier("C001", "Onyebuchi Kingsley",  till_number=1),
        Cashier("C002", "Chioma Prosper",    till_number=2),
        Cashier("C003", "Okorie John",       till_number=3),
        Cashier("C004", "Ukandu James",      till_number=4),
        Cashier("C005", "Anayo Miracle",     till_number=5),
        Cashier("C006", "Chikara Daniel",    till_number=6),
    ]
    managers = [
        Manager("M001", "Ukala Augustine", department="General Manager"),
    ]

    while True:
        clear()
        divider("═")
        print("  TECHRISE PYTHON SUPERMARKET — POINT OF SALE SYSTEM".center(62))
        print("  Aba, Abia State, Nigeria".center(62))
        divider("═")
        print()
        print("    [1]  Customer Shopping")
        print("    [2]  Cashier Login")
        print("    [3]  Manager Portal")
        print("    [0]  Exit System")
        print()
        divider()

        choice = prompt("Select role:", ["1","2","3","0"])

        if choice == "0":
            clear()
            print("\n  System shutdown. Goodbye!\n")
            break
        elif choice == "1":
            cashier_login_choice(inventory, cashiers, all_sales)
        elif choice == "2":
            cashier_menu(inventory, cashiers, all_sales)
        elif choice == "3":
            manager_login(inventory, managers, all_sales)

def cashier_login_choice(inventory: Inventory, cashiers: list[Cashier], all_sales: list):
    clear()
    header("  WELCOME — SELECT A TILL")
    for i, c in enumerate(cashiers, 1):
        print(f"    [{i}] Till {c.till_number}  —  {c.name}")
    print(f"    [0] Back\n")

    choice = prompt("Select till:", [str(i) for i in range(len(cashiers) + 1)])
    if choice == "0":
        return
    cashier = cashiers[int(choice) - 1]
    receipt = customer_shop(inventory, cashier)
    if receipt is not None:
        all_sales.append(receipt.sale)

if __name__ == "__main__":
    main()