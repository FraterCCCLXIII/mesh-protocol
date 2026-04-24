#!/usr/bin/env python3
"""
MESH Payment Service
Stripe integration for subscriptions and creator payouts
Includes STUB MODE for testing without Stripe
"""
import os
import json
import secrets
from datetime import datetime, timedelta
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aiosqlite

# Stripe setup
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_CONNECT_CLIENT_ID = os.environ.get("STRIPE_CONNECT_CLIENT_ID", "")

# STUB MODE - for testing without Stripe
STUB_MODE = os.environ.get("PAYMENTS_STUB_MODE", "true").lower() == "true"

DB_PATH = os.environ.get("PAYMENTS_DB_PATH", "payments.db")
db: Optional[aiosqlite.Connection] = None

# Try to import stripe
STRIPE_AVAILABLE = False
if STRIPE_SECRET_KEY and not STUB_MODE:
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        STRIPE_AVAILABLE = True
    except ImportError:
        print("[Payments] Stripe not installed - running in stub mode")

if STUB_MODE or not STRIPE_AVAILABLE:
    print("[Payments] Running in STUB MODE - all payments are simulated")

async def init_db():
    global db
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            publication_id TEXT NOT NULL,
            name TEXT NOT NULL,
            stripe_product_id TEXT,
            stripe_price_monthly_id TEXT,
            stripe_price_yearly_id TEXT,
            price_monthly INTEGER DEFAULT 0,
            price_yearly INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS subscriptions (
            id TEXT PRIMARY KEY,
            subscriber_id TEXT NOT NULL,
            publication_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            tier TEXT DEFAULT 'monthly',
            status TEXT DEFAULT 'active',
            stripe_subscription_id TEXT,
            stripe_customer_id TEXT,
            current_period_start TEXT,
            current_period_end TEXT,
            created_at TEXT NOT NULL,
            canceled_at TEXT
        );
        CREATE TABLE IF NOT EXISTS customers (
            entity_id TEXT PRIMARY KEY,
            stripe_customer_id TEXT NOT NULL,
            email TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS connect_accounts (
            entity_id TEXT PRIMARY KEY,
            stripe_account_id TEXT NOT NULL,
            onboarding_complete INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS payouts (
            id TEXT PRIMARY KEY,
            creator_id TEXT NOT NULL,
            amount INTEGER NOT NULL,
            currency TEXT DEFAULT 'usd',
            status TEXT DEFAULT 'pending',
            stripe_transfer_id TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_subs_subscriber ON subscriptions(subscriber_id);
        CREATE INDEX IF NOT EXISTS idx_subs_publication ON subscriptions(publication_id);
        CREATE INDEX IF NOT EXISTS idx_products_publication ON products(publication_id);
    """)
    await db.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print(f"[Payments] Started (Stripe: {'enabled' if STRIPE_AVAILABLE else 'mock'})")
    yield
    if db: await db.close()

app = FastAPI(title="MESH Payment Service", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Models
class ProductCreate(BaseModel):
    publication_id: str
    name: str
    price_monthly: int  # cents
    price_yearly: int   # cents

class CheckoutRequest(BaseModel):
    subscriber_id: str
    product_id: str
    tier: str = "monthly"  # monthly or yearly
    success_url: str
    cancel_url: str

class ConnectOnboardRequest(BaseModel):
    entity_id: str
    email: str
    return_url: str
    refresh_url: str

@app.get("/health")
async def health():
    return {
        "status": "healthy", 
        "service": "payments", 
        "stripe": STRIPE_AVAILABLE,
        "stub_mode": STUB_MODE or not STRIPE_AVAILABLE,
    }


# ========== Stub Payment Endpoints ==========

@app.post("/api/stub/pay")
async def stub_pay(req: dict):
    """Simulate a successful payment (STUB MODE)."""
    subscriber_id = req.get("subscriber_id")
    product_id = req.get("product_id")
    amount = req.get("amount", 999)  # Default $9.99
    
    if not subscriber_id or not product_id:
        raise HTTPException(400, "subscriber_id and product_id required")
    
    # Get product
    cursor = await db.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = await cursor.fetchone()
    if not product:
        raise HTTPException(404, "Product not found")
    
    # Create subscription
    sub_id = secrets.token_hex(16)
    now = datetime.utcnow()
    period_end = now + timedelta(days=30)
    
    await db.execute("""
        INSERT INTO subscriptions (id, subscriber_id, publication_id, product_id, 
            tier, status, current_period_start, current_period_end, created_at)
        VALUES (?, ?, ?, ?, 'monthly', 'active', ?, ?, ?)
    """, (sub_id, subscriber_id, product["publication_id"], product_id,
          now.isoformat(), period_end.isoformat(), now.isoformat()))
    await db.commit()
    
    return {
        "status": "success",
        "subscription_id": sub_id,
        "amount": amount,
        "period_end": period_end.isoformat(),
        "stub": True,
    }


@app.post("/api/stub/refund")
async def stub_refund(req: dict):
    """Simulate a refund (STUB MODE)."""
    subscription_id = req.get("subscription_id")
    
    if not subscription_id:
        raise HTTPException(400, "subscription_id required")
    
    await db.execute(
        "UPDATE subscriptions SET status = 'refunded' WHERE id = ?",
        (subscription_id,)
    )
    await db.commit()
    
    return {"status": "refunded", "subscription_id": subscription_id, "stub": True}


@app.get("/api/stub/transactions")
async def stub_list_transactions(subscriber_id: str = Query(None)):
    """List simulated transactions (STUB MODE)."""
    query = """
        SELECT s.*, p.name as product_name, p.price_monthly
        FROM subscriptions s
        JOIN products p ON s.product_id = p.id
    """
    params = []
    
    if subscriber_id:
        query += " WHERE s.subscriber_id = ?"
        params.append(subscriber_id)
    
    query += " ORDER BY s.created_at DESC LIMIT 100"
    
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    
    transactions = []
    for row in rows:
        transactions.append({
            "id": row["id"],
            "subscriber_id": row["subscriber_id"],
            "product_name": row["product_name"],
            "amount": row["price_monthly"],
            "status": row["status"],
            "created_at": row["created_at"],
            "stub": True,
        })
    
    return {"transactions": transactions}


@app.post("/api/stub/creator-payout")
async def stub_creator_payout(req: dict):
    """Simulate a creator payout (STUB MODE)."""
    creator_id = req.get("creator_id")
    amount = req.get("amount", 0)
    
    if not creator_id or amount <= 0:
        raise HTTPException(400, "creator_id and positive amount required")
    
    payout_id = secrets.token_hex(16)
    now = datetime.utcnow().isoformat()
    
    await db.execute("""
        INSERT INTO payouts (id, creator_id, amount, status, created_at, completed_at)
        VALUES (?, ?, ?, 'completed', ?, ?)
    """, (payout_id, creator_id, amount, now, now))
    await db.commit()
    
    return {
        "status": "completed",
        "payout_id": payout_id,
        "amount": amount,
        "stub": True,
    }


@app.get("/api/stub/balance/{creator_id}")
async def stub_creator_balance(creator_id: str):
    """Get simulated creator balance (STUB MODE)."""
    # Calculate from subscriptions to their publications
    cursor = await db.execute("""
        SELECT SUM(p.price_monthly) as total
        FROM subscriptions s
        JOIN products p ON s.product_id = p.id
        WHERE p.publication_id IN (
            SELECT id FROM products WHERE publication_id IN (
                SELECT id FROM publications WHERE owner_id = ?
            )
        )
        AND s.status = 'active'
    """, (creator_id,))
    row = await cursor.fetchone()
    
    # Get paid out amount
    cursor = await db.execute(
        "SELECT SUM(amount) as paid FROM payouts WHERE creator_id = ? AND status = 'completed'",
        (creator_id,)
    )
    paid_row = await cursor.fetchone()
    
    total_earned = row["total"] or 0
    total_paid = paid_row["paid"] or 0
    balance = total_earned - total_paid
    
    return {
        "creator_id": creator_id,
        "total_earned": total_earned,
        "total_paid": total_paid,
        "balance": balance,
        "stub": True,
    }

# Products (subscription tiers)
@app.post("/api/products")
async def create_product(product: ProductCreate):
    """Create a subscription product for a publication"""
    product_id = secrets.token_hex(16)
    now = datetime.utcnow().isoformat()
    
    stripe_product_id = None
    stripe_price_monthly_id = None
    stripe_price_yearly_id = None
    
    if STRIPE_AVAILABLE and STRIPE_SECRET_KEY.startswith("sk_"):
        try:
            # Create Stripe product
            sp = stripe.Product.create(
                name=product.name,
                metadata={"publication_id": product.publication_id}
            )
            stripe_product_id = sp.id
            
            # Create monthly price
            if product.price_monthly > 0:
                pm = stripe.Price.create(
                    product=sp.id,
                    unit_amount=product.price_monthly,
                    currency="usd",
                    recurring={"interval": "month"}
                )
                stripe_price_monthly_id = pm.id
            
            # Create yearly price
            if product.price_yearly > 0:
                py = stripe.Price.create(
                    product=sp.id,
                    unit_amount=product.price_yearly,
                    currency="usd",
                    recurring={"interval": "year"}
                )
                stripe_price_yearly_id = py.id
        except Exception as e:
            print(f"[Payments] Stripe error: {e}")
    
    await db.execute("""
        INSERT INTO products (id, publication_id, name, stripe_product_id, 
            stripe_price_monthly_id, stripe_price_yearly_id, price_monthly, price_yearly, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (product_id, product.publication_id, product.name, stripe_product_id,
          stripe_price_monthly_id, stripe_price_yearly_id, product.price_monthly, 
          product.price_yearly, now))
    await db.commit()
    
    return {
        "id": product_id,
        "stripe_product_id": stripe_product_id,
        "price_monthly_id": stripe_price_monthly_id,
        "price_yearly_id": stripe_price_yearly_id,
    }

@app.get("/api/products/{publication_id}")
async def get_products(publication_id: str):
    """Get subscription products for a publication"""
    cursor = await db.execute(
        "SELECT * FROM products WHERE publication_id = ?",
        (publication_id,)
    )
    rows = await cursor.fetchall()
    return {"items": [dict(r) for r in rows]}

# Checkout
@app.post("/api/checkout")
async def create_checkout(req: CheckoutRequest):
    """Create a checkout session for subscription"""
    # Get product
    cursor = await db.execute("SELECT * FROM products WHERE id = ?", (req.product_id,))
    product = await cursor.fetchone()
    if not product:
        raise HTTPException(404, "Product not found")
    
    price_id = product["stripe_price_monthly_id"] if req.tier == "monthly" else product["stripe_price_yearly_id"]
    
    # Get or create customer
    cursor = await db.execute("SELECT stripe_customer_id FROM customers WHERE entity_id = ?", (req.subscriber_id,))
    customer = await cursor.fetchone()
    
    if STRIPE_AVAILABLE and STRIPE_SECRET_KEY.startswith("sk_"):
        try:
            if not customer:
                # Create Stripe customer
                sc = stripe.Customer.create(metadata={"entity_id": req.subscriber_id})
                await db.execute(
                    "INSERT INTO customers (entity_id, stripe_customer_id, created_at) VALUES (?, ?, ?)",
                    (req.subscriber_id, sc.id, datetime.utcnow().isoformat())
                )
                await db.commit()
                customer_id = sc.id
            else:
                customer_id = customer["stripe_customer_id"]
            
            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[{"price": price_id, "quantity": 1}],
                mode="subscription",
                success_url=req.success_url,
                cancel_url=req.cancel_url,
                metadata={
                    "subscriber_id": req.subscriber_id,
                    "product_id": req.product_id,
                    "publication_id": product["publication_id"],
                    "tier": req.tier,
                }
            )
            
            return {"checkout_url": session.url, "session_id": session.id}
        except Exception as e:
            raise HTTPException(400, f"Stripe error: {e}")
    
    # Mock mode - create subscription directly
    sub_id = secrets.token_hex(16)
    now = datetime.utcnow().isoformat()
    await db.execute("""
        INSERT INTO subscriptions (id, subscriber_id, publication_id, product_id, tier, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'active', ?)
    """, (sub_id, req.subscriber_id, product["publication_id"], req.product_id, req.tier, now))
    await db.commit()
    
    return {"subscription_id": sub_id, "status": "active", "mock": True}

# Subscriptions
@app.get("/api/subscriptions/{subscriber_id}")
async def get_subscriptions(subscriber_id: str):
    """Get user's active subscriptions"""
    cursor = await db.execute("""
        SELECT s.*, p.name as product_name, p.price_monthly, p.price_yearly
        FROM subscriptions s
        JOIN products p ON s.product_id = p.id
        WHERE s.subscriber_id = ? AND s.status = 'active'
    """, (subscriber_id,))
    rows = await cursor.fetchall()
    return {"items": [dict(r) for r in rows]}

@app.get("/api/subscriptions/publication/{publication_id}")
async def get_publication_subscribers(publication_id: str):
    """Get subscribers for a publication"""
    cursor = await db.execute("""
        SELECT s.subscriber_id, s.tier, s.created_at, s.status
        FROM subscriptions s
        WHERE s.publication_id = ? AND s.status = 'active'
    """, (publication_id,))
    rows = await cursor.fetchall()
    return {"items": [dict(r) for r in rows], "count": len(rows)}

@app.post("/api/subscriptions/{sub_id}/cancel")
async def cancel_subscription(sub_id: str):
    """Cancel a subscription"""
    cursor = await db.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,))
    sub = await cursor.fetchone()
    if not sub:
        raise HTTPException(404, "Subscription not found")
    
    if STRIPE_AVAILABLE and sub["stripe_subscription_id"]:
        try:
            stripe.Subscription.delete(sub["stripe_subscription_id"])
        except Exception as e:
            print(f"[Payments] Stripe cancel error: {e}")
    
    now = datetime.utcnow().isoformat()
    await db.execute(
        "UPDATE subscriptions SET status = 'canceled', canceled_at = ? WHERE id = ?",
        (now, sub_id)
    )
    await db.commit()
    
    return {"status": "canceled"}

