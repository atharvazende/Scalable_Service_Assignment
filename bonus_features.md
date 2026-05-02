# Innovative Design Patterns (+2 Bonus Credits Claim)

While many submissions stopped at basic CRUD operations, our implementation utilized several enterprise-grade distributed system patterns to solve real-world microservice challenges. Please consider the following features for the bonus credits:

### 1. Distributed Idempotency (The "Double-Charge" Problem)
In distributed systems, a network timeout might cause a client to retry an order request, potentially resulting in the customer being charged twice. 
- **Our Innovation:** We implemented an `idempotency_key` mechanism in the Order Service. If the exact same request payload is sent twice, the Order Service catches the duplicate key in `order_db` and safely ignores the second request, guaranteeing the customer is never double-charged.

### 2. Banker's Rounding for Financial Accuracy
Floating-point math in Python can lead to rounding errors, which is unacceptable in an E-Commerce Payment system.
- **Our Innovation:** Instead of standard floats, we utilized Python's `Decimal` type with `ROUND_HALF_EVEN` (Banker's Rounding) for all `order_total` and `amount` calculations to guarantee 100% financial precision.

### 3. Asynchronous TTL Reapers (Inventory Deadlock Prevention)
When a user begins an order, the Inventory Service "reserves" stock. However, if the Order Service crashes before finalizing the payment, that stock would be permanently locked in a "reserved" state, making it unavailable to other customers.
- **Our Innovation:** We wrote an asynchronous `reservation_reaper` background task inside the Inventory Service. Every 60 seconds, it scans the `inventory_db` for any orphaned reservations older than 15 minutes and automatically releases them back into `on_hand` stock.

### 4. PII Data Masking & Structured JSON Logging
Basic print statements are difficult to read in a cluster of 6 running microservices. Furthermore, logging raw customer data violates GDPR/privacy policies.
- **Our Innovation:** We built a custom `JSONLogFormatter` middleware (in `utils.py`). It forces all 6 microservices to output beautifully structured JSON logs containing a shared `correlationId` to trace requests across containers. Crucially, it intercepts the logs and automatically replaces sensitive strings (like emails or phone numbers) with `[MASKED_SENSITIVE_DATA]` before they reach the console or RabbitMQ.

### 5. Automated Data Seeding
Instead of manually typing in 1-2 rows of fake data, we built an asynchronous Python script (`seed_data.py`) using `pandas` and `asyncpg` to parse a large, realistic dataset of 120 products and bulk-insert them across the isolated databases in milliseconds.
