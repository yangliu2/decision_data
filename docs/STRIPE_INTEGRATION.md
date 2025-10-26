# Stripe Payment Integration for Panzoto

**Date:** October 26, 2025
**Status:** IMPLEMENTATION IN PROGRESS

## Overview

This document contains the complete implementation guide for integrating Stripe payment processing into Panzoto. Users will be able to purchase credits ($5, $10, $20) via Stripe web checkout.

---

## Prerequisites

- [x] Stripe account created
- [x] API keys obtained (STRIPE_PUBLISHABLE_KEY, STRIPE_SECRET_KEY)
- [x] Stripe library installed (`poetry add stripe`)
- [x] Cost tracking service updated with `add_user_credit()` method
- [x] Backend config updated with Stripe keys

---

## Implementation Steps

### Step 1: Add Pydantic Models

Add these models to `decision_data/data_structure/models.py`:

```python
from pydantic import BaseModel

class CreateCheckoutSessionRequest(BaseModel):
    """Request to create a Stripe checkout session"""
    amount: float  # Amount in USD (e.g., 5.00, 10.00, 20.00)

class CreateCheckoutSessionResponse(BaseModel):
    """Response with Stripe checkout URL"""
    checkout_url: str
    session_id: str
```

**Location to add:** After the existing models (around line 200+)

---

### Step 2: Add Stripe Endpoints to FastAPI

Add these endpoints to `decision_data/api/backend/api.py`:

```python
# Add these imports at the top
import stripe
from decision_data.data_structure.models import (
    CreateCheckoutSessionRequest,
    CreateCheckoutSessionResponse
)

# Configure Stripe (add after app initialization, around line 30)
stripe.api_key = backend_config.STRIPE_SECRET_KEY

# Add these endpoints (add before the startup event, around line 900)

@app.post("/api/create-checkout-session")
async def create_checkout_session(
    request: CreateCheckoutSessionRequest,
    current_user: Dict = Depends(get_current_user)
) -> CreateCheckoutSessionResponse:
    """Create a Stripe Checkout session for credit purchase

    Args:
        request: Amount to purchase ($5, $10, or $20)
        current_user: Authenticated user from JWT token

    Returns:
        Checkout URL and session ID
    """
    user_id = current_user["user_id"]
    amount = request.amount

    # Validate amount (only allow predefined credit packages)
    valid_amounts = [5.00, 10.00, 20.00]
    if amount not in valid_amounts:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid amount. Must be one of: {valid_amounts}"
        )

    try:
        logger.info(f"[STRIPE] Creating checkout session for user {user_id}, amount ${amount}")

        # Create Stripe checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': int(amount * 100),  # Convert to cents
                    'product_data': {
                        'name': f'Panzoto Credits - ${amount:.2f}',
                        'description': f'Audio transcription credits (${amount:.2f})',
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=backend_config.FRONTEND_URL + '/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=backend_config.FRONTEND_URL + '/cancelled',
            client_reference_id=user_id,  # Track which user is paying
            metadata={
                'user_id': user_id,
                'credit_amount': str(amount)
            }
        )

        logger.info(f"[STRIPE] Created session {checkout_session.id} for user {user_id}")

        return CreateCheckoutSessionResponse(
            checkout_url=checkout_session.url,
            session_id=checkout_session.id
        )

    except stripe.error.StripeError as e:
        logger.error(f"[STRIPE] Error creating checkout session: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[STRIPE] Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Payment processing error")


@app.post("/api/stripe-webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events (payment success, failure, etc.)

    This endpoint is called by Stripe when payment events occur.
    It verifies the webhook signature and processes successful payments
    by adding credits to the user's account.
    """
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, backend_config.STRIPE_WEBHOOK_SECRET
        )
        logger.info(f"[STRIPE] Webhook event received: {event['type']}")

    except ValueError as e:
        logger.error(f"[STRIPE] Invalid payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"[STRIPE] Invalid signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle successful payment
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']

        user_id = session['metadata']['user_id']
        credit_amount = float(session['metadata']['credit_amount'])
        payment_intent = session.get('payment_intent')
        amount_paid = session['amount_total'] / 100  # Convert from cents to dollars

        logger.info(
            f"[STRIPE] Payment successful for user {user_id}: "
            f"${amount_paid:.2f} (payment_intent: {payment_intent})"
        )

        # Add credits to user account
        try:
            cost_service = get_cost_tracking_service()
            success = cost_service.add_user_credit(user_id, credit_amount)

            if success:
                logger.info(
                    f"[STRIPE] Successfully added ${credit_amount} credits "
                    f"to user {user_id}"
                )
            else:
                logger.error(
                    f"[STRIPE] Failed to add credits to user {user_id}"
                )

        except Exception as e:
            logger.error(
                f"[STRIPE] Error adding credits to user {user_id}: {e}",
                exc_info=True
            )

    # Handle payment failure
    elif event['type'] == 'checkout.session.expired':
        session = event['data']['object']
        user_id = session['metadata']['user_id']
        logger.warning(f"[STRIPE] Checkout session expired for user {user_id}")

    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        logger.warning(f"[STRIPE] Payment failed: {payment_intent.get('id')}")

    return {"status": "success"}
```