# Check access
@app.get("/api/access/{subscriber_id}/{publication_id}")
async def check_access(subscriber_id: str, publication_id: str):
    """Check if user has access to a publication"""
    cursor = await db.execute("""
        SELECT id, tier FROM subscriptions
        WHERE subscriber_id = ? AND publication_id = ? AND status = 'active'
    """, (subscriber_id, publication_id))
    sub = await cursor.fetchone()
    
    return {
        "has_access": sub is not None,
        "tier": sub["tier"] if sub else None,
        "subscription_id": sub["id"] if sub else None,
    }

# Stripe Connect (creator payouts)
@app.post("/api/connect/onboard")
async def start_connect_onboarding(req: ConnectOnboardRequest):
    """Start Stripe Connect onboarding for a creator"""
    if not STRIPE_AVAILABLE:
        return {"mock": True, "message": "Stripe not available"}
    
    try:
        # Create Connect account
        account = stripe.Account.create(
            type="express",
            email=req.email,
            metadata={"entity_id": req.entity_id}
        )
        
        await db.execute("""
            INSERT INTO connect_accounts (entity_id, stripe_account_id, created_at)
            VALUES (?, ?, ?)
        """, (req.entity_id, account.id, datetime.utcnow().isoformat()))
        await db.commit()
        
        # Create onboarding link
        link = stripe.AccountLink.create(
            account=account.id,
            refresh_url=req.refresh_url,
            return_url=req.return_url,
            type="account_onboarding"
        )
        
        return {"onboarding_url": link.url, "account_id": account.id}
    except Exception as e:
        raise HTTPException(400, f"Stripe error: {e}")

