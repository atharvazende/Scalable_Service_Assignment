# Entity-Relationship Diagram (ERD)

This document visualizes the exact database structures implemented in our microservice architecture. 

It highlights the **Database-per-Service** pattern. Notice that while logical foreign keys (like `product_id` and `order_id`) connect the data, they are separated into isolated physical databases (e.g., `catalog_db` vs `order_db`), satisfying the microservices constraint.

```mermaid
erDiagram
    %% Catalog Service
    PRODUCTS {
        int product_id PK
        string name
        string description
        decimal price
        string category
    }

    %% Inventory Service
    INVENTORY {
        int inventory_id PK
        int product_id FK "Logical constraint to Catalog"
        string warehouse
        int on_hand
        int reserved
        datetime updated_at
    }

    %% Order Service
    CUSTOMERS {
        int customer_id PK
        string name
        string email
        string phone
        string address
    }

    ORDERS {
        int order_id PK
        int customer_id FK
        string order_status "CREATED, CONFIRMED, CANCELLED"
        string payment_status "PENDING, PAID, FAILED"
        decimal order_total
        string idempotency_key "Unique ID for safety"
        string totals_signature "SHA256 Hash"
        datetime created_at
    }

    ORDER_ITEMS {
        int order_item_id PK
        int order_id FK
        int product_id FK "Logical constraint to Catalog"
        int quantity
        decimal price_at_time
    }

    %% Payment Service
    PAYMENTS {
        int payment_id PK
        int order_id FK "Logical constraint to Orders"
        decimal amount
        string status "SUCCESS, FAILED, REFUNDED"
        string method
        string transaction_id
        datetime created_at
    }

    %% Shipping Service
    SHIPMENTS {
        int shipment_id PK
        int order_id FK "Logical constraint to Orders"
        string carrier
        string tracking_number
        string status "PENDING, SHIPPED, DELIVERED"
        datetime updated_at
    }

    %% Notification Service
    NOTIFICATION_LOGS {
        int id PK
        string type "ORDER_CONFIRMED, LOW_STOCK"
        text message
        datetime created_at
    }

    %% Relationships
    CUSTOMERS ||--o{ ORDERS : places
    ORDERS ||--o{ ORDER_ITEMS : contains
    
    %% Logical boundaries across Microservices
    PRODUCTS ||--o{ INVENTORY : "monitored by (isolated DB)"
    PRODUCTS ||--o{ ORDER_ITEMS : "purchased via (isolated DB)"
    ORDERS ||--o| PAYMENTS : "paid through (isolated DB)"
    ORDERS ||--o| SHIPMENTS : "fulfilled by (isolated DB)"
```