---

### Step 3: Configure Stripe Webhook

**After deploying, you need to set up the webhook in Stripe Dashboard:**

1. Go to https://dashboard.stripe.com/webhooks
2. Click "Add endpoint"
3. Enter webhook URL: `http://206.189.185.129:8000/api/stripe-webhook`
4. Select events to listen for:
   - `checkout.session.completed`
   - `checkout.session.expired`
   - `payment_intent.payment_failed`
5. Copy the "Signing secret" (starts with `whsec_`)
6. Add to `.env` file:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxx
   ```

---

### Step 4: Update Android App

#### 4.1 Add to `AuthModels.kt`

```kotlin
// Add to Panzoto/app/src/main/java/com/example/panzoto/data/AuthModels.kt

@Serializable
data class CreateCheckoutSessionRequest(
    val amount: Double
)

@Serializable
data class CreateCheckoutSessionResponse(
    val checkout_url: String,
    val session_id: String
)
```

#### 4.2 Update `AuthService.kt`

```kotlin
// Add to Panzoto/app/src/main/java/com/example/panzoto/service/AuthService.kt

suspend fun createCheckoutSession(amount: Double): Result<CreateCheckoutSessionResponse> {
    return withContext(Dispatchers.IO) {
        try {
            val response: HttpResponse = client.post("$BASE_URL/create-checkout-session") {
                headers {
                    append("Authorization", "Bearer ${getAuthToken()}")
                }
                contentType(ContentType.Application.Json)
                setBody(CreateCheckoutSessionRequest(amount = amount))
            }

            if (response.status.isSuccess()) {
                val checkoutResponse = response.body<CreateCheckoutSessionResponse>()
                Result.success(checkoutResponse)
            } else {
                val errorBody = response.bodyAsText()
                Result.failure(Exception("Failed to create checkout: $errorBody"))
            }
        } catch (e: Exception) {
            Log.e("AuthService", "Error creating checkout session", e)
            Result.failure(e)
        }
    }
}

private suspend fun getAuthToken(): String {
    return dataStore.data.map { prefs ->
        prefs[PreferencesKeys.TOKEN_KEY] ?: ""
    }.first()
}
```

#### 4.3 Update `GetCreditsDialog` in `HomeScreen.kt`

```kotlin
// Replace the GetCreditsDialog in HomeScreen.kt with this updated version

@Composable
fun GetCreditsDialog(
    onDismiss: () -> Unit,
    onPurchaseCredit: (Double) -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Text(
                text = "Get Credits",
                style = MaterialTheme.typography.headlineSmall,
                color = MaterialTheme.colorScheme.primary
            )
        },
        text = {
            Column {
                Text(
                    text = "Purchase recording credits to continue using Panzoto.",
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(bottom = 16.dp)
                )

                // Credit packages
                CreditPackageButton(
                    amount = 5.00,
                    description = "$5 - Basic Package",
                    onClick = { onPurchaseCredit(5.00) }
                )
                Spacer(modifier = Modifier.height(8.dp))

                CreditPackageButton(
                    amount = 10.00,
                    description = "$10 - Popular Package",
                    onClick = { onPurchaseCredit(10.00) },
                    isPopular = true
                )
                Spacer(modifier = Modifier.height(8.dp))

                CreditPackageButton(
                    amount = 20.00,
                    description = "$20 - Premium Package",
                    onClick = { onPurchaseCredit(20.00) }
                )

                Spacer(modifier = Modifier.height(16.dp))

                Text(
                    text = "Pricing: OpenAI Whisper $0.006/min, AWS S3 $0.023/GB",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel")
            }
        },
        containerColor = MaterialTheme.colorScheme.surface
    )
}

@Composable
fun CreditPackageButton(
    amount: Double,
    description: String,
    onClick: () -> Unit,
    isPopular: Boolean = false
) {
    Button(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        colors = if (isPopular) {
            ButtonDefaults.buttonColors(
                containerColor = MaterialTheme.colorScheme.primary
            )
        } else {
            ButtonDefaults.buttonColors()
        }
    ) {
        Text(description)
    }
}
```

#### 4.4 Update `HomeScreen` to handle purchases

```kotlin
// Update the HomeScreen composable in HomeScreen.kt

