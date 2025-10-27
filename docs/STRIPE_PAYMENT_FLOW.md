# Stripe Payment Flow - Complete Implementation

**Status:** ✅ TEST MODE WORKING | ⏳ Production requires HTTPS

**Date:** October 26, 2025

---

## Overview

Complete Stripe payment integration for Panzoto Android app with automatic app return after payment completion. Users can purchase credits via Stripe Checkout with seamless UX.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Android App (Panzoto)                   │
│  - PaymentScreen: Select credit package ($5, $10, $20)      │
│  - Deep link handler: Auto-return from Stripe               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓ POST /api/create-checkout-session
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Backend (DigitalOcean)                 │
│  - Create Stripe checkout session                           │
│  - Return checkout URL to app                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓ Open browser with Stripe URL
┌─────────────────────────────────────────────────────────────┐
│                    Stripe Checkout                          │
│  - User enters payment details                              │
│  - Payment processed securely by Stripe                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ↓              ↓              ↓
   Deep Link      Webhook        Redirect
panzoto://payment   (async)     (to success)
        │              │              │
        └──────────────┴──────────────┘
                       │
                       ↓ App reopens & shows success
┌─────────────────────────────────────────────────────────────┐
│                     Android App                             │
│  - Toast: "Payment successful!"                             │
│  - Auto-navigate to Cost screen                             │
│  - Show updated credit balance                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Payment Flow Step-by-Step

### 1. User Initiates Payment

**Location:** Cost Screen or Payment Screen

```kotlin
// User taps "Add Credits" button (bright orange)
Button(onClick = onNavigateToPayment) {
    Icon(imageVector = Icons.Default.CreditCard)
    Text("Add Credits")
}
```

**User Experience:**
- Cost Screen has prominent orange "Add Credits" button
- Navigation drawer has "Get Credits" menu item
- Payment screen shows three packages: $5, $10, $20

### 2. Create Stripe Checkout Session

**Android Request:**
```kotlin
// PaymentScreen.kt
authService.createCheckoutSession(amount = 5.00)
```

**Backend Endpoint:** `POST /api/create-checkout-session`
```python
# decision_data/api/backend/api.py
@app.post("/api/create-checkout-session")
async def create_stripe_checkout_session(
    request: CreateCheckoutSessionRequest,
    user: dict = Depends(get_current_user)
):
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {'name': 'Panzoto Credits'},
                'unit_amount': int(request.amount * 100)
            },
            'quantity': 1
        }],
        mode='payment',
        success_url='panzoto://payment/success?session_id={CHECKOUT_SESSION_ID}',
        cancel_url='panzoto://payment/cancel',
        client_reference_id=user_id,
        metadata={'user_id': user_id, 'amount': request.amount}
    )
    return {'checkout_url': session.url, 'session_id': session.id}
```

### 3. Open Stripe Checkout in Browser

**Android:**
```kotlin
val intent = Intent(Intent.ACTION_VIEW, Uri.parse(checkoutResponse.checkout_url))
context.startActivity(intent)
```

**User Experience:**
- Browser opens with Stripe Checkout page
- User enters card details (test mode: 4242 4242 4242 4242)
- Stripe processes payment securely

### 4. Payment Completion

**Two parallel processes:**

#### A. Webhook (Async - Credits Account)
```python
@app.post("/api/stripe-webhook")
async def stripe_webhook(request: Request):
    event = stripe.Webhook.construct_event(
        payload=await request.body(),
        sig_header=request.headers.get('stripe-signature'),
        secret=webhook_secret
    )

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session['metadata']['user_id']
        amount = float(session['metadata']['amount'])

        # Add credits to user account
        cost_service.add_user_credit(user_id, amount)
```

#### B. Deep Link (Immediate - UX Feedback)
```
Stripe redirects to: panzoto://payment/success?session_id=XXX
```

### 5. App Reopens Automatically

**MainActivity.kt - Deep Link Handler:**
```kotlin
override fun onNewIntent(intent: Intent) {
    super.onNewIntent(intent)
    handleDeepLink(intent)
}

private fun handleDeepLink(intent: Intent?) {
    val data: Uri? = intent?.data
    if (data?.scheme == "panzoto" && data.host == "payment") {
        when (data.path) {
            "/success" -> {
                Toast.makeText(this, "Payment successful! Your credits have been added.", LENGTH_LONG).show()
                pendingPaymentSuccess = true  // Triggers navigation
            }
            "/cancel" -> {
                Toast.makeText(this, "Payment cancelled", LENGTH_SHORT).show()
            }
        }
    }
}
```