@app.get("/api/connect/{entity_id}")
async def get_connect_status(entity_id: str):
    """Get creator's Connect account status"""
    cursor = await db.execute(
        "SELECT * FROM connect_accounts WHERE entity_id = ?",
        (entity_id,)
    )
    account = await cursor.fetchone()
    if not account:
        return {"connected": False}
    
    if STRIPE_AVAILABLE:
        try:
            sa = stripe.Account.retrieve(account["stripe_account_id"])
            return {
                "connected": True,
                "account_id": sa.id,
                "charges_enabled": sa.charges_enabled,
                "payouts_enabled": sa.payouts_enabled,
                "onboarding_complete": sa.details_submitted,
            }
        except:
            pass
    
    return {
        "connected": True,
        "account_id": account["stripe_account_id"],
        "onboarding_complete": bool(account["onboarding_complete"]),
    }

# Payouts
@app.post("/api/payouts")
async def create_payout(creator_id: str, amount: int):
    """Create a payout to a creator"""
    # Get Connect account
    cursor = await db.execute(
        "SELECT stripe_account_id FROM connect_accounts WHERE entity_id = ?",
        (creator_id,)
    )
    account = await cursor.fetchone()
    if not account:
        raise HTTPException(400, "Creator not connected to Stripe")
    
    payout_id = secrets.token_hex(16)
    now = datetime.utcnow().isoformat()
    
    stripe_transfer_id = None
    if STRIPE_AVAILABLE:
        try:
            transfer = stripe.Transfer.create(
                amount=amount,
                currency="usd",
                destination=account["stripe_account_id"],
                metadata={"payout_id": payout_id, "creator_id": creator_id}
            )
            stripe_transfer_id = transfer.id
        except Exception as e:
            raise HTTPException(400, f"Transfer failed: {e}")
    
    await db.execute("""
        INSERT INTO payouts (id, creator_id, amount, stripe_transfer_id, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (payout_id, creator_id, amount, stripe_transfer_id, now))
    await db.commit()
    
    return {"payout_id": payout_id, "amount": amount, "transfer_id": stripe_transfer_id}

@app.get("/api/payouts/{creator_id}")
async def get_payouts(creator_id: str):
    """Get payout history for a creator"""
    cursor = await db.execute(
        "SELECT * FROM payouts WHERE creator_id = ? ORDER BY created_at DESC",
        (creator_id,)
    )
    rows = await cursor.fetchall()
    return {"items": [dict(r) for r in rows]}

# Webhook
@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    """Handle Stripe webhooks"""
    if not STRIPE_AVAILABLE:
        return {"status": "ok", "mock": True}
    
    payload = await request.body()
    
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(400, f"Webhook error: {e}")
    
    # Handle events
    if event.type == "checkout.session.completed":
        session = event.data.object
        meta = session.metadata
        
        # Create subscription record
        sub_id = secrets.token_hex(16)
        now = datetime.utcnow().isoformat()
        
        await db.execute("""
            INSERT INTO subscriptions (id, subscriber_id, publication_id, product_id, 
                tier, status, stripe_subscription_id, stripe_customer_id, created_at)
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)
        """, (sub_id, meta.get("subscriber_id"), meta.get("publication_id"),
              meta.get("product_id"), meta.get("tier"), session.subscription,
              session.customer, now))
        await db.commit()
    
    elif event.type == "customer.subscription.deleted":
        sub = event.data.object
        await db.execute(
            "UPDATE subscriptions SET status = 'canceled', canceled_at = ? WHERE stripe_subscription_id = ?",
            (datetime.utcnow().isoformat(), sub.id)
        )
        await db.commit()
    
    elif event.type == "invoice.payment_failed":
        invoice = event.data.object
        await db.execute(
            "UPDATE subscriptions SET status = 'past_due' WHERE stripe_subscription_id = ?",
            (invoice.subscription,)
        )
        await db.commit()
    
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "12007")))