@Composable
fun HomeScreen(
    userSession: UserSession,
    onStartRecording: () -> Unit,
    onStopRecording: () -> Unit,
    recordingViewModel: RecordingViewModel? = null,
    creditBalance: Double = 1.0
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val authService = remember { AuthService(context) }

    // ... existing code ...

    // Update the showGetCreditsDialog handling
    if (showGetCreditsDialog) {
        GetCreditsDialog(
            onDismiss = { showGetCreditsDialog = false },
            onPurchaseCredit = { amount ->
                scope.launch(Dispatchers.IO) {
                    authService.createCheckoutSession(amount).fold(
                        onSuccess = { checkoutResponse ->
                            // Open browser with Stripe Checkout URL
                            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(checkoutResponse.checkout_url))
                            withContext(Dispatchers.Main) {
                                context.startActivity(intent)
                                showGetCreditsDialog = false
                            }
                        },
                        onFailure = { error ->
                            Log.e("HomeScreen", "Failed to create checkout: $error")
                        }
                    )
                }
            }
        )
    }
}
```

---

## Testing

### Test with Stripe Test Mode

Stripe provides test card numbers:

**Successful payment:**
- Card: `4242 4242 4242 4242`
- Expiry: Any future date (e.g., 12/34)
- CVC: Any 3 digits (e.g., 123)
- ZIP: Any 5 digits (e.g., 12345)

**Declined payment:**
- Card: `4000 0000 0000 0002`

### Testing Steps

1. **Test checkout session creation:**
   ```bash
   curl -X POST http://localhost:8000/api/create-checkout-session \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"amount": 5.00}'
   ```

2. **Test webhook locally (use Stripe CLI):**
   ```bash
   stripe listen --forward-to localhost:8000/api/stripe-webhook
   stripe trigger checkout.session.completed
   ```

3. **Test Android app:**
   - Tap "Start Recording" when balance is $0
   - Dialog appears with credit packages
   - Tap "$10 - Popular Package"
   - Browser opens with Stripe Checkout
   - Enter test card: 4242 4242 4242 4242
   - Complete payment
   - Return to app
   - Check credit balance (should show $11.00)

---

## Production Deployment

### 1. Switch to Production Mode

In Stripe Dashboard:
- Toggle from "Test mode" to "Live mode"
- Get new production API keys
- Update `.env` with production keys
- Update webhook URL to production server

### 2. Deploy to Server

```bash
# Commit changes
git add .
git commit -m "feat: add Stripe payment integration"
git push origin main

# Server will auto-deploy via GitHub Actions
# Or manually:
ssh root@206.189.185.129 "cd /root/decision_data && git pull && poetry install"

# Restart server
ssh root@206.189.185.129 "pkill -9 -f uvicorn"
ssh root@206.189.185.129 "cd /root/decision_data && /root/.cache/pypoetry/virtualenvs/decision-data-e8iAcpEn-py3.12/bin/uvicorn decision_data.api.backend.api:app --host 0.0.0.0 --port 8000 > /var/log/api.log 2>&1 &"
```

### 3. Set up Production Webhook

- Create webhook in Stripe Dashboard (Live mode)
- URL: `http://206.189.185.129:8000/api/stripe-webhook`
- Add `STRIPE_WEBHOOK_SECRET` to server `.env`
- Restart server

---

## Security Considerations

1. **Webhook Verification:** Always verify Stripe webhook signatures
2. **Amount Validation:** Only allow predefined amounts ($5, $10, $20)
3. **User Association:** Use JWT tokens to associate payments with users
4. **Idempotency:** Stripe automatically handles duplicate webhooks
5. **Logging:** Log all payment events for audit trail

---

## Troubleshooting

### Webhook not receiving events
- Check webhook URL is publicly accessible
- Verify webhook secret matches Stripe Dashboard
- Check server logs: `tail -f /var/log/api.log | grep STRIPE`

### Credits not added after payment
- Check webhook logs in Stripe Dashboard
- Verify `add_user_credit()` is working: check DynamoDB
- Ensure user_id in metadata matches actual user

### Checkout session creation fails
- Verify Stripe API keys are correct
- Check amount is valid ($5, $10, or $20)
- Ensure user is authenticated (JWT token valid)

---

## Cost Analysis

**Stripe Fees:**
- Per transaction: 2.9% + $0.30

**Actual cost to you:**
- $5.00 purchase → You receive $4.55 (9% fee)
- $10.00 purchase → You receive $9.41 (5.9% fee)
- $20.00 purchase → You receive $19.11 (4.4% fee)

**Recommendation:** Encourage larger purchases to minimize percentage fees.

---

## Next Steps

1. Implement email notifications for successful payments
2. Add purchase history screen in Android app
3. Consider subscription model for heavy users
4. Add refund functionality
5. Implement credit expiration policy

---

**Last Updated:** October 26, 2025
**Author:** Claude Code
**Status:** Ready for implementation
