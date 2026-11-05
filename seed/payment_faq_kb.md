# Razorpay Payment Gateway - Knowledge Base

> Source: Razorpay Payment Gateway FAQ
> Purpose: Voice agent knowledge base / semantic retrieval source
> Last updated: 2026-11-04

---

## Category: Payments & Checkout

### Q: How does a customer make payments using the Razorpay Payment Gateway?
**Keywords:** payment, checkout, how to pay, customer payment, Razorpay checkout

**Answer:** Customers can make payments through Razorpay Checkout. Please note that any transaction made is a real transaction. The money will be deducted from the customer's account when the transaction is completed, and will be auto-refunded to the account in 4 to 5 days if it is a test.

---

### Q: Why am I facing issues with the checkout?
**Keywords:** checkout issue, checkout not loading, payment failed, late auth, debited but failed

**Answer:** There are a few possible reasons for checkout issues:

1. **Checkout not loading:** Check for any incorrect parameters in the payload and ensure the API key you are using is valid, non-expired, and the most recently generated one.
2. **Delay in payment processing:** This is often referred to as "Late Auth" and is a common issue within the payments ecosystem.
3. **Payment failed but customer was debited:** If the payment is debited from the customer but does not reflect on the dashboard, the amount will be refunded within 3 to 7 business days.

---

### Q: What is Late Authorisation?
**Keywords:** late authorisation, late auth, payment interruption, network issues, bank delay

**Answer:** Late authorisation is a situation that arises when a payment is interrupted by external factors such as network issues or technical errors at the customer's or bank's end. In such cases, funds may or may not get debited from the customer's bank account, and Razorpay does not receive a payment status from the bank.

---

### Q: A payment is marked as 'failed' on my Dashboard but money is debited from the customer's account. What should I do?
**Keywords:** failed payment, money debited, callback, refund, customer debited

**Answer:** A payment is marked as 'failed' when Razorpay does not receive a successful callback message from the issuing bank. If the customer's account is debited and no successful callback is received, the amount will be auto-refunded by the customer's issuing bank in 7 to 10 working days.

Razorpay verifies the status with the bank at regular intervals. If there is a change in status, the payment moves to the authorized state, and a notification is sent to you and the customer. In such scenarios, you can either:

- **Provide services:** Capture the payment and provide the service or good as promised to the customer.
- **Refund the transaction:** If you cannot provide the service as per agreed terms such as time of delivery, cost of purchase, or inventory issues, refund the payment to the customer.

---

## Category: Pricing, Fees & GST

### Q: How much does Razorpay charge per transaction?
**Keywords:** pricing, transaction fee, charges, cost, standard plan, enterprise plan

**Answer:** Under the standard plan designed for small and medium enterprises, Razorpay charges 2 percent per transaction. Razorpay also offers an enterprise plan designed for large volumes, which gives you the best prices possible for your business.

---

### Q: Is GST mandatory to accept payments?
**Keywords:** GST mandatory, GST requirement, TDS, tax, annual turnover

**Answer:** No, GST is not mandatory if your business does not have an annual turnover of over 20 lakh rupees. However, if you do not provide your GST details, you will not be able to claim TDS at the time of filing your tax returns.

---

### Q: What is the applicable GST and how is it charged?
**Keywords:** GST rate, GST charge, 18 percent GST, domestic card, invoice

**Answer:** 18 percent GST is charged on the fee deducted for all payment methods, except for domestic card transactions of an amount less than or equal to 2000 rupees. You can check the Monthly Invoice Report from the Reports section of your Dashboard to understand the GST charged.

---

## Category: Testing & Integration

### Q: How can we test our website or mobile app integration with Razorpay Payment Gateway?
**Keywords:** test integration, sandbox, test mode, mock bank, simulated transactions

**Answer:** Razorpay offers a sandbox environment where you can test integrations before going live. To test your integration, generate test API Keys in test mode and implement them in your code. Test mode features a mock bank page with Success and Failure buttons to replicate the live payment experience. No money is deducted as these are simulated transactions.