**AndroidManifest.xml - Deep Link Configuration:**
```xml
<activity
    android:name=".MainActivity"
    android:launchMode="singleTop">

    <intent-filter android:autoVerify="true">
        <action android:name="android.intent.action.VIEW" />
        <category android:name="android.intent.category.DEFAULT" />
        <category android:name="android.intent.category.BROWSABLE" />

        <data
            android:scheme="panzoto"
            android:host="payment" />
    </intent-filter>
</activity>
```

### 6. Navigate to Cost Screen

**Automatic Navigation:**
```kotlin
LaunchedEffect(pendingPaymentSuccess) {
    if (pendingPaymentSuccess) {
        navController.navigate("cost") {
            popUpTo("home")
        }
        pendingPaymentSuccess = false
    }
}
```

**User Experience:**
- App automatically navigates to Cost screen
- Updated credit balance displayed
- User sees their new credits immediately

---

## Files Modified

### Android App (`/Users/fangfanglai/AndroidStudioProjects/Panzoto/`)

#### 1. **PaymentScreen.kt** (NEW)
- Three credit package cards ($5, $10, $20)
- Stripe checkout session creation
- Loading states and error handling
- Pricing information card

#### 2. **MainActivity.kt**
- `onNewIntent()` override for deep link handling
- `handleDeepLink()` method for payment success/cancel
- `pendingPaymentSuccess` state for navigation
- Pass state to MainAppScreen

**Key Changes:**
```kotlin
// Line 94: State variable
private var pendingPaymentSuccess by mutableStateOf(false)

// Line 103: Handle deep link on launch
handleDeepLink(intent)

// Lines 179-206: Deep link handler
override fun onNewIntent(intent: Intent)
private fun handleDeepLink(intent: Intent?)
```

#### 3. **AndroidManifest.xml**
- Deep link intent filter for `panzoto://payment`
- `launchMode="singleTop"` to prevent duplicate activities

#### 4. **AuthModels.kt**
- `CreateCheckoutSessionRequest` data class
- `CreateCheckoutSessionResponse` data class

#### 5. **AuthService.kt**
- `createCheckoutSession(amount: Double)` method
- POST request to `/api/create-checkout-session`

#### 6. **CostScreen.kt**
- Full-width orange "Add Credits" button
- Credit card icon
- `onNavigateToPayment` callback parameter

#### 7. **HomeScreen.kt**
- Minor UI adjustments (if any)

---

## Backend Configuration

### Config (`decision_data/backend/config/config.py`)

```python
FRONTEND_URL: str = "panzoto://payment"  # Android deep link
```

### Stripe Test Keys

**In `.env`:**
```bash
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_eLgQWtKzo2Hatvp6bJ0jRbonKKpPMC1X
```

---

## Testing

### Test Mode Payment

**Test Card:** 4242 4242 4242 4242
- Any future expiry date
- Any 3-digit CVC
- Any billing ZIP code

**Test Flow:**
1. Open Panzoto app
2. Navigate to Cost screen or "Get Credits" in drawer
3. Tap "Add Credits" button
4. Select a credit package ($5, $10, or $20)
5. Browser opens with Stripe Checkout
6. Enter test card: `4242 4242 4242 4242`
7. Complete payment
8. App automatically reopens
9. See "Payment successful!" toast
10. View updated credit balance on Cost screen

**Expected Results:**
- ✅ Browser opens with Stripe Checkout
- ✅ Test payment processes successfully
- ✅ App automatically reopens
- ✅ Success toast message displayed
- ✅ Navigation to Cost screen
- ✅ Credit balance updated (via webhook)

---

## Current Limitations

### 1. HTTP Only (Not Production Ready)

**Issue:** Stripe webhooks require HTTPS for production

**Current Setup:**
- Backend: `http://206.189.185.129:8000`
- Works in test mode
- **NOT** suitable for real payments

**Solution Required:**
- Set up HTTPS with domain name
- Configure SSL certificate
- Update Stripe webhook URL to HTTPS endpoint

### 2. Test Mode Only

**Current Configuration:**
- Using Stripe test keys
- Only test cards work
- No real money processed

**For Production:**
- Switch to live Stripe keys
- Configure production webhook endpoint
- Enable HTTPS (required)

---

## Production Checklist

Before accepting real payments:

