# Business Action Schema

## Overview

This document outlines a standardized action schema for building modular AI assistants across various business domains. Each action includes:

- **Action Name**: Normalized action identifier
- **Mandatory Params**: Required inputs for the action
- **Optional Params**: Helpful refiners or selectors

---

## 🛒 Flipkart (E-commerce)

| Action Name | Mandatory Params | Optional Params |
|-------------|------------------|-----------------|
| `search_product` | `category` | `color`, `brand`, `price_range`, `occasion`, `gender`, `rating` |
| `view_product_detail` | `product_id` | — |
| `track_order` | `order_id` | — |
| `cancel_order` | `order_id` | `cancellation_reason` |
| `return_order` | `order_id` | `return_reason`, `pickup_address` |
| `refund_status` | `order_id` | — |
| `compare_products` | `product_ids` (list) | — |
| `add_to_cart` | `product_id`, `quantity` | `variant`, `delivery_pincode` |
| `checkout` | `cart_id`, `payment_method` | `address_id`, `coupon_code` |

---

## ✈️ MakeMyTrip (Travel Booking)

| Action Name | Mandatory Params | Optional Params |
|-------------|------------------|-----------------|
| `search_flights` | `from_city`, `to_city`, `date` | `return_date`, `class`, `airlines`, `stops` |
| `book_flight` | `flight_id`, `passenger_details` | `payment_method`, `insurance_opt_in` |
| `cancel_flight` | `booking_id` | `cancellation_reason` |
| `check_flight_status` | `flight_number`, `date` | — |
| `search_hotels` | `city`, `checkin_date`, `checkout_date` | `guests`, `stars`, `amenities`, `area` |
| `book_hotel` | `hotel_id`, `dates`, `guests` | `room_type`, `payment_method` |

---

## 🏦 HDFC Bank (Banking)

| Action Name | Mandatory Params | Optional Params |
|-------------|------------------|-----------------|
| `check_balance` | `account_id` | — |
| `transfer_money` | `from_account`, `to_account`, `amount` | `remarks`, `transfer_mode` |
| `pay_credit_card` | `card_number`, `amount` | `payment_source` |
| `block_card` | `card_number` | `reason` |
| `apply_loan` | `loan_type`, `amount` | `duration`, `income_proof` |
| `transaction_history` | `account_id` | `date_range`, `filter_type` |

---

## 🏘 IQ Student Accommodation

| Action Name | Mandatory Params | Optional Params |
|-------------|------------------|-----------------|
| `search_properties` | `city` or `university` | `move_in_date`, `price_range`, `room_type`, `stay_duration`, `amenities` |
| `view_property_detail` | `property_id` | — |
| `book_room` | `room_id`, `student_info` | `payment_plan`, `booking_date` |
| `ask_question` | `property_id`, `question_text` | `room_id` |
| `track_booking_status` | `booking_id` | — |
| `cancel_booking` | `booking_id` | `reason` |

---

## 🌏 IDP (Study Abroad Counseling)

| Action Name | Mandatory Params | Optional Params |
|-------------|------------------|-----------------|
| `search_courses` | `country`, `study_level` | `subject`, `university`, `intake_month` |
| `book_counseling` | `student_name`, `email` | `preferred_time`, `counselor_id` |
| `upload_documents` | `student_id`, `document_type` | `file_name` |
| `track_application` | `application_id` | — |

---

## 👨‍💼 Naukri.com (Job Search)

| Action Name | Mandatory Params | Optional Params |
|-------------|------------------|-----------------|
| `search_jobs` | `keywords` or `role` | `location`, `experience_range`, `salary_range`, `industry` |
| `apply_job` | `job_id`, `resume` | `cover_letter` |
| `update_resume` | `user_id`, `resume_file` | — |
| `track_application` | `application_id` | — |
| `schedule_interview` | `job_id`, `candidate_id`, `date` | `interviewer` |

---

## 📈 Zerodha (Stock Trading)

| Action Name | Mandatory Params | Optional Params |
|-------------|------------------|-----------------|
| `search_stock` | `stock_name` or `symbol` | `exchange` |
| `buy_stock` | `stock_id`, `quantity` | `price_limit`, `order_type` |
| `sell_stock` | `stock_id`, `quantity` | `price_limit`, `order_type` |
| `check_portfolio` | `user_id` | — |
| `download_statement` | `account_id`, `date_range` | `format` (pdf, csv) |

---

## 🍔 Swiggy (Food Delivery)

| Action Name | Mandatory Params | Optional Params |
|-------------|------------------|-----------------|
| `search_restaurants` | `location` | `cuisine`, `rating`, `delivery_time` |
| `place_order` | `cart_items`, `address` | `coupon`, `payment_method` |
| `track_order` | `order_id` | — |
| `cancel_order` | `order_id` | `reason` |
| `reorder` | `previous_order_id` | — |
| `rate_order` | `order_id`, `rating` | `feedback_text` |

---

## 🧠 Reusable Agent Architecture

### Agent Type Mapping

| Agent Type | Covers Actions | Description |
|------------|----------------|-------------|
| **`product_search_agent`** | `search_*`, `compare_products`, `filter_*` | Handles discovery and comparison functionality across domains |
| **`product_detail_agent`** | `view_*_detail`, `download_statement`, `track_*` | Manages detailed information retrieval and status tracking |
| **`process_agent`** | `place_order`, `cancel_*`, `apply_*`, `book_*`, `upload_*`, `refund_*` | Executes transactional operations and workflow processes |

### Benefits of Standardization

1. **Consistency**: Uniform action naming across different business domains
2. **Reusability**: Agents can be shared and adapted across multiple businesses
3. **Maintainability**: Single codebase for common functionality patterns
4. **Scalability**: Easy to add new businesses following the same schema
5. **Testing**: Standardized testing approaches across all domains

---

## Implementation Notes

### JSON Schema Example

```json
{
  "action": "search_product",
  "business_domain": "ecommerce",
  "mandatory_params": {
    "category": "electronics"
  },
  "optional_params": {
    "brand": "samsung",
    "price_range": "10000-50000",
    "rating": "4+"
  }
}
```

### Future Enhancements

- **Custom Intents**: Add support for domain-specific intents (small talk, help, complaints)
- **Validation Rules**: Parameter validation and type checking
- **Error Handling**: Standardized error responses across all actions
- **Logging**: Consistent logging format for all business operations
- **Rate Limiting**: Unified rate limiting across different business APIs

---

## Contributing

When adding new business domains:

1. Follow the same action naming convention
2. Clearly define mandatory vs optional parameters
3. Map actions to appropriate reusable agent types
4. Update the agent architecture section accordingly
5. Add comprehensive examples and documentation 