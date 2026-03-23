# Data Model Documentation

## Source Dataset

19 SAP O2C tables delivered as JSONL files:

### Core Flow Tables
| Table | Grain | Rows | Primary Key |
|-------|-------|------|-------------|
| sales_order_headers | 1 per order | 100 | salesOrder |
| sales_order_items | 1 per line item | 167 | (salesOrder, salesOrderItem) |
| sales_order_schedule_lines | 1 per schedule line | 179 | (salesOrder, salesOrderItem, scheduleLine) |
| outbound_delivery_headers | 1 per delivery | 86 | deliveryDocument |
| outbound_delivery_items | 1 per delivery line | 137 | (deliveryDocument, deliveryDocumentItem) |
| billing_document_headers | 1 per invoice | 163 | billingDocument |
| billing_document_items | 1 per invoice line | 245 | (billingDocument, billingDocumentItem) |
| billing_document_cancellations | 1 per cancelled invoice | 80 | billingDocument |
| journal_entry_items_accounts_receivable | 1 per AR posting | 123 | (companyCode, fiscalYear, accountingDocument, accountingDocumentItem) |
| payments_accounts_receivable | 1 per cleared AR posting | 120 | same as above |

### Master Data Tables
| Table | Rows | Primary Key |
|-------|------|-------------|
| business_partners | 8 | businessPartner |
| business_partner_addresses | 8 | (businessPartner, addressId) |
| customer_company_assignments | 8 | (customer, companyCode) |
| customer_sales_area_assignments | 28 | (customer, salesOrganization, distributionChannel, division) |
| plants | 44 | plant |
| products | 69 | product |
| product_descriptions | 69 | (product, language) |
| product_plants | 3,036 | (product, plant) |
| product_storage_locations | 16,723 | (product, plant, storageLocation) |

## Validated Join Map

```
Customer (8) ──PLACED_ORDER──► Sales Order (100)
                                    │
                         SO Item (167)
                                    │ 1:1 (137 matched, 30 unmatched)
                                    ▼
                         Delivery Item (137)
                                    │ 1:2 (124 matched, cancelled+replacement)
                                    ▼
                         Billing Item (245)
                                    │ 163 billing docs → 123 journal entries
                                    ▼
                         Journal Entry (123)
                                    │ 120 cleared, 3 open
                                    ▼
                         Payment (120)
```

### Join Coverage

| Link | Left | Right | Matched | Cardinality |
|------|------|-------|---------|-------------|
| SO → Delivery | 167 items | 137 items | 137 (82%) | Strict 1:1 |
| Delivery → Billing | 137 items | 245 items | 124 (90%) | 1:2 (original + replacement) |
| Billing → Journal | 163 docs | 123 entries | 123 (75%) | 1:1 |
| Journal → Payment | 123 entries | 120 rows | 120 (98%) | Identity (subset) |
| Material → Product | 69 | 69 | 69 (100%) | 1:1 |
| Customer → BP | 8 | 8 | 8 (100%) | 1:1 |

### Key Finding: Billing Cancellation Pattern

80 of 83 original invoices (type F2) were cancelled. Each was replaced by an S1 document. The system:
- Pairs cancelled → replacement via shared delivery item reference
- Always filters to `is_cancelled = false` for flow analysis
- Retains cancelled documents for graph visualization (dashed edges)

### Key Finding: Payment Table Semantics

`payments_accounts_receivable` is NOT a separate table — it's a filtered view of `journal_entry_items_accounts_receivable` containing only rows where `clearingAccountingDocument IS NOT NULL`. The 3 JE rows without clearing are open receivables.

## Graph Model

### Nodes (669 total)
| Type | Count | ID Pattern |
|------|-------|-----------|
| customer | 8 | customer:{id} |
| sales_order | 100 | sales_order:{id} |
| delivery | 86 | delivery:{id} |
| billing | 163 | billing:{id} |
| journal | 123 | journal:{id} |
| payment | 76 | payment:{id} |
| product | 69 | product:{id} |
| plant | 44 | plant:{id} |

### Edges (859 total)
| Type | Count | Direction |
|------|-------|-----------|
| PLACED_ORDER | 100 | customer → sales_order |
| CONTAINS_PRODUCT | 167 | sales_order → product |
| FULFILLED_BY | 86 | sales_order → delivery |
| SHIPS_FROM | 100 | sales_order → plant |
| BILLED_AS | 83 | delivery → billing (active only) |
| CANCELLED_BY | 80 | billing → billing |
| POSTED_AS | 123 | billing → journal |
| CLEARED_BY | 120 | journal → payment |