- [ ] **Set up domain name** (e.g., `api.panzoto.com`)
- [ ] **Configure HTTPS/SSL certificate** (Let's Encrypt or CloudFlare)
- [ ] **Update backend URL** in Android app to HTTPS
- [ ] **Switch to Stripe live keys** in backend `.env`
- [ ] **Configure production webhook** in Stripe Dashboard
- [ ] **Test with real card** (small amount like $0.50)
- [ ] **Verify webhook receives events** over HTTPS
- [ ] **Test refund flow** (if needed)
- [ ] **Monitor first real transactions** closely

---

## Security Notes

### Payment Security

✅ **What's Secure:**
- Card details never touch our servers
- Stripe handles all PCI compliance
- Payment processing by Stripe (certified)
- Webhook signature verification

✅ **Fraud Prevention:**
- Deep link doesn't credit account (only UX)
- Actual crediting via webhook (server-verified)
- Manually visiting `panzoto://payment/success` does nothing
- Stripe session ID validated on webhook

### Architecture Security

**Why Deep Link is Safe:**
- Deep link = UI feedback only
- Credits added via webhook (async)
- Webhook verifies payment with Stripe
- Cannot fake credits by opening deep link

**Payment Flow Security:**
1. User requests checkout → Backend creates Stripe session
2. Stripe processes payment → Stripe sends webhook
3. Webhook verified → Backend credits account
4. Deep link → App shows success message

**Result:** Even if user manually opens deep link, they don't get free credits because crediting happens via webhook verification.

---

## Next Steps

### Immediate (Required for Production)

1. **HTTPS Setup** (CRITICAL)
   - Register domain name
   - Point DNS to DigitalOcean server (206.189.185.129)
   - Install SSL certificate (Let's Encrypt)
   - Configure Nginx reverse proxy
   - Update Android app backend URL to HTTPS

2. **Stripe Production Keys**
   - Switch from test to live keys
   - Update webhook endpoint to HTTPS
   - Configure production webhook secret

3. **Testing**
   - Small real transaction test ($0.50)
   - Verify webhook delivery
   - Confirm credits added correctly

### Future Enhancements

- [ ] Email receipt after payment
- [ ] Payment history screen
- [ ] Refund support (if needed)
- [ ] Multiple payment methods (Google Pay, Apple Pay)
- [ ] Subscription model (monthly credits)
- [ ] Promotional codes/discounts

---

## Troubleshooting

### Payment Button Not Working

**Check:**
1. Backend server running: `curl http://206.189.185.129:8000/api/health`
2. JWT token valid (not expired)
3. Network connectivity
4. Logcat for error messages

### App Doesn't Reopen After Payment

**Check:**
1. Deep link configured in AndroidManifest.xml
2. `launchMode="singleTop"` set
3. Stripe redirect URLs configured correctly
4. Test deep link manually: `adb shell am start -a android.intent.action.VIEW -d "panzoto://payment/success?session_id=test"`

### Credits Not Added After Payment

**Check:**
1. Webhook endpoint accessible: `curl http://206.189.185.129:8000/api/stripe-webhook`
2. Webhook signature validation passing
3. Backend logs for webhook events
4. Stripe dashboard for webhook delivery status

### Test Card Declined

**Use correct test card:**
- Success: `4242 4242 4242 4242`
- Decline: `4000 0000 0000 0002`
- More test cards: https://stripe.com/docs/testing

---

## Cost Analysis

### Per Transaction Costs

**Stripe Fees:**
- 2.9% + $0.30 per successful card charge

**Examples:**
- $5.00 charge → $0.445 fee (8.9%) → $4.555 net
- $10.00 charge → $0.590 fee (5.9%) → $9.410 net
- $20.00 charge → $0.880 fee (4.4%) → $19.120 net

**Recommendation:** Higher amounts = lower percentage fees

### AWS Costs (Minimal)

- DynamoDB writes: ~$0.0000001 per credit update
- API calls: Free tier (negligible)
- No additional infrastructure needed

---

## Monitoring

### Key Metrics to Track

1. **Payment Success Rate**
   - Target: >95%
   - Monitor Stripe dashboard

2. **Webhook Delivery Rate**
   - Target: 100%
   - Check webhook logs

3. **Average Transaction Value**
   - Goal: Optimize package pricing
   - Track via Stripe analytics

4. **Time to Credit**
   - Should be < 5 seconds
   - Monitor backend logs

---

## Support & Documentation

### Stripe Resources

- Dashboard: https://dashboard.stripe.com
- Test Mode: https://dashboard.stripe.com/test
- Webhook Logs: https://dashboard.stripe.com/webhooks
- API Docs: https://stripe.com/docs/api

### Internal Documentation

- Backend API: `docs/STRIPE_INTEGRATION.md`
- Android CLAUDE.md: `/Users/fangfanglai/AndroidStudioProjects/Panzoto/CLAUDE.md`
- Main CLAUDE.md: `/Users/fangfanglai/Projects/decision_data/CLAUDE.md`

---

**Last Updated:** October 26, 2025
**Status:** ✅ Test Mode Working | ⏳ Production Pending HTTPS Setup