---

### Q: Do you have any test cards to check website or mobile app integration?
**Keywords:** test cards, test card details, Mastercard, Visa, AMEX, subscription test, international test

**Answer:** Yes, Razorpay provides test card details to inspect the payment flow. You can use any CVV and any future date as the expiry date. The test cards include:

- **Mastercard:** 5104015555555558 or 5104060000000008
- **Visa:** 4386289407660153
- **Subscription:** 5104015555555558
- **International Mastercard:** 5555555555554444 or 5105105105105100
- **International Visa:** 401288888881881 or 4000184186218826
- **American Express:** 379862000000006

---

## Category: Payment Capture

### Q: What is Standard Capture?
**Keywords:** standard capture, authorisation, delayed capture, capture request

**Answer:** Standard capture is an authorisation followed by a delayed capture of the payment. When a customer makes a payment, the amount is deducted from the customer's bank account by Razorpay. The authorised amount is settled to your account only after you initiate a capture request.

---

### Q: What is auto-capture and how do I enable it for payments?
**Keywords:** auto-capture, automatic capture, authorized state, payment settings, enable auto capture

**Answer:** When a customer makes a payment, it goes to the authorized state. You need to capture the payments to get them settled to your account. Auto-capture enables payments to be captured automatically as soon as they are authorized. Payments that are authorized but not captured are automatically refunded to customers in 5 days. To set up automatic capture, configure the Payment Capture settings on your Dashboard.

---

### Q: How do I manually capture a payment?
**Keywords:** manual capture, capture payment, dashboard capture, API capture

**Answer:** You can manually capture payments either from the Dashboard or by using APIs. You need to capture the payments to get them settled to your account. Payments that are authorized but not captured are automatically refunded to customers in 5 days.

---

## Category: International Payments

### Q: Can I accept International Payments through Razorpay?
**Keywords:** international payments, foreign payments, cross border, global payments

**Answer:** Yes, you can accept international payments using the Razorpay Payment Gateway.

---

## Category: Settlements

### Q: How are payments made by my customers settled to my account? Is any action required from my end?
**Keywords:** settlement, settle to account, settlement cycle, auto settlement, payout

**Answer:** No action is required from your end for settlements. The captured payments are settled automatically to your account as per your settlement cycle.

---

## Category: Security & Compliance

### Q: Is Razorpay PCI-DSS compliant?
**Keywords:** PCI DSS, compliance, security, PCI compliant, data security

**Answer:** Yes, Razorpay is PCI-DSS compliant.

---

## Voice Agent Guidance Notes

**Tone:** Professional, friendly, clear, and concise. Avoid technical jargon when speaking to end customers unless the user is a developer.

**Formatting for voice output:**
- Numbers should be spoken naturally (for example, "two percent" instead of "2%")
- Currency should be read as "rupees" after the amount
- Card numbers should NOT be read out character by character unless the user is clearly testing integration
- Use natural pauses between list items

**Fallback behavior:**
- If a question is outside this knowledge base, respond with: "I don't have that specific information. I can connect you with a Razorpay support representative who can help further."
- For account-specific questions (settlement delays, specific transaction status), direct the user to the Dashboard or support.

**Key disambiguation:**
- "Capture" refers to payment capture, not screen capture
- "Settlement" refers to funds being transferred to the merchant account
- "Authorized" means the payment is approved but not yet captured
- "Late Auth" is shorthand for Late Authorisation

---

## Semantic Tags Index

- **Payment flow:** checkout, capture, authorisation, settlement, refund
- **Billing:** pricing, GST, TDS, fees, invoice
- **Developer:** test cards, sandbox, API keys, integration, test mode
- **Troubleshooting:** failed payment, late auth, checkout issues, debited but failed
- **Compliance:** PCI-DSS, GST, security
- **Scope:** international payments, domestic cards, subscriptions
