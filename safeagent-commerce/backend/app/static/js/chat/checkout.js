/**
 * chat/checkout.js — Razorpay Standard Checkout Modal
 * ======================================================
 * Flow:
 *   1. User clicks "Pay Now" after Validator PASS
 *   2. openRazorpayModal() opens the Razorpay checkout modal with the order_id
 *      from the already-validated checkout_data
 *   3. On payment.success → send the 3 tokens to POST /api/verify-payment
 *      (backend does HMAC-SHA256, marks order CAPTURED)
 *   4. On payment.failed or modal dismiss → show error, allow retry
 *
 * KEY_SECRET never touches this file. Only KEY_ID is used here.
 */

async function handleCheckout() {
    if (!activeCartId || cartItems.length === 0) return;
    checkoutState = "validating";
    updateValidatorBox();

    try {
        const data = await apiCheckout(activeCartId, sessionId);
        if (data.is_blocked) {
            if (data.block_reason_code === "CART_ALREADY_PAID") {
                checkoutState = "paid";
                updateValidatorBox(data.reply, data.block_reason_code, null);
            } else {
                checkoutState = "blocked";
                updateValidatorBox(data.reply, data.block_reason_code, null);
            }
        } else {
            checkoutState = "approved";
            updateValidatorBox(data.reply, "PASS", data.checkout_data);
        }
        await fetchCartFromBackend();
    } catch (err) {
        checkoutState = "blocked";
        updateValidatorBox("Server error: " + err.message, "SERVER_ERROR", null);
    }
}

function openRazorpayModal(checkoutData) {
    /**
     * Opens the Razorpay Standard Checkout modal.
     * checkoutData is from POST /chat/checkout response:
     *   { razorpay_order_id, razorpay_key_id, amount_paisa, amount_rupees }
     */
    const rootEl = document.getElementById("chat-root");
    const keyId  = rootEl.dataset.razorpayKey;

    if (!keyId || keyId.startsWith("rzp_test_placeholder")) {
        appendSystemError("Razorpay key not configured. Check .env file.");
        return;
    }

    const options = {
        key:         keyId,
        amount:      checkoutData.amount_paisa,
        currency:    "INR",
        order_id:    checkoutData.razorpay_order_id,
        name:        "SafeAgent Commerce",
        description: "Validator-approved purchase",
        theme:       { color: "#6366f1" },

        handler: async function (response) {
            // ── Payment success: verify signature on backend ───────────────
            try {
                const result = await apiVerifyPayment(
                    response.razorpay_order_id,
                    response.razorpay_payment_id,
                    response.razorpay_signature,
                    sessionId,
                );
                showPaymentSuccess(result);
            } catch (err) {
                appendSystemError("Payment made but verification failed: " + err.message);
            }
        },

        modal: {
            ondismiss: function () {
                // User closed modal without paying — reset to approved so they can retry
                appendSystemError("Payment cancelled. You can click 'Pay Now' to try again.");
            }
        },

        prefill: {},

        notes: {
            session_id: sessionId,
            cart_id:    activeCartId,
        },
    };

    const rzp = new Razorpay(options);

    rzp.on("payment.failed", function (response) {
        appendSystemError(
            "Payment failed: " + (response.error?.description || "Unknown error from Razorpay.")
        );
        checkoutState = "blocked";
        updateValidatorBox(
            response.error?.description || "Payment declined by Razorpay.",
            response.error?.reason || "PAYMENT_FAILED",
            null,
        );
    });

    rzp.open();
}

function showPaymentSuccess(result) {
    /**
     * Show a success message in the chat stream after payment capture.
     * Refreshes cart so sidebar shows PAID state.
     */
    checkoutState = "paid";
    updateValidatorBox();
    updateCartStatusBadge("paid");

    const c = document.getElementById("messages-container");
    const div = document.createElement("div");
    div.className = "message-enter flex justify-center";
    div.innerHTML = `
        <div class="max-w-lg rounded-xl px-5 py-4 border text-center space-y-1"
             style="background: var(--color-success-bg); borderColor: var(--color-success-border);">
            <p class="text-sm font-semibold text-emerald-800">Payment Successful!</p>
            <p class="text-xs text-emerald-700">
                ₹${result.amount_rupees.toLocaleString("en-IN")} charged · Order #${result.order_id}
            </p>
            <p class="text-[11px] text-emerald-600">Payment ID: ${result.razorpay_payment_id}</p>
        </div>`;
    c.appendChild(div);
    c.scrollTop = c.scrollHeight;
    fetchCartFromBackend();
}
