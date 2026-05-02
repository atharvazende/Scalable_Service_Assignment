# Service Boundary & Workflow Sequence Diagram

This sequence diagram proves that we have implemented a **true microservices workflow** rather than just disconnected CRUD endpoints. 

It demonstrates the Orchestrator pattern where the Order Service enforces strict business rules (e.g., verifying product exists, reserving stock, charging the payment before shipping) across multiple isolated boundaries.

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant OS as Order Service
    participant CS as Catalog Service
    participant IS as Inventory Service
    participant PS as Payment Service
    participant SS as Shipping Service
    participant MQ as RabbitMQ
    participant NS as Notification Service

    Client->>OS: POST /v1/orders (items, idempotency_key)
    activate OS
    
    %% Rule: Validate product exists and get price
    OS->>CS: GET /v1/products/{id}
    activate CS
    CS-->>OS: 200 OK (Product Info & Price)
    deactivate CS
    
    %% Rule: Validate stock limits and constraints
    OS->>IS: POST /v1/inventory/reserve (order_id, items)
    activate IS
    alt Insufficient Stock
        IS-->>OS: 400 Bad Request
        OS-->>Client: 400 Error (Inventory failed)
    else Stock Available
        IS-->>OS: 200 OK (Stock Reserved)
    end
    deactivate IS
    
    %% Rule: Enforce workflow (Payment BEFORE Shipment)
    OS->>PS: POST /v1/payments/charge (order_id, amount)
    activate PS
    alt Payment Fails
        PS-->>OS: 400 Bad Request
        OS-xIS: POST /v1/inventory/release (rollback stock)
        OS-->>Client: 400 Error (Payment Failed)
    else Payment Succeeds
        PS-->>OS: 200 OK (Payment Processed)
    end
    deactivate PS
    
    %% Rule: Trigger Fulfillment
    OS->>SS: POST /v1/shipments (order_id)
    activate SS
    SS-->>OS: 200 OK (Shipment Initiated)
    deactivate SS
    
    %% Rule: Asynchronous Event Publishing
    OS-)MQ: Publish "ORDER_CONFIRMED" event
    
    OS-->>Client: 201 Created (Order Confirmed)
    deactivate OS
    
    %% Background consumption
    MQ-)NS: Deliver "ORDER_CONFIRMED"
    activate NS
    NS->>NS: Mask Sensitive PII Data
    NS->>NS: Log Event to notification_db
    deactivate NS
```
